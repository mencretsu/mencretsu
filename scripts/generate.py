#!/usr/bin/env python3
"""
scripts/generate.py — GitHub Profile README Generator
mencretsu/mencretsu

Pulls data from GitHub REST API, generates 4 SVG "chapters" into assets/.
Run via GitHub Actions or locally:
  GH_TOKEN=<your_pat> python scripts/generate.py

Token priority: GH_TOKEN (PAT, full repo access) → GITHUB_TOKEN (built-in, public only).
For private repo stats, add a PAT as GH_TOKEN secret in repo settings.
"""

import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

# ─── Config ──────────────────────────────────────────────────────────────────

USERNAME = "mencretsu"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ─── Palette ─────────────────────────────────────────────────────────────────

BG      = "#010409"
SURFACE = "#0d1117"
BORDER  = "#21262d"
TEXT    = "#e6edf3"
DIM     = "#8b949e"
ACCENT  = "#388bfd"
GREEN   = "#3fb950"
ORANGE  = "#f0883e"
PURPLE  = "#a371f7"
FONT    = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"

# ─── Helpers ─────────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    """XML-escape a string for safe SVG embedding."""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def get(url: str, params: dict = None, retries: int = 3) -> list | dict:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        except requests.RequestException as e:
            print(f"    request error: {e}", flush=True)
            time.sleep(5 * (attempt + 1))
            continue

        if r.status_code == 403:
            if r.headers.get("X-RateLimit-Remaining") == "0":
                reset_ts = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset_ts - time.time(), 0) + 5
                print(f"    rate limit — sleeping {wait:.0f}s …", flush=True)
                time.sleep(wait)
                continue

        if r.status_code in (404, 409):
            return []
        if r.status_code == 200:
            return r.json()

        print(f"    HTTP {r.status_code} for {url}", flush=True)
        return []

    return []


def get_pages(url: str, params: dict = None, max_pages: int = 5) -> list:
    params = params or {}
    out = []
    for page in range(1, max_pages + 1):
        chunk = get(url, {**params, "per_page": 100, "page": page})
        if not isinstance(chunk, list) or not chunk:
            break
        out.extend(chunk)
        if len(chunk) < 100:
            break
    return out


# ─── Data collection ─────────────────────────────────────────────────────────

def collect() -> dict:
    print("→ fetching repos …", flush=True)
    repos = get_pages(
        "https://api.github.com/user/repos",
        {"type": "owner", "sort": "pushed"},
        max_pages=10,
    )
    own = [r for r in repos if not r.get("fork")]
    print(f"  {len(own)} own repos found", flush=True)

    since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    commits_by_date: dict[str, int] = defaultdict(int)
    commits_by_hour: dict[int, int] = defaultdict(int)
    commits_by_dow: dict[int, int]  = defaultdict(int)
    commit_messages: list[str]       = []
    repo_commit_counts: dict[str, int] = {}

    for i, repo in enumerate(own):
        name = repo["name"]
        print(f"  [{i+1}/{len(own)}] {name}", flush=True)

        raw = get_pages(
            f"https://api.github.com/repos/{USERNAME}/{name}/commits",
            {"author": USERNAME, "since": since},
            max_pages=3,
        )

        count = 0
        for c in raw:
            author = c.get("commit", {}).get("author", {})
            date_str = author.get("date", "")
            if not date_str:
                continue
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            commits_by_date[dt.strftime("%Y-%m-%d")] += 1
            commits_by_hour[dt.hour] += 1
            commits_by_dow[dt.weekday()] += 1  # 0=Mon … 6=Sun

            msg = c.get("commit", {}).get("message", "").split("\n")[0].strip()
            if msg:
                commit_messages.append(msg)
            count += 1

        repo_commit_counts[name] = count

    return {
        "repos": own,
        "commits_by_date": dict(commits_by_date),
        "commits_by_hour": dict(commits_by_hour),
        "commits_by_dow": dict(commits_by_dow),
        "commit_messages": commit_messages,
        "repo_commit_counts": repo_commit_counts,
        "total_commits": sum(commits_by_date.values()),
    }


