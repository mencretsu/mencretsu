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

BG      = "#010409"
SURFACE = "#0d1117"
BORDER  = "#21262d"
TEXT    = "#e6edf3"
DIM     = "#8b949e"
ACCENT  = "#388bfd"
GREEN   = "#3fb950"
ORANGE  = "#f0883e"
PURPLE  = "#a371f7"
RED     = "#f85149"
FONT    = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"


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
    commits_by_date  = defaultdict(int)
    commits_by_hour  = defaultdict(int)
    commits_by_dow   = defaultdict(int)
    commit_messages  = []
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


# ─── Chapter 1 — The Numbers ─────────────────────────────────────────────────

def ch1(data):
    total   = data["total_commits"]
    by_hour = data["commits_by_hour"]
    by_dow  = data["commits_by_dow"]

    fav_hour = max(by_hour, key=by_hour.get) if by_hour else 2
    fav_dow  = max(by_dow,  key=by_dow.get)  if by_dow  else 6
    DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

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

    BAR_W, BAR_GAP = 24, 6
    BAR_STEP = BAR_W + BAR_GAP
    BAR_MAX  = 32
    BAR_Y    = 306
    GRID_X   = (800 - (24*BAR_STEP - BAR_GAP)) // 2
    max_h    = max(by_hour.values(), default=1)

    bars = ""
    for h in range(24):
        cnt = by_hour.get(h, 0)
        bh  = max(int((cnt/max_h)*BAR_MAX), 1 if cnt>0 else 0)
        x   = GRID_X + h*BAR_STEP
        col = ACCENT if h == fav_hour else BORDER
        opa = "1" if h == fav_hour else "0.65"
        if bh:
            bars += (
                f'  <rect x="{x}" y="{BAR_Y+BAR_MAX-bh}" '
                f'width="{BAR_W}" height="{bh}" fill="{col}" rx="3" opacity="{opa}"/>\n'
            )
    for h in [0,6,12,18,23]:
        lx = GRID_X + h*BAR_STEP + BAR_W//2
        bars += (
            f'  <text x="{lx}" y="{BAR_Y+BAR_MAX+15}" '
            f'font-family="{FONT}" font-size="9" fill="{DIM}" text-anchor="middle">{h:02d}</text>\n'
        )

    return f'''\
<svg width="800" height="400" viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="glow1"><feGaussianBlur stdDeviation="4" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <linearGradient id="lg1" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{ACCENT};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:{PURPLE};stop-opacity:0"/>
    </linearGradient>
  </defs>
  <rect width="800" height="400" fill="{BG}" rx="12"/>
  <rect x="1" y="1" width="798" height="398" fill="none" stroke="{BORDER}" stroke-width="1" rx="11"/>
  <text x="36" y="48" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="3">THE NUMBERS</text>
  <text x="764" y="48" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="2" text-anchor="end">LAST 365 DAYS</text>
  <rect x="36" y="58" width="220" height="1" fill="url(#lg1)"/>
  <text x="145" y="160" font-family="{FONT}" font-size="58" font-weight="700"
        fill="{TEXT}" text-anchor="middle" filter="url(#glow1)">{esc(total_str)}</text>
  <text x="145" y="182" font-family="{FONT}" font-size="10" fill="{DIM}"
        text-anchor="middle" letter-spacing="3">COMMITS</text>
  <line x1="272" y1="105" x2="272" y2="200" stroke="{BORDER}" stroke-width="1"/>
  <text x="450" y="152" font-family="{FONT}" font-size="46" font-weight="700"
        fill="{ACCENT}" text-anchor="middle" filter="url(#glow1)">{esc(hour_str)}</text>
  <text x="450" y="174" font-family="{FONT}" font-size="10" fill="{DIM}"
        text-anchor="middle" letter-spacing="3">PEAK HOUR</text>
  <text x="450" y="192" font-family="{FONT}" font-size="10" fill="{PURPLE}"
        text-anchor="middle">— {esc(_hvibe(fav_hour))} —</text>
  <line x1="590" y1="105" x2="590" y2="200" stroke="{BORDER}" stroke-width="1"/>
  <text x="700" y="152" font-family="{FONT}" font-size="26" font-weight="700"
        fill="{ORANGE}" text-anchor="middle" filter="url(#glow1)">{esc(day_str)}</text>
  <text x="700" y="174" font-family="{FONT}" font-size="10" fill="{DIM}"
        text-anchor="middle" letter-spacing="2">MOST ACTIVE</text>
  <rect x="36" y="213" width="728" height="1" fill="{BORDER}"/>
  <text x="400" y="252" font-family="{FONT}" font-size="13" fill="{DIM}"
        text-anchor="middle" font-style="italic">&quot;{esc(_vibe(fav_hour))}&quot;</text>
  <text x="36" y="294" font-family="{FONT}" font-size="10" fill="{DIM}" letter-spacing="2">HOURLY ACTIVITY</text>
  <rect x="36" y="300" width="728" height="1" fill="{BORDER}" opacity="0.35"/>
{bars}
</svg>'''


