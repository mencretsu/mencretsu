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
        if 0 <= h < 3:  return "late night. just you and the compiler"
        if 3 <= h < 6:  return "still awake at this hour?"
        if 6 <= h < 9:  return "coding first thing in the morning"
        if 9 <= h < 12: return "normal hours. suspicious"
        if 12 <= h < 14: return "coding through lunch"
        if 14 <= h < 17: return "afternoon grind"
        if 17 <= h < 20: return "opened the editor right after work"
        if 20 <= h < 22: return "nighttime. calm and focused"
        return "deep night. zero distractions"

    def _vibe(h: int) -> str:
        if 0 <= h < 6:  return "still coding this late."
        if 6 <= h < 12: return "clean workflow."
        if 12 <= h < 18: return "coding through work hours."
        return "night coding session."

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


# ─── Chapter 2 — The Grind (animated heatmap + radial clock) ─────────────────

def ch2(data: dict) -> str:
    cbd     = data["commits_by_date"]
    by_hour = data["commits_by_hour"]
    by_dow  = data["commits_by_dow"]
    total   = data["total_commits"]

    # Smaller cells so heatmap fits left of the clock
    CELL = 9
    GAP  = 2
    STEP = CELL + GAP
    LEFT = 44
    TOP  = 84
    W, H = 800, 228

    today     = datetime.now(timezone.utc).date()
    start_raw = today - timedelta(days=363)
    start     = start_raw - timedelta(days=(start_raw.isoweekday() % 7))

    total_days  = (today - start).days + 1
    total_weeks = min(math.ceil(total_days / 7), 52)

    max_day = max(cbd.values(), default=1)

    # Blue palette instead of boring GitHub green
    def cell_color(n: int) -> str:
        if n == 0: return "#0d1117"
        r = n / max_day
        if r < 0.20: return "#0c2d6b"
        if r < 0.45: return "#1050bb"
        if r < 0.75: return "#2470e8"
        return ACCENT

    cells      = ""
    month_seen: dict[str, int] = {}

    for week in range(total_weeks):
        delay = round(week * 0.017, 3)
        for dow in range(7):
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
            is_hot = count >= max_day * 0.75 and count > 0

            if is_hot:
                # Reveal then pulse continuously
                cells += (
                    f'  <rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" '
                    f'fill="{col}" rx="2" opacity="0" filter="url(#glow2)">\n'
                    f'    <animate attributeName="opacity" values="0;1" dur="0.35s" '
                    f'begin="{delay}s" fill="freeze"/>\n'
                    f'    <animate attributeName="opacity" values="1;0.45;1" dur="2s" '
                    f'begin="{round(delay+0.35,3)}s" repeatCount="indefinite"/>\n'
                    f'  </rect>\n'
                )
            else:
                cells += (
                    f'  <rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" '
                    f'fill="{col}" rx="2" opacity="0">\n'
                    f'    <animate attributeName="opacity" values="0;1" dur="0.35s" '
                    f'begin="{delay}s" fill="freeze"/>\n'
                    f'  </rect>\n'
                )

    month_labels = ""
    for mk, week in sorted(month_seen.items())[:13]:
        abbr = datetime.strptime(mk, "%Y-%m").strftime("%b")
        x    = LEFT + week * STEP
        month_labels += (
            f'  <text x="{x}" y="{TOP - 10}" font-family="{FONT}" '
            f'font-size="9" fill="{DIM}">{abbr}</text>\n'
        )

    day_labels = ""
    for di, dname in enumerate(["", "Mon", "", "Wed", "", "Fri", ""]):
        if dname:
            y = TOP + di * STEP + CELL
            day_labels += (
                f'  <text x="{LEFT - 6}" y="{y}" font-family="{FONT}" '
                f'font-size="9" fill="{DIM}" text-anchor="end">{dname}</text>\n'
            )

    # ── Radial 24h clock ──────────────────────────────────────────────────────
    fav_hour    = max(by_hour, key=by_hour.get) if by_hour else 0
    max_h_count = max(by_hour.values(), default=1)
    CX, CY, BASE_R = 716, 136, 44

    def _hlabel(h: int) -> str:
        if h == 0:  return "12 AM"
        if h < 12:  return f"{h} AM"
        if h == 12: return "12 PM"
        return f"{h - 12} PM"

    clock_parts = ""
    # Outer ring
    clock_parts += (
        f'  <circle cx="{CX}" cy="{CY}" r="{BASE_R + 3}" fill="none" '
        f'stroke="{BORDER}" stroke-width="1"/>\n'
    )

    for h in range(24):
        count = by_hour.get(h, 0)
        angle = (h / 24) * 2 * math.pi - math.pi / 2
        bar_len = 5 + int((count / max_h_count) * 26) if count > 0 else 2
        x1 = CX + math.cos(angle) * (BASE_R + 5)
        y1 = CY + math.sin(angle) * (BASE_R + 5)
        x2 = CX + math.cos(angle) * (BASE_R + 5 + bar_len)
        y2 = CY + math.sin(angle) * (BASE_R + 5 + bar_len)
        is_peak = (h == fav_hour)
        col = ACCENT if is_peak else ("#1a4fbb" if count > 0 else BORDER)
        sw  = 4 if is_peak else (2 if count > 0 else 1)

        if is_peak:
            clock_parts += (
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{col}" stroke-width="{sw}" stroke-linecap="round" '
                f'filter="url(#glow2)">\n'
                f'    <animate attributeName="stroke-opacity" values="1;0.45;1" '
                f'dur="1.6s" repeatCount="indefinite"/>\n'
                f'  </line>\n'
            )
        else:
            clock_parts += (
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{col}" stroke-width="{sw}" stroke-linecap="round"/>\n'
            )

    # Cardinal labels: 12a top, 6a right, 12p bottom, 6p left
    for h, label in [(0, "12a"), (6, "6a"), (12, "12p"), (18, "6p")]:
        angle = (h / 24) * 2 * math.pi - math.pi / 2
        lx = CX + math.cos(angle) * (BASE_R + 38)
        ly = CY + math.sin(angle) * (BASE_R + 38)
        clock_parts += (
            f'  <text x="{lx:.1f}" y="{ly:.1f}" font-family="{FONT}" font-size="8" '
            f'fill="{DIM}" text-anchor="middle" dominant-baseline="middle">{label}</text>\n'
        )

    # Center: peak hour
    clock_parts += (
        f'  <text x="{CX}" y="{CY - 7}" font-family="{FONT}" font-size="15" '
        f'font-weight="700" fill="{ACCENT}" text-anchor="middle">{_hlabel(fav_hour)}</text>\n'
        f'  <text x="{CX}" y="{CY + 8}" font-family="{FONT}" font-size="7.5" '
        f'fill="{DIM}" text-anchor="middle" letter-spacing="1.5">PEAK HOUR</text>\n'
    )

    # ── Bottom tagline ────────────────────────────────────────────────────────
    night     = sum(v for k, v in by_hour.items() if k >= 22 or k < 6)
    weekend   = sum(v for k, v in by_dow.items()  if k >= 5)
    night_p   = round(night   / total * 100) if total else 0
    weekend_p = round(weekend / total * 100) if total else 0

    if night_p > 50:
        tagline = f"{night_p}% of commits happen at night. consistent schedule."
    elif weekend_p > 40:
        tagline = f"{weekend_p}% of commits happen on weekends."
    else:
        tagline = f"{night_p}% night commits  ·  {weekend_p}% weekend commits"

    stats_y = TOP + 7 * STEP + 20

    return f'''\
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="glow2">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}" rx="12"/>
  <rect x="1" y="1" width="{W-2}" height="{H-2}" fill="none" stroke="{BORDER}" stroke-width="1" rx="11"/>

  <text x="36" y="42" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="3">THE GRIND</text>
  <text x="{W-36}" y="42" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="2" text-anchor="end">365 DAYS</text>
  <rect x="36" y="52" width="110" height="1" fill="{ACCENT}" opacity="0.4"/>

  <!-- vertical divider between heatmap and clock -->
  <line x1="632" y1="64" x2="632" y2="{H-28}" stroke="{BORDER}" stroke-width="1" opacity="0.5"/>

  <!-- clock section label -->
  <text x="642" y="78" font-family="{FONT}" font-size="9" fill="{DIM}" letter-spacing="2">24H ACTIVITY</text>

{month_labels}
{day_labels}
{cells}
{clock_parts}
  <text x="{LEFT}" y="{stats_y}" font-family="{FONT}" font-size="10" fill="{DIM}">{esc(tagline)}</text>
</svg>'''