# ─── Chapter 1 — The Numbers ─────────────────────────────────────────────────

def ch1(data: dict) -> str:
    total    = data["total_commits"]
    by_hour  = data["commits_by_hour"]
    by_dow   = data["commits_by_dow"]

    fav_hour = max(by_hour, key=by_hour.get) if by_hour else 2
    fav_dow  = max(by_dow,  key=by_dow.get)  if by_dow  else 6

    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def _hlabel(h: int) -> str:
        if h == 0:  return "12 AM"
        if h < 12:  return f"{h} AM"
        if h == 12: return "12 PM"
        return f"{h - 12} PM"

    def _hvibe(h: int) -> str:
        if 0 <= h < 3:  return "dini hari. compiler jadi satu-satunya temen"
        if 3 <= h < 6:  return "jam segini? lo baik-baik aja kan?"
        if 6 <= h < 9:  return "pagi-pagi langsung ngoding. gila"
        if 9 <= h < 12: return "jam normal. mencurigakan"
        if 12 <= h < 14: return "ngoding sambil makan siang, lol"
        if 14 <= h < 17: return "afternoon grind. efektif"
        if 17 <= h < 20: return "pulang langsung buka editor"
        if 20 <= h < 22: return "malam, tenang, flow state"
        return "deep night. no distraction. pure chaos"

    def _vibe(h: int) -> str:
        if 0 <= h < 6:  return "compiler jadi saksi bisu jam segini."
        if 6 <= h < 12: return "workflow rapi. lo oke kok."
        if 12 <= h < 18: return "ngoding di jam orang kerja. kalkulasi risikonya."
        return "malam adalah canvas-mu. dan bug adalah teman lamamu."

    total_str = f"{total:,}"
    hour_str  = _hlabel(fav_hour)
    day_str   = DAYS[fav_dow]

    # Bar chart layout (centered)
    BAR_W, BAR_GAP = 24, 6
    BAR_STEP   = BAR_W + BAR_GAP
    BAR_MAX    = 32
    BAR_Y      = 306
    # center 24 bars (total span = 24*30 - gap = 714)
    GRID_X     = (800 - (24 * BAR_STEP - BAR_GAP)) // 2
    max_h      = max(by_hour.values(), default=1)

    bars = ""
    for h in range(24):
        cnt = by_hour.get(h, 0)
        bh  = max(int((cnt / max_h) * BAR_MAX), 1 if cnt > 0 else 0)
        x   = GRID_X + h * BAR_STEP
        col = ACCENT if h == fav_hour else BORDER
        opa = "1" if h == fav_hour else "0.65"
        if bh:
            bars += (
                f'  <rect x="{x}" y="{BAR_Y + BAR_MAX - bh}" '
                f'width="{BAR_W}" height="{bh}" fill="{col}" rx="3" opacity="{opa}"/>\n'
            )

    for h in [0, 6, 12, 18, 23]:
        lx = GRID_X + h * BAR_STEP + BAR_W // 2
        bars += (
            f'  <text x="{lx}" y="{BAR_Y + BAR_MAX + 15}" '
            f'font-family="{FONT}" font-size="9" fill="{DIM}" text-anchor="middle">{h:02d}</text>\n'
        )

    return f'''\
<svg width="800" height="400" viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="glow1">
      <feGaussianBlur stdDeviation="4" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="lg1" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{ACCENT};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:{PURPLE};stop-opacity:0"/>
    </linearGradient>
  </defs>

  <!-- bg -->
  <rect width="800" height="400" fill="{BG}" rx="12"/>
  <rect x="1" y="1" width="798" height="398" fill="none" stroke="{BORDER}" stroke-width="1" rx="11"/>

  <!-- header label -->
  <text x="36" y="48" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="3">THE NUMBERS</text>
  <text x="764" y="48" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="2" text-anchor="end">LAST 365 DAYS</text>
  <rect x="36" y="58" width="220" height="1" fill="url(#lg1)"/>

  <!-- stat 1 — total commits -->
  <text x="145" y="160" font-family="{FONT}" font-size="58" font-weight="700"
        fill="{TEXT}" text-anchor="middle" filter="url(#glow1)">{esc(total_str)}</text>
  <text x="145" y="182" font-family="{FONT}" font-size="10" fill="{DIM}"
        text-anchor="middle" letter-spacing="3">COMMITS</text>

  <line x1="272" y1="105" x2="272" y2="200" stroke="{BORDER}" stroke-width="1"/>

  <!-- stat 2 — peak hour -->
  <text x="450" y="152" font-family="{FONT}" font-size="46" font-weight="700"
        fill="{ACCENT}" text-anchor="middle" filter="url(#glow1)">{esc(hour_str)}</text>
  <text x="450" y="174" font-family="{FONT}" font-size="10" fill="{DIM}"
        text-anchor="middle" letter-spacing="3">PEAK HOUR</text>
  <text x="450" y="192" font-family="{FONT}" font-size="10" fill="{PURPLE}"
        text-anchor="middle">— {esc(_hvibe(fav_hour))} —</text>

  <line x1="590" y1="105" x2="590" y2="200" stroke="{BORDER}" stroke-width="1"/>

  <!-- stat 3 — most active day -->
  <text x="700" y="152" font-family="{FONT}" font-size="26" font-weight="700"
        fill="{ORANGE}" text-anchor="middle" filter="url(#glow1)">{esc(day_str)}</text>
  <text x="700" y="174" font-family="{FONT}" font-size="10" fill="{DIM}"
        text-anchor="middle" letter-spacing="2">MOST ACTIVE</text>

  <!-- vibe divider -->
  <rect x="36" y="213" width="728" height="1" fill="{BORDER}"/>
  <text x="400" y="252" font-family="{FONT}" font-size="13" fill="{DIM}"
        text-anchor="middle" font-style="italic">&quot;{esc(_vibe(fav_hour))}&quot;</text>

  <!-- activity spread -->
  <text x="36" y="294" font-family="{FONT}" font-size="10" fill="{DIM}" letter-spacing="2">HOURLY ACTIVITY</text>
  <rect x="36" y="300" width="728" height="1" fill="{BORDER}" opacity="0.35"/>

{bars}
</svg>'''


