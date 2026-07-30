#!/usr/bin/env python3
"""Generate self-hosted GitHub stats + top-langs + streak SVG cards.

Fetches data directly from the GitHub GraphQL API (no third-party
rendering service dependency) and renders three theme-matched SVGs into
the repo root. Run standalone (GH_TOKEN + GH_USERNAME env vars) or via
.github/workflows/stats.yml.
"""
import os
import sys
import json
import datetime
import urllib.request
from xml.sax.saxutils import escape

BG = "#0f0a1a"
TITLE = "#d11aff"
ACCENT = "#00d9ff"
TEXT = "#e2e8f0"
MUTED = "#8b8398"
BORDER = "#2a1f3d"

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount forkCount primaryLanguage { name color } }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_user(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "hackdev-stats-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def compute_stats(user):
    repos = user["repositories"]["nodes"]
    total_stars = sum(r["stargazerCount"] for r in repos)
    total_forks = sum(r["forkCount"] for r in repos)
    total_repos = user["repositories"]["totalCount"]
    followers = user["followers"]["totalCount"]

    cal = user["contributionsCollection"]["contributionCalendar"]
    total_contrib = cal["totalContributions"]
    days = []
    for w in cal["weeks"]:
        for d in w["contributionDays"]:
            days.append((datetime.date.fromisoformat(d["date"]), d["contributionCount"]))
    days.sort()

    idx = len(days) - 1
    if days and days[idx][1] == 0:
        idx -= 1
    current_streak = 0
    while idx >= 0 and days[idx][1] > 0:
        current_streak += 1
        idx -= 1

    longest_streak = 0
    run = 0
    for _, count in days:
        if count > 0:
            run += 1
            longest_streak = max(longest_streak, run)
        else:
            run = 0

    lang_counts = {}
    for r in repos:
        lang = r["primaryLanguage"]
        if not lang:
            continue
        key = (lang["name"], lang["color"] or "#888888")
        lang_counts[key] = lang_counts.get(key, 0) + 1
    top_langs = sorted(lang_counts.items(), key=lambda kv: -kv[1])[:6]

    return {
        "name": user["name"],
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_repos": total_repos,
        "followers": followers,
        "total_contrib": total_contrib,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "top_langs": top_langs,
    }


def stats_card_svg(s):
    w, h = 460, 195
    rows = [
        ("Total Stars", s["total_stars"], "★"),
        ("Total Commits (past year)", s["total_contrib"], "◈"),
        ("Total Repositories", s["total_repos"], "▤"),
        ("Followers", s["followers"], "◉"),
        ("Total Forks", s["total_forks"], "⎇"),
    ]
    row_y = 76
    row_h = 26
    body = []
    for label, value, icon in rows:
        body.append(f'''
    <g transform="translate(28,{row_y})">
      <text fill="{ACCENT}" font-family="monospace" font-size="15">{escape(icon)}</text>
      <text x="24" y="0" fill="{TEXT}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13.5">{escape(label)}:</text>
      <text x="{w - 56}" y="0" fill="{TITLE}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="14.5" font-weight="700" text-anchor="end">{value}</text>
    </g>''')
        row_y += row_h

    return f'''<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="14" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>
  <text x="28" y="36" fill="{TITLE}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="18" font-weight="700">{escape(s["name"])}&#8217;s GitHub Stats</text>
  <line x1="28" y1="48" x2="{w-28}" y2="48" stroke="{BORDER}" stroke-width="1"/>
  {''.join(body)}
</svg>
'''


def top_langs_svg(s):
    w, h = 370, 195
    langs = s["top_langs"]
    total = sum(c for _, c in langs) or 1

    bar_y = 100
    bar_w = w - 56
    x = 28
    segs = []
    for (name, color), count in langs:
        seg_w = bar_w * count / total
        segs.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="10" fill="{color}" />')
        x += seg_w
    bar_markup = "".join(segs)

    legend = []
    ly = bar_y + 30
    col_w = (w - 56) / 2
    for i, ((name, color), count) in enumerate(langs):
        pct = 100 * count / total
        cx = 28 + (i % 2) * col_w
        cy = ly + (i // 2) * 24
        legend.append(f'''
    <circle cx="{cx+4}" cy="{cy-4}" r="5" fill="{color}" />
    <text x="{cx+16}" y="0" transform="translate(0,{cy})" fill="{TEXT}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12.5">{escape(name)} <tspan fill="{MUTED}">{pct:.1f}%</tspan></text>''')

    return f'''<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="14" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>
  <text x="28" y="36" fill="{TITLE}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="18" font-weight="700">Most Used Languages</text>
  <line x1="28" y1="48" x2="{w-28}" y2="48" stroke="{BORDER}" stroke-width="1"/>
  <rect x="28" y="{bar_y}" width="{bar_w}" height="10" rx="5" fill="#1c1430" />
  {bar_markup}
  {''.join(legend)}
</svg>
'''


def streak_svg(s):
    w, h = 460, 195
    cx_total, cx_current, cx_longest = 90, 230, 370
    cy = 95
    r = 46

    def stat_block(cx, value, label, ring=False):
        parts = []
        if ring:
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TITLE}" stroke-width="2.5" />')
            parts.append(f'<circle cx="{cx}" cy="{cy-r-14}" r="4" fill="{ACCENT}" />')
        parts.append(f'<text x="{cx}" y="{cy-4}" fill="{TITLE if ring else TEXT}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="26" font-weight="800" text-anchor="middle">{value}</text>')
        parts.append(f'<text x="{cx}" y="{cy+18}" fill="{MUTED}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11" text-anchor="middle">{escape(label)}</text>')
        return "".join(parts)

    body = (
        stat_block(cx_total, s["total_contrib"], "Total Contributions")
        + stat_block(cx_current, s["current_streak"], "Current Streak", ring=True)
        + stat_block(cx_longest, s["longest_streak"], "Longest Streak")
    )
    return f'''<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="14" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>
  <text x="{w/2}" y="30" fill="{TITLE}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="15" font-weight="700" text-anchor="middle">{escape(s["name"])}&#8217;s Contribution Streak</text>
  <line x1="{cx_total+r+22}" y1="35" x2="{cx_total+r+22}" y2="{h-25}" stroke="{BORDER}" stroke-width="1"/>
  <line x1="{cx_longest-r-22}" y1="35" x2="{cx_longest-r-22}" y2="{h-25}" stroke="{BORDER}" stroke-width="1"/>
  {body}
</svg>
'''


def main():
    login = os.environ.get("GH_USERNAME") or (sys.argv[1] if len(sys.argv) > 1 else None)
    token = os.environ.get("GH_TOKEN")
    outdir = os.environ.get("OUT_DIR", ".")
    if not login or not token:
        print("Usage: GH_TOKEN=... GH_USERNAME=... python generate_stats.py", file=sys.stderr)
        sys.exit(1)

    user = fetch_user(login, token)
    s = compute_stats(user)

    with open(f"{outdir}/stats-card.svg", "w", encoding="utf-8") as f:
        f.write(stats_card_svg(s))
    with open(f"{outdir}/top-langs.svg", "w", encoding="utf-8") as f:
        f.write(top_langs_svg(s))
    with open(f"{outdir}/streak-stats.svg", "w", encoding="utf-8") as f:
        f.write(streak_svg(s))

    print(json.dumps(s, default=str, indent=2))


if __name__ == "__main__":
    main()