# ─── Chapter 3 — The Journey (animated timeline) ─────────────────────────────

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
        cnt    = rcounts.get(r["name"], 0)
        stars  = r.get("stargazers_count", 0)
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

    n       = len(timeline)
    ROW_H   = 78
    W       = 800
    H       = max(100 + n * ROW_H + 60, 300)
    LINE_X  = 132
    BAR_MAX = 220   # max px width for commit bar

    max_commits = max((rcounts.get(r["name"], 0) for r in timeline), default=1)

    tl_s   = 88
    tl_e   = 88 + n * ROW_H - 24
    tl_len = tl_e - tl_s
    # total draw duration for the line = sum of per-item delays + a little
    line_dur = round(0.1 + n * 0.13 + 0.3, 2)

    rows = ""
    for i, repo in enumerate(timeline):
        y         = 88 + i * ROW_H
        delay     = round(i * 0.13, 3)
        bar_delay = round(delay + 0.18, 3)
        pulse_beg = round(delay + 0.45, 3)

        try:
            dt       = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
            mon_str  = dt.strftime("%b")
            year_str = dt.strftime("%Y")
        except (ValueError, KeyError):
            mon_str = year_str = "—"

        cnt   = rcounts.get(repo["name"], 0)
        lang  = repo.get("language") or "—"
        lcol  = LANG_COLORS.get(lang, DIM)
        desc  = (repo.get("description") or "no description.").strip()
        if len(desc) > 60:
            desc = desc[:57] + "…"
        stars = repo.get("stargazers_count", 0)
        bar_w = max(4, int((cnt / max_commits) * BAR_MAX))

        rows += f'''\
  <!-- {esc(repo["name"])} -->
  <g opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.4s"
             begin="{delay}s" fill="freeze"/>

    <!-- pulsing outer dot -->
    <circle cx="{LINE_X}" cy="{y + 10}" r="7" fill="{ACCENT}" opacity="0.14">
      <animate attributeName="r"       values="7;12;7"         dur="2.4s" begin="{pulse_beg}s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.14;0.03;0.14" dur="2.4s" begin="{pulse_beg}s" repeatCount="indefinite"/>
    </circle>
    <!-- solid inner dot -->
    <circle cx="{LINE_X}" cy="{y + 10}" r="3.5" fill="{ACCENT}"/>

    <!-- date stamp -->
    <text x="{LINE_X - 12}" y="{y + 9}"  font-family="{FONT}" font-size="9"
          fill="{DIM}" text-anchor="end">{esc(mon_str)}</text>
    <text x="{LINE_X - 12}" y="{y + 21}" font-family="{FONT}" font-size="9"
          fill="{DIM}" text-anchor="end">{esc(year_str)}</text>

    <!-- repo name + desc -->
    <text x="{LINE_X + 20}" y="{y + 16}" font-family="{FONT}" font-size="14"
          font-weight="700" fill="{TEXT}">{esc(repo["name"])}</text>
    <text x="{LINE_X + 20}" y="{y + 32}" font-family="{FONT}" font-size="10"
          fill="{DIM}">{esc(desc)}</text>

    <!-- commit bar track -->
    <rect x="{LINE_X + 20}" y="{y + 46}" width="{BAR_MAX}" height="3"
          fill="{BORDER}" rx="1.5"/>
    <!-- commit bar fill — animates in -->
    <rect x="{LINE_X + 20}" y="{y + 46}" width="0" height="3"
          fill="{ACCENT}" rx="1.5">
      <animate attributeName="width" from="0" to="{bar_w}" dur="0.65s"
               begin="{bar_delay}s" fill="freeze"
               calcMode="spline" keySplines="0.22 1 0.36 1" keyTimes="0;1"/>
    </rect>

    <!-- meta row -->
    <text x="{LINE_X + 20}" y="{y + 65}" font-family="{FONT}" font-size="9"
          fill="{ACCENT}">{cnt} commits</text>
    <circle cx="{LINE_X + 98}" cy="{y + 61}" r="4" fill="{lcol}"/>
    <text x="{LINE_X + 106}" y="{y + 65}" font-family="{FONT}" font-size="9"
          fill="{DIM}">{esc(lang)}</text>
'''
        if stars:
            rows += (
                f'    <text x="{LINE_X + 165}" y="{y + 65}" font-family="{FONT}" '
                f'font-size="9" fill="{ORANGE}">★ {stars}</text>\n'
            )
        if i < n - 1:
            rows += (
                f'    <line x1="{LINE_X + 20}" y1="{y + 72}" x2="764" y2="{y + 72}" '
                f'stroke="{BORDER}" stroke-width="1" opacity="0.28"/>\n'
            )
        rows += '  </g>\n\n'

    return f'''\
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="tlg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%"   style="stop-color:{ACCENT};stop-opacity:0.8"/>
      <stop offset="100%" style="stop-color:{ACCENT};stop-opacity:0.03"/>
    </linearGradient>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}" rx="12"/>
  <rect x="1" y="1" width="{W-2}" height="{H-2}" fill="none" stroke="{BORDER}" stroke-width="1" rx="11"/>

  <text x="36" y="48" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="3">THE JOURNEY</text>
  <text x="{W-36}" y="48" font-family="{FONT}" font-size="11" fill="{DIM}"
        letter-spacing="2" text-anchor="end">{n} PROJECTS</text>
  <rect x="36" y="58" width="145" height="1" fill="{ACCENT}" opacity="0.4"/>

  <!-- timeline line draws top-to-bottom -->
  <line x1="{LINE_X}" y1="{tl_s}" x2="{LINE_X}" y2="{tl_e}"
        stroke="url(#tlg)" stroke-width="1"
        stroke-dasharray="{tl_len}" stroke-dashoffset="{tl_len}">
    <animate attributeName="stroke-dashoffset" from="{tl_len}" to="0"
             dur="{line_dur}s" begin="0s" fill="freeze"
             calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </line>

{rows}
</svg>'''