# ─── Chapter 2 — The Grind (heatmap) ─────────────────────────────────────────

def ch2(data: dict) -> str:
    cbd     = data["commits_by_date"]
    by_hour = data["commits_by_hour"]
    by_dow  = data["commits_by_dow"]
    total   = data["total_commits"]

    CELL = 11
    GAP  = 3
    STEP = CELL + GAP
    LEFT = 52
    TOP  = 72
    W, H = 800, 235

    today     = datetime.now(timezone.utc).date()
    start_raw = today - timedelta(days=363)
    # rewind to the previous Sunday
    start = start_raw - timedelta(days=(start_raw.isoweekday() % 7))

    total_days  = (today - start).days + 1
    total_weeks = min(math.ceil(total_days / 7), 53)

    max_day = max(cbd.values(), default=1)

    def cell_color(n: int) -> str:
        if n == 0:            return "#161b22"
        r = n / max_day
        if r < 0.20:          return "#0e4429"
        if r < 0.45:          return "#006d32"
        if r < 0.75:          return "#26a641"
        return "#39d353"

    cells        = ""
    month_seen: dict[str, int] = {}

    for week in range(total_weeks):
        for dow in range(7):  # 0=Sun … 6=Sat
            date = start + timedelta(days=week * 7 + dow)
            if date > today:
                continue

            mk = date.strftime("%Y-%m")
            if mk not in month_seen:
                month_seen[mk] = week

            count = cbd.get(date.strftime("%Y-%m-%d"), 0)
            cx    = LEFT + week * STEP
            cy    = TOP  + dow  * STEP
            col   = cell_color(count)
            glow  = ' filter="url(#glow2)"' if count >= max_day * 0.75 and count > 0 else ""
            cells += f'  <rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" fill="{col}" rx="2"{glow}/>\n'

    month_labels = ""
    for mk, week in sorted(month_seen.items())[:13]:
        abbr = datetime.strptime(mk, "%Y-%m").strftime("%b")
        x    = LEFT + week * STEP
        month_labels += (
            f'  <text x="{x}" y="{TOP - 8}" font-family="{FONT}" '
            f'font-size="9" fill="{DIM}">{abbr}</text>\n'
        )

    day_labels = ""
    for di, dname in enumerate(["", "Mon", "", "Wed", "", "Fri", ""]):
        if dname:
            y = TOP + di * STEP + CELL
            day_labels += (
                f'  <text x="{LEFT - 7}" y="{y}" font-family="{FONT}" '
                f'font-size="9" fill="{DIM}" text-anchor="end">{dname}</text>\n'
            )

    night   = sum(v for k, v in by_hour.items() if k >= 22 or k < 6)
    weekend = sum(v for k, v in by_dow.items()  if k >= 5)
    night_p   = round(night   / total * 100) if total else 0
    weekend_p = round(weekend / total * 100) if total else 0

    if night_p > 50:
        tagline = f"{night_p}% commit jam malam/dini hari. night owl confirmed."
    elif weekend_p > 40:
        tagline = f"{weekend_p}% commit di weekend. weekday lo ngapain?"
    else:
        tagline = f"{night_p}% malam  ·  {weekend_p}% weekend  ·  pola yang cukup manusiawi"

    stats_y = TOP + 7 * STEP + 22

    return f'''\
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="glow2">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}" rx="12"/>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" fill="none" stroke="{BORDER}" stroke-width="1" rx="11"/>

  <text x="36" y="38" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="3">THE GRIND</text>
  <text x="{W - 36}" y="38" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="2" text-anchor="end">365 DAYS</text>
  <rect x="36" y="48" width="110" height="1" fill="{ACCENT}" opacity="0.4"/>

{month_labels}
{day_labels}
{cells}
  <text x="{LEFT}" y="{stats_y}" font-family="{FONT}" font-size="10" fill="{DIM}">{esc(tagline)}</text>
</svg>'''


