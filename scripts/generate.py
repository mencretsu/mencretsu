import math
import os
import sys
import time
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

USERNAME = "mencretsu"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Accent colors stay hardcoded — these are semantic and must be visible in both modes
ACCENT  = "#388bfd"
GREEN   = "#3fb950"
ORANGE  = "#f0883e"
PURPLE  = "#a371f7"
RED     = "#f85149"
FONT    = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"

# Shared CSS injected into every SVG
# Default = dark (GitHub dark mode), light override via media query
SVG_STYLE = """<style>
  text       { font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace; }
  .t-primary { fill: #e6edf3; }
  .t-dim     { fill: #8b949e; }
  .sep       { stroke: #30363d; fill: none; }
  .bg-card   { fill: #161b22; }
  @media (prefers-color-scheme: light) {
    .t-primary { fill: #1f2328; }
    .t-dim     { fill: #656d76; }
    .sep       { stroke: #d0d7de; fill: none; }
    .bg-card   { fill: #f6f8fa; }
  }
</style>"""


def esc(s):
    return (s.replace("&","&amp;").replace("<","&lt;")
             .replace(">","&gt;").replace('"',"&quot;"))


def get(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        except requests.RequestException as e:
            print(f"    request error: {e}", flush=True)
            time.sleep(5*(attempt+1))
            continue
        if r.status_code == 403:
            if r.headers.get("X-RateLimit-Remaining") == "0":
                reset_ts = int(r.headers.get("X-RateLimit-Reset", time.time()+60))
                wait = max(reset_ts - time.time(), 0) + 5
                print(f"    rate limit — sleeping {wait:.0f}s …", flush=True)
                time.sleep(wait)
                continue
        if r.status_code in (404, 409): return []
        if r.status_code == 200: return r.json()
        print(f"    HTTP {r.status_code} for {url}", flush=True)
        return []
    return []


def get_pages(url, params=None, max_pages=5):
    params = params or {}
    out = []
    for page in range(1, max_pages+1):
        chunk = get(url, {**params, "per_page": 100, "page": page})
        if not isinstance(chunk, list) or not chunk: break
        out.extend(chunk)
        if len(chunk) < 100: break
    return out


def collect():
    print("→ fetching repos …", flush=True)
    repos = get_pages("https://api.github.com/user/repos",
                      {"type":"owner","sort":"pushed"}, max_pages=10)
    own = [r for r in repos if not r.get("fork")]
    print(f"  {len(own)} own repos found", flush=True)

    since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    commits_by_date    = defaultdict(int)
    commits_by_hour    = defaultdict(int)
    commits_by_dow     = defaultdict(int)
    commit_messages    = []
    repo_commit_counts = {}

    for i, repo in enumerate(own):
        name = repo["name"]
        print(f"  [{i+1}/{len(own)}] {name}", flush=True)
        raw = get_pages(
            f"https://api.github.com/repos/{USERNAME}/{name}/commits",
            {"author": USERNAME, "since": since}, max_pages=3)
        count = 0
        for c in raw:
            author   = c.get("commit", {}).get("author", {})
            date_str = author.get("date", "")
            if not date_str: continue
            try:
                dt = datetime.fromisoformat(date_str.replace("Z","+00:00"))
            except ValueError:
                continue
            commits_by_date[dt.strftime("%Y-%m-%d")] += 1
            commits_by_hour[dt.hour] += 1
            commits_by_dow[dt.weekday()] += 1
            msg = c.get("commit",{}).get("message","").split("\n")[0].strip()
            if msg: commit_messages.append(msg)
            count += 1
        repo_commit_counts[name] = count

    return {
        "repos": own,
        "commits_by_date": dict(commits_by_date),
        "commits_by_hour": dict(commits_by_hour),
        "commits_by_dow":  dict(commits_by_dow),
        "commit_messages": commit_messages,
        "repo_commit_counts": repo_commit_counts,
        "total_commits": sum(commits_by_date.values()),
    }


# ─── Chapter 1 — The Numbers ──────────────────────────────────────────────────
def ch1(data):
    total   = data["total_commits"]
    by_hour = data["commits_by_hour"]
    by_dow  = data["commits_by_dow"]

    fav_hour = max(by_hour, key=by_hour.get) if by_hour else 2
    fav_dow  = max(by_dow,  key=by_dow.get)  if by_dow  else 6
    DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    night   = sum(v for k,v in by_hour.items() if k>=22 or k<6)
    night_p = round(night/total*100) if total else 0
    weekend = sum(v for k,v in by_dow.items() if k>=5)
    wknd_p  = round(weekend/total*100) if total else 0

    def _hlabel(h):
        if h == 0:  return "12 AM"
        if h < 12:  return f"{h} AM"
        if h == 12: return "12 PM"
        return f"{h-12} PM"

    def _hvibe(h):
        if 0<=h<3:   return "late night. just you and the compiler"
        if 3<=h<6:   return "still awake at this hour?"
        if 6<=h<9:   return "coding first thing in the morning"
        if 9<=h<12:  return "normal hours. suspicious"
        if 12<=h<14: return "coding through lunch"
        if 14<=h<17: return "afternoon grind"
        if 17<=h<20: return "opened the editor right after work"
        if 20<=h<22: return "nighttime. calm and focused"
        return "deep night. zero distractions"

    def _vibe(h):
        if 0<=h<6:   return "still coding this late."
        if 6<=h<12:  return "clean workflow."
        if 12<=h<18: return "coding through work hours."
        return "night coding session."

    total_str = f"{total:,}"
    hour_str  = _hlabel(fav_hour)
    day_str   = DAYS[fav_dow]

    # ── hourly bar chart ──────────────────────────────────────────────────────
    BAR_W, BAR_GAP = 24, 6
    BAR_STEP = BAR_W + BAR_GAP
    BAR_MAX  = 52
    BAR_Y    = 378   # baseline y
    GRID_X   = (800 - (24*BAR_STEP - BAR_GAP)) // 2
    max_h    = max(by_hour.values(), default=1)

    bars = ""
    for h in range(24):
        cnt = by_hour.get(h, 0)
        bh  = max(int((cnt/max_h)*BAR_MAX), 1 if cnt>0 else 0)
        x   = GRID_X + h*BAR_STEP
        is_peak = (h == fav_hour)
        col = ACCENT
        opa = "1" if is_peak else "0.3"
        if bh:
            bars += (
                f'<rect x="{x}" y="{BAR_Y - bh}" '
                f'width="{BAR_W}" height="{bh}" fill="{col}" rx="3" opacity="{opa}"/>\n'
            )
        if is_peak:
            bars += (
                f'<text x="{x + BAR_W//2}" y="{BAR_Y - bh - 6}" '
                f'class="t-dim" font-size="9" text-anchor="middle" letter-spacing="1">PEAK</text>\n'
            )

    for h in [0, 6, 12, 18, 23]:
        lx = GRID_X + h*BAR_STEP + BAR_W//2
        bars += (
            f'<text x="{lx}" y="{BAR_Y + 16}" '
            f'class="t-dim" font-size="10" text-anchor="middle">{h:02d}</text>\n'
        )

    return f'''\
<svg width="800" height="460" viewBox="0 0 800 460" xmlns="http://www.w3.org/2000/svg">
  {SVG_STYLE}
  <defs>
    <linearGradient id="hdrg" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <!-- header -->
  <text x="36" y="46" class="t-dim" font-size="11" letter-spacing="3">THE NUMBERS</text>
  <text x="764" y="46" class="t-dim" font-size="11" letter-spacing="2" text-anchor="end">LAST 365 DAYS</text>
  <rect x="36" y="54" width="220" height="1" fill="url(#hdrg)"/>

  <!-- ── row 1: 3 stat cards ─────────────────────────────────────────── -->
  <!-- COMMITS -->
  <rect x="36" y="68" width="224" height="106" rx="8" class="bg-card"/>
  <text x="148" y="130" class="t-primary" font-size="52" font-weight="700"
        text-anchor="middle">{esc(total_str)}</text>
  <text x="148" y="150" class="t-dim" font-size="9" text-anchor="middle"
        letter-spacing="3">COMMITS</text>

  <!-- PEAK HOUR -->
  <rect x="270" y="68" width="260" height="106" rx="8" class="bg-card"/>
  <text x="400" y="122" fill="{ACCENT}" font-size="38" font-weight="700"
        text-anchor="middle">{esc(hour_str)}</text>
  <text x="400" y="143" class="t-dim" font-size="9" text-anchor="middle"
        letter-spacing="3">PEAK HOUR</text>
  <text x="400" y="160" fill="{PURPLE}" font-size="10" text-anchor="middle"
        >— {esc(_hvibe(fav_hour))} —</text>

  <!-- MOST ACTIVE DAY -->
  <rect x="540" y="68" width="224" height="106" rx="8" class="bg-card"/>
  <text x="652" y="120" fill="{ORANGE}" font-size="22" font-weight="700"
        text-anchor="middle">{esc(day_str)}</text>
  <text x="652" y="143" class="t-dim" font-size="9" text-anchor="middle"
        letter-spacing="2">MOST ACTIVE</text>

  <!-- vibe quote -->
  <text x="400" y="204" class="t-dim" font-size="13" text-anchor="middle"
        font-style="italic">&quot;{esc(_vibe(fav_hour))}&quot;</text>

  <!-- ── separator ───────────────────────────────────────────────────── -->
  <line x1="36" y1="216" x2="764" y2="216" class="sep" stroke-width="1"/>

  <!-- ── row 2: night% + weekend% cards ─────────────────────────────── -->
  <rect x="36" y="224" width="352" height="78" rx="8" class="bg-card"/>
  <text x="212" y="270" fill="{GREEN}" font-size="34" font-weight="700"
        text-anchor="middle">{night_p}%</text>
  <text x="212" y="289" class="t-dim" font-size="10" text-anchor="middle"
        letter-spacing="2">NIGHT COMMITS</text>

  <rect x="400" y="224" width="364" height="78" rx="8" class="bg-card"/>
  <text x="582" y="270" fill="{ORANGE}" font-size="34" font-weight="700"
        text-anchor="middle">{wknd_p}%</text>
  <text x="582" y="289" class="t-dim" font-size="10" text-anchor="middle"
        letter-spacing="2">WEEKEND COMMITS</text>

  <!-- ── hourly bar chart ─────────────────────────────────────────────── -->
  <line x1="36" y1="316" x2="764" y2="316" class="sep" stroke-width="1"/>
  <text x="36" y="334" class="t-dim" font-size="9" letter-spacing="2">HOURLY ACTIVITY</text>
  <line x1="36" y1="340" x2="764" y2="340" class="sep" stroke-width="1" opacity="0.4"/>
{bars}
</svg>'''


# ─── Chapter 2 — The Grind ────────────────────────────────────────────────────
def ch2(data):
    cbd                = data["commits_by_date"]
    total              = data["total_commits"]
    repo_commit_counts = data["repo_commit_counts"]

    W, H = 800, 560

    today     = datetime.now(timezone.utc).date()
    start_raw = today - timedelta(days=363)
    start     = start_raw - timedelta(days=(start_raw.isoweekday() % 7))

    # ── Build weeks with honest open/close ───────────────────────────────
    # open  = avg commits/week of ALL previous active weeks
    # close = total commits this week
    # green = this week >= avg so far, red = below avg
    running_totals = []
    weeks = []
    for w in range(52):
        week_days   = [start + timedelta(days=w*7+d) for d in range(7)]
        week_counts = [cbd.get(d.strftime("%Y-%m-%d"), 0) for d in week_days]
        total_w     = sum(week_counts)

        last4 = running_totals[-4:] if running_totals else []
        avg_prev = sum(last4) / len(last4) if last4 else 0.0

        weeks.append({
            "total":    total_w,
            "open":     avg_prev,
            "close":    float(total_w),
            "date":     week_days[0],
            "days":     week_days,
            "counts":   week_counts,
        })
        if total_w > 0:
            running_totals.append(total_w)

    # ── Streak calculation ────────────────────────────────────────────────
    all_dates = sorted(cbd.keys())
    current_streak = 0
    longest_streak = 0
    streak = 0
    d = today
    while cbd.get(d.strftime("%Y-%m-%d"), 0) > 0:
        current_streak += 1
        d -= timedelta(days=1)

    streak = 0
    if all_dates:
        prev = datetime.strptime(all_dates[0], "%Y-%m-%d").date()
        streak = 1
        for ds in all_dates[1:]:
            cur = datetime.strptime(ds, "%Y-%m-%d").date()
            if (cur - prev).days == 1:
                streak += 1
                longest_streak = max(longest_streak, streak)
            else:
                streak = 1
            prev = cur
        longest_streak = max(longest_streak, streak)

    active_weeks = sum(1 for w in weeks if w["total"] > 0)
    avg_per_week = round(total / max(active_weeks, 1), 1)

    active_weeks_list = [w for w in weeks if w["total"] > 0]
    active_week = max(weeks, key=lambda w: w["total"])
    lazy_week   = min(active_weeks_list, key=lambda w: w["total"]) if active_weeks_list else active_week

    def week_label(w):
        d = w["date"]
        return f"week {(d.day-1)//7+1} of {d.strftime('%b')}"

    # ── Top repos (max 5) ─────────────────────────────────────────────────
    top_repos = sorted(
        [(k, v) for k, v in repo_commit_counts.items() if v > 0],
        key=lambda x: x[1], reverse=True
    )[:5]
    max_repo_count = top_repos[0][1] if top_repos else 1

    # ── Candle chart geometry ─────────────────────────────────────────────
    CL_X1, CL_X2       = 56, 764
    CL_Y_TOP, CL_Y_BOT = 180, 330
    CL_H                = CL_Y_BOT - CL_Y_TOP

    max_val = max((max(w["open"], w["close"]) for w in weeks if w["total"] > 0), default=1)

    def to_y(v):
        if v <= 0: return CL_Y_BOT
        log_v   = math.log1p(v)
        log_max = math.log1p(max_val)
        return CL_Y_BOT - int((log_v / log_max) * CL_H)

    cw_full = (CL_X2 - CL_X1) / len(weeks)
    cw_body = max(cw_full * 0.62, 3)
    cw_gap  = cw_full - cw_body

    # avg reference line
    avg_y = to_y(avg_per_week)

    candles_svg = ""
    for i, wk in enumerate(weeks):
        cx    = CL_X1 + i * cw_full + cw_gap / 2
        delay = round(i * 0.018, 3)

        if wk["total"] == 0:
            doji_y = to_y(wk["open"])
            candles_svg += (
                f'<line x1="{cx:.1f}" y1="{doji_y}" '
                f'x2="{cx+cw_body:.1f}" y2="{doji_y}" '
                f'stroke="#30363d" stroke-width="1.5" '
                f'stroke-linecap="round" opacity="0.4"/>\n'
            )
            continue

        o = wk["open"]
        c = wk["close"]
        is_up    = c >= o
        col      = GREEN if is_up else RED
        open_y   = to_y(o)
        close_y  = to_y(c)
        body_top = min(open_y, close_y)
        body_bot = max(open_y, close_y)
        body_h   = max(body_bot - body_top, 2)
        mid_y    = (body_top + body_bot) // 2

        candles_svg += (
            f'<rect x="{cx:.1f}" y="{mid_y}" width="{cw_body:.1f}" height="0" '
            f'fill="{col}" rx="1" opacity="0.85">'
            f'<animate attributeName="y" from="{mid_y}" to="{body_top}" '
            f'dur="0.28s" begin="{delay}s" fill="freeze" '
            f'calcMode="spline" keySplines="0.22 1 0.36 1" keyTimes="0;1"/>'
            f'<animate attributeName="height" from="0" to="{body_h}" '
            f'dur="0.28s" begin="{delay}s" fill="freeze" '
            f'calcMode="spline" keySplines="0.22 1 0.36 1" keyTimes="0;1"/>'
            f'</rect>\n'
        )

    # month labels
    month_labels = ""
    prev_month   = None
    for i, wk in enumerate(weeks):
        if wk["date"].month != prev_month:
            x    = CL_X1 + i * cw_full + cw_body / 2
            abbr = wk["date"].strftime("%b")
            month_labels += (
                f'<text x="{x:.1f}" y="{CL_Y_BOT+15}" class="t-dim" '
                f'font-size="10" text-anchor="middle">{abbr}</text>\n'
            )
            prev_month = wk["date"].month

    # y-axis grid lines (right side, inside chart)
    grid_lines = ""
    for pct in [0.25, 0.5, 0.75, 1.0]:
        gy  = CL_Y_BOT - int(pct * CL_H)
        val = int(pct * max_val)
        grid_lines += (
            f'<line x1="{CL_X1}" y1="{gy}" x2="{CL_X2}" y2="{gy}" '
            f'stroke="#21262d" stroke-width="1" opacity="0.4"/>\n'
            f'<text x="{CL_X1-4}" y="{gy+4}" class="t-dim" font-size="10" '
            f'text-anchor="end">{val}</text>\n'
        )

    # ── Top repos bars ────────────────────────────────────────────────────
    REPO_Y0    = 408
    REPO_BAR_H = 13
    REPO_STEP  = 24
    REPO_X0    = 200   # label column ends, bar starts
    REPO_X1    = 740   # bar max right edge
    REPO_BAR_W = REPO_X1 - REPO_X0

    repos_svg = ""
    for idx, (rname, rcount) in enumerate(top_repos):
        ry      = REPO_Y0 + idx * REPO_STEP
        bar_w   = int((rcount / max_repo_count) * REPO_BAR_W)
        name_tr = esc(rname[:22] + "…" if len(rname) > 22 else rname)
        repos_svg += (
            f'<text x="36" y="{ry+10}" class="t-primary" font-size="11">{name_tr}</text>\n'
            f'<rect x="{REPO_X0}" y="{ry}" width="{REPO_BAR_W}" height="{REPO_BAR_H}" '
            f'rx="3" fill="{ACCENT}" opacity="0.1"/>\n'
            f'<rect x="{REPO_X0}" y="{ry}" width="{bar_w}" height="{REPO_BAR_H}" '
            f'rx="3" fill="{ACCENT}" opacity="0.7"/>\n'
            f'<text x="{REPO_X1+8}" y="{ry+10}" class="t-dim" font-size="11">{rcount}</text>\n'
        )

    LG_Y = CL_Y_BOT + 30

    return f'''\
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  {SVG_STYLE}
  <defs>
    <linearGradient id="hdrg2" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <!-- ── HEADER ──────────────────────────────────────────────────────── -->
  <text x="36" y="44" class="t-dim" font-size="11" letter-spacing="3">THE GRIND</text>
  <text x="{W-36}" y="44" class="t-dim" font-size="11" letter-spacing="2"
        text-anchor="end">52 WEEKS</text>
  <rect x="36" y="52" width="110" height="1" fill="url(#hdrg2)"/>

  <!-- ── ROW 1: 4 stat mini-cards ────────────────────────────────────── -->
  <rect x="36"  y="62" width="168" height="72" rx="8" class="bg-card"/>
  <text x="120" y="98"  fill="{ACCENT}"  font-size="30" font-weight="700" text-anchor="middle">{avg_per_week}</text>
  <text x="120" y="118" class="t-dim" font-size="9" text-anchor="middle" letter-spacing="2">AVG / WEEK</text>

  <rect x="214" y="62" width="168" height="72" rx="8" class="bg-card"/>
  <text x="298" y="98"  fill="{GREEN}"  font-size="30" font-weight="700" text-anchor="middle">{current_streak}d</text>
  <text x="298" y="118" class="t-dim" font-size="9" text-anchor="middle" letter-spacing="2">CURRENT STREAK</text>

  <rect x="392" y="62" width="168" height="72" rx="8" class="bg-card"/>
  <text x="476" y="98"  fill="{ORANGE}" font-size="30" font-weight="700" text-anchor="middle">{longest_streak}d</text>
  <text x="476" y="118" class="t-dim" font-size="9" text-anchor="middle" letter-spacing="2">LONGEST STREAK</text>

  <rect x="570" y="62" width="194" height="72" rx="8" class="bg-card"/>
  <text x="667" y="98"  fill="{PURPLE}" font-size="30" font-weight="700" text-anchor="middle">{active_weeks}/52</text>
  <text x="667" y="118" class="t-dim" font-size="9" text-anchor="middle" letter-spacing="2">ACTIVE WEEKS</text>

  <!-- ── CANDLE CHART ─────────────────────────────────────────────────── -->
  <line x1="36" y1="148" x2="764" y2="148" class="sep" stroke-width="1"/>
  <text x="36" y="164" class="t-dim" font-size="9" letter-spacing="2">WEEKLY COMMITS</text>
  <text x="764" y="164" class="t-dim" font-size="9" text-anchor="end" letter-spacing="1">green = above avg · red = below</text>

  <!-- avg baseline -->
  <line x1="{CL_X1}" y1="{avg_y}" x2="{CL_X2}" y2="{avg_y}"
        stroke="{ACCENT}" stroke-width="1" stroke-dasharray="3 4" opacity="0.8"/>
  <text x="{CL_X1-4}" y="{avg_y+4}" fill="{ACCENT}" font-size="9"
        text-anchor="end" opacity="0.9">avg</text>

  <line x1="{CL_X1}" y1="{CL_Y_BOT}" x2="{CL_X2}" y2="{CL_Y_BOT}"
        stroke="#30363d" stroke-width="1"/>

  {grid_lines}
  {candles_svg}
  {month_labels}

  <!-- ── LEGEND ──────────────────────────────────────────────────────── -->
  <line x1="36" y1="{LG_Y-6}" x2="764" y2="{LG_Y-6}"
        stroke="#21262d" stroke-width="1" opacity="0.5"/>
  <rect x="36"  y="{LG_Y}" width="9" height="9" fill="{GREEN}" rx="2" opacity="0.85"/>
  <text x="50"  y="{LG_Y+9}" class="t-dim" font-size="10">most active —</text>
  <text x="132" y="{LG_Y+9}" fill="{GREEN}" font-size="10" font-weight="700"
        >{esc(week_label(active_week))} · {active_week["total"]} commits</text>
  <rect x="400" y="{LG_Y}" width="9" height="9" fill="{RED}" rx="2" opacity="0.85"/>
  <text x="414" y="{LG_Y+9}" class="t-dim" font-size="10">most lazy —</text>
  <text x="488" y="{LG_Y+9}" fill="{RED}" font-size="10" font-weight="700"
        >{esc(week_label(lazy_week))} · {lazy_week["total"]} commits</text>

  <!-- ── TOP REPOS ────────────────────────────────────────────────────── -->
  <line x1="36" y1="374" x2="764" y2="374" class="sep" stroke-width="1"/>
  <text x="36"  y="390" class="t-dim" font-size="9" letter-spacing="2">TOP REPOS</text>
  <text x="764" y="390" class="t-dim" font-size="9" text-anchor="end">commits</text>
{repos_svg}
</svg>'''


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        print("ERROR: no token. set GH_TOKEN or GITHUB_TOKEN.", file=sys.stderr)
        sys.exit(1)

    os.makedirs("assets", exist_ok=True)
    data = collect()
    print(f"  total commits: {data['total_commits']}", flush=True)

    chapters = [
        ("chapter1.svg", "The Numbers", ch1),
        ("chapter2.svg", "The Grind",   ch2),
    ]

    for fname, label, fn in chapters:
        print(f"→ generating {label} …", flush=True)
        svg  = fn(data)
        path = os.path.join("assets", fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"  saved {path}", flush=True)

    print("✓ done.", flush=True)


if __name__ == "__main__":
    main()