# ─── Chapter 2 — THE GRIND ────────────────
def ch2(data):
    cbd     = data["commits_by_date"]
    by_hour = data["commits_by_hour"]
    total   = data["total_commits"]

    W, H = 800, 420

    # Bangun weekly buckets (52 minggu terakhir)
    today     = datetime.now(timezone.utc).date()
    start_raw = today - timedelta(days=363)
    start     = start_raw - timedelta(days=(start_raw.isoweekday() % 7))

    weeks = []
    for w in range(52):
        week_days = [start + timedelta(days=w*7+d) for d in range(7)]
        week_counts = [cbd.get(d.strftime("%Y-%m-%d"), 0) for d in week_days]
        total_w  = sum(week_counts)
        nonzero  = [c for c in week_counts if c > 0]
        wk_min   = min(nonzero) if nonzero else 0
        wk_max   = max(nonzero) if nonzero else 0
        wk_open  = week_counts[0]   # Senin
        wk_close = week_counts[-1]  # Minggu
        weeks.append({
            "total": total_w, "min": wk_min, "max": wk_max,
            "open": wk_open,  "close": wk_close,
            "date": week_days[0],
        })

    # Candle area
    CL_X1, CL_X2 = 36, 764
    CL_Y_TOP, CL_Y_BOT = 72, 220
    CL_H = CL_Y_BOT - CL_Y_TOP

    max_total = max(w["total"] for w in weeks) if weeks else 1

    n_candles = len(weeks)
    cw_full   = (CL_X2 - CL_X1) / n_candles
    cw_body   = max(cw_full * 0.55, 2)
    cw_gap    = cw_full - cw_body

    candles_svg = ""
    for i, wk in enumerate(weeks):
        cx    = CL_X1 + i * cw_full + cw_gap / 2
        delay = round(i * 0.03, 3)

        prev_total = weeks[i-1]["total"] if i > 0 else wk["total"]
        is_up  = wk["total"] >= prev_total
        col    = GREEN if is_up else RED

        # Tinggi body = proporsi total minggu ini vs max
        if max_total == 0:
            body_h = 1
        else:
            body_h = max(int((wk["total"] / max_total) * CL_H), 2)

        body_y = CL_Y_BOT - body_h

        # Wick = kalau ada spread min/max dalam seminggu
        if max_total > 0 and wk["max"] > 0:
            wick_top = CL_Y_BOT - int((wk["max"] / max_total) * CL_H) - 3
            wick_bot = CL_Y_BOT
        else:
            wick_top = body_y
            wick_bot = CL_Y_BOT

        cx_mid = cx + cw_body / 2

        # Wick line
        candles_svg += (
            f'<line x1="{cx_mid:.1f}" y1="{wick_top}" x2="{cx_mid:.1f}" y2="{wick_bot}" '
            f'stroke="{col}" stroke-width="1" opacity="0.35">'
            f'<animate attributeName="opacity" from="0" to="0.35" dur="0.2s" '
            f'begin="{delay}s" fill="freeze"/>'
            f'</line>\n'
        )

        # Body — animasi tumbuh dari bawah ke atas
        candles_svg += (
            f'<rect x="{cx:.1f}" y="{CL_Y_BOT}" width="{cw_body:.1f}" height="0" '
            f'fill="{col}" rx="1" opacity="0.85">'
            f'<animate attributeName="y" from="{CL_Y_BOT}" to="{body_y}" '
            f'dur="0.35s" begin="{delay}s" fill="freeze" '
            f'calcMode="spline" keySplines="0.22 1 0.36 1" keyTimes="0;1"/>'
            f'<animate attributeName="height" from="0" to="{body_h}" '
            f'dur="0.35s" begin="{delay}s" fill="freeze" '
            f'calcMode="spline" keySplines="0.22 1 0.36 1" keyTimes="0;1"/>'
            f'</rect>\n'
        )

    # Month labels di bawah chart
    month_labels = ""
    prev_month = None
    for i, wk in enumerate(weeks):
        if wk["date"].month != prev_month:
            x    = CL_X1 + i * cw_full + cw_body / 2
            abbr = wk["date"].strftime("%b")
            month_labels += (
                f'<text x="{x:.1f}" y="{CL_Y_BOT+16}" font-family="{FONT}" '
                f'font-size="9" fill="{DIM}" text-anchor="middle">{abbr}</text>\n'
            )
            prev_month = wk["date"].month

    # Y-axis grid lines (tipis)
    grid_lines = ""
    for pct in [0.25, 0.5, 0.75, 1.0]:
        gy  = CL_Y_BOT - int(pct * CL_H)
        val = int(pct * max_total)
        grid_lines += (
            f'<line x1="{CL_X1}" y1="{gy}" x2="{CL_X2}" y2="{gy}" '
            f'stroke="{BORDER}" stroke-width="1" opacity="0.4"/>\n'
            f'<text x="{CL_X1-4}" y="{gy+4}" font-family="{FONT}" font-size="8" '
            f'fill="{DIM}" text-anchor="end">{val}</text>\n'
        )

    # ── Radial 24h clock di bawah, tengah ────────────────────────────────────
    fav_hour    = max(by_hour, key=by_hour.get) if by_hour else 0
    max_h_count = max(by_hour.values(), default=1)
    CX, CY, BASE_R = 400, 340, 50

    def _hlabel(h):
        if h == 0:  return "12 AM"
        if h < 12:  return f"{h} AM"
        if h == 12: return "12 PM"
        return f"{h-12} PM"

    clock_svg = (
        f'<circle cx="{CX}" cy="{CY}" r="{BASE_R+4}" fill="none" '
        f'stroke="{BORDER}" stroke-width="1"/>\n'
        f'<circle cx="{CX}" cy="{CY}" r="{BASE_R}" fill="{SURFACE}" opacity="0.6"/>\n'
    )

    for h in range(24):
        cnt_h  = by_hour.get(h, 0)
        angle  = (h / 24) * 2 * math.pi - math.pi / 2
        bar_l  = 6 + int((cnt_h / max_h_count) * 32) if cnt_h > 0 else 2
        x1 = CX + math.cos(angle) * (BASE_R + 6)
        y1 = CY + math.sin(angle) * (BASE_R + 6)
        x2 = CX + math.cos(angle) * (BASE_R + 6 + bar_l)
        y2 = CY + math.sin(angle) * (BASE_R + 6 + bar_l)
        is_peak = (h == fav_hour)
        col = ACCENT if is_peak else ("#1a4fbb" if cnt_h > 0 else BORDER)
        sw  = 5 if is_peak else (2 if cnt_h > 0 else 1)
        delay_r = round(1.8 + h * 0.04, 3)

        anim = (
            f'<animate attributeName="stroke-opacity" values="1;0.4;1" '
            f'dur="1.8s" begin="{delay_r}s" repeatCount="indefinite"/>'
            if is_peak else ""
        )
        clock_svg += (
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
            f'stroke="{col}" stroke-width="{sw}" stroke-linecap="round">'
            f'<animate attributeName="x2" to="{x2:.1f}" dur="0.3s" begin="{delay_r}s" fill="freeze"/>'
            f'<animate attributeName="y2" to="{y2:.1f}" dur="0.3s" begin="{delay_r}s" fill="freeze"/>'
            f'{anim}'
            f'</line>\n'
        )

    for h, label in [(0,"12a"),(6,"6a"),(12,"12p"),(18,"6p")]:
        angle = (h / 24) * 2 * math.pi - math.pi / 2
        lx = CX + math.cos(angle) * (BASE_R + 46)
        ly = CY + math.sin(angle) * (BASE_R + 46)
        clock_svg += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-family="{FONT}" font-size="9" '
            f'fill="{DIM}" text-anchor="middle" dominant-baseline="middle">{label}</text>\n'
        )

    clock_svg += (
        f'<text x="{CX}" y="{CY-8}" font-family="{FONT}" font-size="17" font-weight="700" '
        f'fill="{ACCENT}" text-anchor="middle" filter="url(#glw)">{_hlabel(fav_hour)}</text>\n'
        f'<text x="{CX}" y="{CY+10}" font-family="{FONT}" font-size="8" '
        f'fill="{DIM}" text-anchor="middle" letter-spacing="2">PEAK HOUR</text>\n'
    )

    # legend kiri-kanan clock
    night   = sum(v for k,v in by_hour.items() if k>=22 or k<6)
    night_p = round(night/total*100) if total else 0
    weekend_commits = sum(v for k,v in data["commits_by_dow"].items() if k>=5)
    wknd_p  = round(weekend_commits/total*100) if total else 0

    return f'''\
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="glw">
      <feGaussianBlur stdDeviation="3" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="hdrg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}" rx="12"/>
  <rect x="1" y="1" width="{W-2}" height="{H-2}" fill="none" stroke="{BORDER}" stroke-width="1" rx="11"/>

  <!-- header -->
  <text x="36" y="44" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="3">THE GRIND</text>
  <text x="{W-36}" y="44" font-family="{FONT}" font-size="11" fill="{DIM}" letter-spacing="2" text-anchor="end">52 WEEKS</text>
  <rect x="36" y="54" width="110" height="1" fill="url(#hdrg)"/>

  <!-- legend -->
  <rect x="{CL_X2-120}" y="38" width="10" height="10" fill="{GREEN}" rx="2" opacity="0.85"/>
  <text x="{CL_X2-106}" y="48" font-family="{FONT}" font-size="9" fill="{DIM}">up week</text>
  <rect x="{CL_X2-55}" y="38" width="10" height="10" fill="{RED}" rx="2" opacity="0.85"/>
  <text x="{CL_X2-41}" y="48" font-family="{FONT}" font-size="9" fill="{DIM}">down</text>

  <!-- baseline -->
  <line x1="{CL_X1}" y1="{CL_Y_BOT}" x2="{CL_X2}" y2="{CL_Y_BOT}"
        stroke="{BORDER}" stroke-width="1"/>

  <!-- grid -->
  {grid_lines}

  <!-- candles -->
  {candles_svg}

  <!-- month labels -->
  {month_labels}

  <!-- divider sebelum clock -->
  <line x1="36" y1="258" x2="764" y2="258" stroke="{BORDER}" stroke-width="1" opacity="0.4"/>

  <!-- label clock section -->
  <text x="{CX}" y="282" font-family="{FONT}" font-size="9" fill="{DIM}"
        text-anchor="middle" letter-spacing="3">24H ACTIVITY PATTERN</text>

  <!-- radial clock -->
  {clock_svg}

  <!-- stat kiri & kanan clock -->
  <text x="120" y="{CY-6}" font-family="{FONT}" font-size="22" font-weight="700"
        fill="{PURPLE}" text-anchor="middle">{night_p}%</text>
  <text x="120" y="{CY+12}" font-family="{FONT}" font-size="9" fill="{DIM}"
        text-anchor="middle" letter-spacing="1">night commits</text>

  <text x="680" y="{CY-6}" font-family="{FONT}" font-size="22" font-weight="700"
        fill="{ORANGE}" text-anchor="middle">{wknd_p}%</text>
  <text x="680" y="{CY+12}" font-family="{FONT}" font-size="9" fill="{DIM}"
        text-anchor="middle" letter-spacing="1">weekend commits</text>
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


# ─── Local preview dengan dummy data ─────────────────────────────────────────

if __name__ == "__main__":
    from datetime import date

    today = date.today()
    cbd   = {}
    for i in range(365):
        d = today - timedelta(days=i)
        if random.random() > 0.38:
            cbd[d.strftime("%Y-%m-%d")] = random.randint(1, 14)

    by_hour = {h: random.randint(0, 40) for h in range(24)}
    by_hour[2]  = 55   # peak jam 2 pagi biar dramatis
    by_dow  = {d: random.randint(5, 60) for d in range(7)}

    data = {
        "repos": [],
        "commits_by_date":     cbd,
        "commits_by_hour":     by_hour,
        "commits_by_dow":      by_dow,
        "commit_messages":     [],
        "repo_commit_counts":  {},
        "total_commits":       sum(cbd.values()),
    }

    os.makedirs("assets", exist_ok=True)

    with open("assets/chapter1.svg", "w") as f:
        f.write(ch1(data))
    print("→ assets/chapter1.svg")

    with open("assets/chapter2.svg", "w") as f:
        f.write(ch2(data))
    print("→ assets/chapter2.svg")

    print("✓ buka di browser.")