# ─── Chapter 3 — The Journey (timeline) ──────────────────────────────────────

def ch3(data: dict) -> str:
    repos   = data["repos"]
    rcounts = data["repo_commit_counts"]

    LANG_COLORS = {
        "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
        "HTML": "#e34c26", "CSS": "#563d7c", "Java": "#b07219",
        "C": "#555555", "C++": "#f34b7d", "Go": "#00ADD8", "Rust": "#dea584",
        "Shell": "#89e051", "Kotlin": "#F18E33", "Swift": "#ffac45",
        "PHP": "#4F5D95", "Ruby": "#701516", "Vue": "#41b883", "Dart": "#00B4AB",
        "Svelte": "#ff3e00", "Lua": "#000080",
    }

    def score(r):
        cnt   = rcounts.get(r["name"], 0)
        stars = r.get("stargazers_count", 0)
        pushed = r.get("pushed_at", "")
        recency = 0
        if pushed:
            try:
                dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                recency = max(0, 365 - (datetime.now(timezone.utc) - dt).days)
            except ValueError:
                pass
        return cnt * 3 + stars * 5 + recency * 0.5

    meaningful = [r for r in repos if rcounts.get(r["name"], 0) > 0]
    top_names  = {r["name"] for r in sorted(meaningful, key=score, reverse=True)[:8]}
    timeline   = sorted(
        [r for r in meaningful if r["name"] in top_names],
        key=lambda r: r.get("created_at", ""),
    )

    n      = len(timeline)
    ROW_H  = 70
    W      = 800
    H      = max(100 + n * ROW_H + 50, 300)
    LINE_X = 132

    rows = ""
    for i, repo in enumerate(timeline):
        y = 88 + i * ROW_H

        try:
            dt        = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
            mon_str   = dt.strftime("%b")
            year_str  = dt.strftime("%Y")
        except (ValueError, KeyError):
            mon_str = year_str = "—"

        cnt   = rcounts.get(repo["name"], 0)
        lang  = repo.get("language") or "—"
        lcol  = LANG_COLORS.get(lang, DIM)
        desc  = (repo.get("description") or "no description.").strip()
        if len(desc) > 60:
            desc = desc[:57] + "…"
        stars = repo.get("stargazers_count", 0)

        rows += f"""\
  <!-- {esc(repo["name"])} -->
  <circle cx="{LINE_X}" cy="{y + 8}" r="6" fill="{ACCENT}" opacity="0.18"/>
  <circle cx="{LINE_X}" cy="{y + 8}" r="3" fill="{ACCENT}"/>

  <text x="{LINE_X - 11}" y="{y + 7}" font-family="{FONT}" font-size="9"
        fill="{DIM}" text-anchor="end">{esc(mon_str)}</text>
  <text x="{LINE_X - 11}" y="{y + 19}" font-family="{FONT}" font-size="9"
        fill="{DIM}" text-anchor="end">{esc(year_str)}</text>

  <text x="{LINE_X + 20}" y="{y + 14}" font-family="{FONT}" font-size="14"
        font-weight="700" fill="{TEXT}">{esc(repo["name"])}</text>
  <text x="{LINE_X + 20}" y="{y + 30}" font-family="{FONT}" font-size="10"
        fill="{DIM}">{esc(desc)}</text>

  <text x="{LINE_X + 20}" y="{y + 49}" font-family="{FONT}" font-size="9"
        fill="{ACCENT}">{cnt} commits</text>
  <circle cx="{LINE_X + 92}" cy="{y + 45}" r="4" fill="{lcol}"/>
  <text x="{LINE_X + 100}" y="{y + 49}" font-family="{FONT}" font-size="9"
        fill="{DIM}">{esc(lang)}</text>
"""
        if stars:
            rows += (
                f'  <text x="{LINE_X + 155}" y="{y + 49}" font-family="{FONT}" '
                f'font-size="9" fill="{ORANGE}">★ {stars}</text>\n'
            )
        if i < n - 1:
            rows += (
                f'  <line x1="{LINE_X + 20}" y1="{y + 60}" x2="764" y2="{y + 60}" '
                f'stroke="{BORDER}" stroke-width="1" opacity="0.35"/>\n'
            )

    tl_s = 88
    tl_e = 88 + n * ROW_H - 20

    return f'''\
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="tlg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%"   style="stop-color:{ACCENT};stop-opacity:0.7"/>
      <stop offset="100%" style="stop-color:{ACCENT};stop-opacity:0.04"/>
    </linearGradient>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}" rx="12"/>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" fill="none" stroke="{BORDER}" stroke-width="1" rx="11"/>

  <text x="36" y="48" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="3">THE JOURNEY</text>
  <text x="{W - 36}" y="48" font-family="{FONT}" font-size="11" fill="{DIM}"
        letter-spacing="2" text-anchor="end">{n} PROJECTS</text>
  <rect x="36" y="58" width="145" height="1" fill="{ACCENT}" opacity="0.4"/>

  <line x1="{LINE_X}" y1="{tl_s}" x2="{LINE_X}" y2="{tl_e}"
        stroke="url(#tlg)" stroke-width="1" stroke-dasharray="3,4"/>

{rows}
</svg>'''


