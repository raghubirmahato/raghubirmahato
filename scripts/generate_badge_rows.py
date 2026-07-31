#!/usr/bin/env python3
"""Self-draw the profile's badges (email/github/instagram/facebook,
followers/views/location) as individual SVGs with a real drop-shadow
glow, one file per badge so each can still be wrapped in its own
markdown <a href> (GitHub strips <map>/<area>, so a single flattened
image can't carry multiple click targets — verified via the Markdown
render API).

GitHub's markdown sanitizer strips inline `style`/CSS from rendered
markdown, so a shadow can only exist by baking it into the image itself
(same reasoning as matrix-divider-*.svg and stats-card.svg elsewhere in
this repo). shields.io/komarev have no shadow option, so badges are
redrawn here instead of embedded.

Followers and profile-view counts are live values fetched at generation
time (refreshed periodically by .github/workflows/stats.yml), not
hardcoded, so they drift only as far as the refresh cadence.
"""
import os
import sys
import json
import re
import urllib.request
from xml.sax.saxutils import escape

BG_LABEL = "#0f0a1a"
PURPLE = "#d11aff"
CYAN = "#00d9ff"
LABEL_TEXT = "#ffffff"
VALUE_TEXT = "#0f0a1a"

HEIGHT = 32
FONT_SIZE = 12.5
CHAR_W = 8.6  # heuristic average width for bold uppercase sans-serif at FONT_SIZE
H_PAD = 14
SHADOW_MARGIN = 5  # must cover the glow's blur radius so it isn't clipped


def text_w(s):
    return len(s) * CHAR_W


def build_badge_svg(label, value, color):
    label_w = text_w(label) + H_PAD * 2
    value_w = text_w(value) + H_PAD * 2
    inner_w = label_w + value_w
    filter_id = "glow-purple" if color == PURPLE else "glow-cyan"

    canvas_w = inner_w + 2 * SHADOW_MARGIN
    canvas_h = HEIGHT + 2 * SHADOW_MARGIN
    x = SHADOW_MARGIN
    y = SHADOW_MARGIN

    return f'''<svg width="{canvas_w:.1f}" height="{canvas_h:.1f}" viewBox="0 0 {canvas_w:.1f} {canvas_h:.1f}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="glow-purple" x="-60%" y="-60%" width="220%" height="220%">
      <feDropShadow dx="0" dy="0.8" stdDeviation="1.6" flood-color="{PURPLE}" flood-opacity="0.85"/>
    </filter>
    <filter id="glow-cyan" x="-60%" y="-60%" width="220%" height="220%">
      <feDropShadow dx="0" dy="0.8" stdDeviation="1.6" flood-color="{CYAN}" flood-opacity="0.85"/>
    </filter>
  </defs>
  <g filter="url(#{filter_id})">
    <rect x="{x:.1f}" y="{y:.1f}" width="{label_w:.1f}" height="{HEIGHT}" fill="{BG_LABEL}" />
    <rect x="{x+label_w:.1f}" y="{y:.1f}" width="{value_w:.1f}" height="{HEIGHT}" fill="{color}" />
    <text x="{x+label_w/2:.1f}" y="{y+HEIGHT/2+4.5:.1f}" fill="{LABEL_TEXT}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="{FONT_SIZE}" font-weight="700" letter-spacing="0.6" text-anchor="middle">{escape(label)}</text>
    <text x="{x+label_w+value_w/2:.1f}" y="{y+HEIGHT/2+4.5:.1f}" fill="{VALUE_TEXT}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="{FONT_SIZE}" font-weight="700" text-anchor="middle">{escape(value)}</text>
  </g>
</svg>
'''


def fetch_followers(login, token):
    req = urllib.request.Request(
        f"https://api.github.com/users/{login}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "hackdev-badge-generator"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)["followers"]


# komarev's view counter is keyed by this literal string, independent of
# the actual GitHub login — kept as the original username so the account
# rename (raghubirrajmahato15 -> raghubirmahato) doesn't reset the
# accumulated view count back to zero.
VIEWS_COUNTER_KEY = "raghubirrajmahato15"


def fetch_profile_views(counter_key):
    req = urllib.request.Request(
        f"https://komarev.com/ghpvc/?username={counter_key}&style=flat",
        headers={"User-Agent": "hackdev-badge-generator"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        svg = resp.read().decode("utf-8", "ignore")
    m = re.search(r">([\d,]+)<", svg)
    return m.group(1) if m else "0"


def main():
    login = os.environ.get("GH_USERNAME") or (sys.argv[1] if len(sys.argv) > 1 else None)
    token = os.environ.get("GH_TOKEN")
    outdir = os.environ.get("OUT_DIR", ".")
    if not login or not token:
        print("Usage: GH_TOKEN=... GH_USERNAME=... python generate_badge_rows.py", file=sys.stderr)
        sys.exit(1)

    followers = fetch_followers(login, token)
    views = fetch_profile_views(VIEWS_COUNTER_KEY)

    badges = [
        ("badge-email", "EMAIL", "raghubirrajmahato15@gmail.com", PURPLE),
        ("badge-github", "GITHUB", "raghubirmahato", CYAN),
        ("badge-instagram", "INSTAGRAM", "raghubir_raj_mahato", PURPLE),
        ("badge-facebook", "FACEBOOK", "Raghubir Mahato", CYAN),
        ("badge-followers", "FOLLOWERS", str(followers), PURPLE),
        ("badge-views", "PROFILE VIEWS", views, CYAN),
        ("badge-location", "BASED IN", "KATHMANDU, NEPAL", PURPLE),
    ]

    for filename, label, value, color in badges:
        svg = build_badge_svg(label, value, color)
        out = f"{outdir}/{filename}.svg"
        with open(out, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