# ─── Chapter 4 — In Your Own Words (cycling quote carousel) ──────────────────

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
        if m == m.lower():        s += 2
        if any(c in m for c in "!?"): s += 2
        if "..." in m or "…" in m:    s += 1
        for w in (
            "finally", "why", "wtf", "idk", "todo", "hmm", "ok ", "lol", "wkwk",
            "??", "!!", "oops", "ugh", "dammit", "argh", "somehow",
            "broken", "cursed", "no idea", "help", "please", "works on my machine",
        ):
            if w in l: s += 4
        return s

    candidates = list({m.strip() for m in messages if not is_boring(m.strip())})
    best = sorted(candidates, key=vibe_score, reverse=True)[:7]

    if not best:
        best = [
            "no interesting commits found.",
            "write chaotic commit messages. it builds character.",
            "commit -m 'fix stuff' doesn't count.",
        ]

    W, H   = 800, 195
    N      = len(best)
    SHOW   = 3.2          # seconds each message is displayed
    FADE   = 0.38         # fade in/out duration
    TOTAL  = round(N * SHOW, 3)

    DOT_R   = 3
    DOT_GAP = 16
    DOTS_X  = W // 2 - ((N - 1) * DOT_GAP) // 2
    DOTS_Y  = H - 22

    msg_svgs  = ""
    dot_parts = ""

    for i, msg in enumerate(best):
        display = msg if len(msg) <= 60 else msg[:57] + "…"

        t0 = 0.0
        t1 = round((i * SHOW)              / TOTAL, 4)
        t2 = round((i * SHOW + FADE)       / TOTAL, 4)
        t3 = round(((i + 1) * SHOW - FADE) / TOTAL, 4)
        t4 = round(((i + 1) * SHOW)        / TOTAL, 4)
        t5 = 1.0
        t2 = min(t2, t3)
        t4 = min(t4, t5)

        kt = f"{t0};{t1};{t2};{t3};{t4};{t5}"

        msg_svgs += (
            f'  <text x="{W//2}" y="110" font-family="{FONT}" font-size="15"'
            f' font-weight="600" fill="{TEXT}" text-anchor="middle" opacity="0">\n'
            f'    {esc(display)}\n'
            f'    <animate attributeName="opacity" values="0;0;1;1;0;0"\n'
            f'             keyTimes="{kt}" dur="{TOTAL}s" repeatCount="indefinite"/>\n'
            f'  </text>\n\n'
        )

        counter = f"{i+1:02d} / {N:02d}"
        msg_svgs += (
            f'  <text x="{W//2}" y="136" font-family="{FONT}" font-size="9"'
            f' fill="{DIM}" text-anchor="middle" letter-spacing="2" opacity="0">\n'
            f'    {counter}\n'
            f'    <animate attributeName="opacity" values="0;0;0.5;0.5;0;0"\n'
            f'             keyTimes="{kt}" dur="{TOTAL}s" repeatCount="indefinite"/>\n'
            f'  </text>\n\n'
        )

        dx = DOTS_X + i * DOT_GAP
        dot_parts += (
            f'  <circle cx="{dx}" cy="{DOTS_Y}" r="{DOT_R}" fill="{BORDER}">\n'
            f'    <animate attributeName="fill"\n'
            f'             values="{BORDER};{BORDER};{ACCENT};{ACCENT};{BORDER};{BORDER}"\n'
            f'             keyTimes="{kt}" dur="{TOTAL}s" repeatCount="indefinite"/>\n'
            f'    <animate attributeName="r"\n'
            f'             values="{DOT_R};{DOT_R};{DOT_R+2};{DOT_R+2};{DOT_R};{DOT_R}"\n'
            f'             keyTimes="{kt}" dur="{TOTAL}s" repeatCount="indefinite"/>\n'
            f'  </circle>\n'
        )

    return f'''\
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="{BG}" rx="12"/>
  <rect x="1" y="1" width="{W-2}" height="{H-2}" fill="none" stroke="{BORDER}" stroke-width="1" rx="11"/>

  <text x="36" y="48" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="3">IN YOUR OWN WORDS</text>
  <text x="{W-36}" y="48" font-family="{FONT}" font-size="11" fill="{DIM}"
        letter-spacing="2" text-anchor="end">RAW COMMIT LOG</text>
  <rect x="36" y="58" width="230" height="1" fill="{PURPLE}" opacity="0.4"/>

  <!-- decorative quote marks -->
  <text x="58" y="128" font-family="Georgia,serif" font-size="80"
        fill="{BORDER}" opacity="0.28">&ldquo;</text>
  <text x="{W-58}" y="134" font-family="Georgia,serif" font-size="80"
        fill="{BORDER}" opacity="0.28" text-anchor="end">&rdquo;</text>

{msg_svgs}
{dot_parts}
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