# ─── Chapter 4 — In Your Own Words ───────────────────────────────────────────

def ch4(data: dict) -> str:
    messages = data["commit_messages"]

    BORING_EXACT = {
        "initial commit", "initial", "update", "updates", "fix", "fixes",
        "add", "added", "remove", "removed", "delete", "deleted", "wip",
        "test", "tests", "testing", "minor fix", "bug fix", "hotfix",
        "refactor", "cleanup", "clean up", "readme", "readme update",
        "update readme", "merge", "revert",
    }
    BORING_PREFIX = (
        "merge pull", "merge branch", "bump ", "revert ", "chore:", "ci:",
        "docs:", "style:", "build:",
    )

    def is_boring(m: str) -> bool:
        l = m.lower().strip()
        if l in BORING_EXACT: return True
        if any(l.startswith(p) for p in BORING_PREFIX): return True
        if len(l) < 8: return True
        return False

    def vibe_score(m: str) -> int:
        s = 0
        l = m.lower()
        if 12 <= len(m) <= 65:   s += 3
        elif 8  <= len(m) <= 80: s += 1
        if m == m.lower():        s += 2  # casual casing
        if any(c in m for c in "!?"): s += 2
        if "..." in m or "…" in m:    s += 1
        for w in (
            "finally", "why", "wtf", "idk", "todo", "hmm", "ok ", "lol", "wkwk",
            "??", "!!", "lupa", "coba", "nyoba", "tambahin", "benerin", "harusnya",
            "kayak", "masih", "udah", "belum", "sorry", "gak tau", "nggak",
            "waduh", "anjir", "aduh", "oops", "ugh", "dammit", "argh", "somehow",
            "broken", "cursed", "no idea", "help", "please", "works on my machine",
        ):
            if w in l: s += 4
        return s

    candidates = list({m.strip() for m in messages if not is_boring(m.strip())})
    best = sorted(candidates, key=vibe_score, reverse=True)[:7]

    if not best:
        best = [
            "no interesting commits found. kamu terlalu rapi.",
            "write chaotic commit messages. it builds character.",
        ]

    W      = 800
    LINE_H = 54
    H      = 90 + len(best) * LINE_H + 50

    lines = ""
    for i, msg in enumerate(best):
        y       = 85 + i * LINE_H
        display = msg if len(msg) <= 68 else msg[:65] + "…"
        bg_col  = SURFACE if i % 2 == 0 else BG

        lines += (
            f'  <rect x="30" y="{y - 6}" width="740" height="{LINE_H - 4}" fill="{bg_col}" rx="4"/>\n'
            f'  <text x="46" y="{y + 13}" font-family="{FONT}" font-size="10"'
            f' fill="{ACCENT}" opacity="0.65">#{i + 1:02d}</text>\n'
            f'  <text x="77" y="{y + 13}" font-family="{FONT}" font-size="12"'
            f' fill="{TEXT}">{esc(display)}</text>\n'
            f'  <text x="754" y="{y + 20}" font-family="{FONT}" font-size="24"'
            f' fill="{BORDER}" text-anchor="end" opacity="0.4">&quot;</text>\n'
        )

    footer_y = 85 + len(best) * LINE_H + 28

    return f'''\
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="{BG}" rx="12"/>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" fill="none" stroke="{BORDER}" stroke-width="1" rx="11"/>

  <text x="36" y="48" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="3">IN YOUR OWN WORDS</text>
  <text x="{W - 36}" y="48" font-family="{FONT}" font-size="11" fill="{DIM}"
        letter-spacing="2" text-anchor="end">RAW COMMIT MESSAGES</text>
  <rect x="36" y="58" width="230" height="1" fill="{PURPLE}" opacity="0.4"/>

{lines}
  <text x="400" y="{footer_y}" font-family="{FONT}" font-size="10" fill="{DIM}"
        text-anchor="middle" font-style="italic">honest logs from an honest coder.</text>
</svg>'''


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        print("ERROR: no token found. set GH_TOKEN or GITHUB_TOKEN.", file=sys.stderr)
        sys.exit(1)

    os.makedirs("assets", exist_ok=True)

    data = collect()
    print(f"  total commits in range: {data['total_commits']}", flush=True)

    chapters = [
        ("chapter1.svg", "The Numbers",         ch1),
        ("chapter2.svg", "The Grind",            ch2),
        ("chapter3.svg", "The Journey",          ch3),
        ("chapter4.svg", "In Your Own Words",    ch4),
    ]

    for fname, label, fn in chapters:
        print(f"→ generating {label} …", flush=True)
        svg = fn(data)
        path = os.path.join("assets", fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"  saved {path}", flush=True)

    print("✓ all chapters generated.", flush=True)


if __name__ == "__main__":
    main()
