#!/usr/bin/env python3
import base64, html, json, os, time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://wakatime.com/api/v1/users/current"
KEY = os.environ["WAKATIME_API_KEY"]

def get_json(path, retries=4):
    token = base64.b64encode(f"{KEY}:".encode()).decode()
    req = Request(API + path, headers={"Authorization": f"Basic {token}", "User-Agent": "github-profile-wakatime-card"})
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=30) as r:
                return json.load(r)
        except HTTPError as e:
            if e.code == 202 and attempt < retries - 1:
                time.sleep(8); continue
            raise
        except URLError:
            if attempt == retries - 1: raise
            time.sleep(5)
    raise RuntimeError("WakaTime API request failed")

def esc(v): return html.escape(str(v), quote=True)

def fmt(seconds):
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600); m = rem // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"

today = datetime.now(timezone.utc).date()
start = today - timedelta(days=29)
stats = get_json("/stats/all_time")["data"]
total = stats.get("total_seconds_including_other_language", stats.get("total_seconds", 0))
daily_avg = stats.get("daily_average", 0)
languages = sorted(stats.get("languages", []), key=lambda x: x.get("total_seconds", 0), reverse=True)[:6]
summaries = get_json(f"/summaries?start={start.isoformat()}&end={today.isoformat()}").get("data", [])
by_date = {x.get("range", {}).get("date"): x.get("grand_total", {}).get("total_seconds", 0) for x in summaries}
activity = [by_date.get((start + timedelta(days=i)).isoformat(), 0) for i in range(30)]

W,H=980,650; TEXT="#f0f6fc"; MUTED="#8b949e"; BORDER="#30363d"; PANEL="#161b22"; CYAN="#58a6ff"; PINK="#f778ba"; PURPLE="#a371f7"; GREEN="#3fb950"
svg=[f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#151b25"/><stop offset="1" stop-color="#0d1117"/></linearGradient><linearGradient id="line" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{PINK}"/></linearGradient></defs><rect width="{W}" height="{H}" rx="22" fill="url(#bg)" stroke="{BORDER}" stroke-width="2"/><circle cx="32" cy="30" r="6" fill="{PINK}"/><circle cx="52" cy="30" r="6" fill="{PURPLE}"/><circle cx="72" cy="30" r="6" fill="{CYAN}"/><text x="38" y="76" fill="{TEXT}" font-family="Arial,Helvetica,sans-serif" font-size="25" font-weight="700">Coding Activity</text><text x="942" y="76" text-anchor="end" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="13" font-weight="700">ALL TIME</text><line x1="38" y1="94" x2="942" y2="94" stroke="{BORDER}"/><rect x="38" y="116" width="430" height="126" rx="16" fill="{PANEL}" stroke="{BORDER}"/><text x="62" y="148" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="12" font-weight="700">TOTAL CODING TIME</text><text x="62" y="192" fill="{TEXT}" font-family="Arial,Helvetica,sans-serif" font-size="34" font-weight="700">{esc(fmt(total))}</text><text x="62" y="219" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="12">Since your WakaTime account started</text><rect x="486" y="116" width="214" height="126" rx="16" fill="{PANEL}" stroke="{BORDER}"/><text x="510" y="148" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="12" font-weight="700">DAILY AVERAGE</text><text x="510" y="192" fill="{CYAN}" font-family="Arial,Helvetica,sans-serif" font-size="30" font-weight="700">{esc(fmt(daily_avg))}</text><text x="510" y="219" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="12">Average coding time</text><rect x="718" y="116" width="224" height="126" rx="16" fill="{PANEL}" stroke="{BORDER}"/><text x="742" y="148" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="12" font-weight="700">TOP LANGUAGE</text>''']
if languages:
    top=languages[0]; svg.append(f'<text x="742" y="190" fill="{PINK}" font-family="Arial,Helvetica,sans-serif" font-size="25" font-weight="700">{esc(top.get("name","—"))}</text><text x="742" y="219" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="12">{float(top.get("percent",0)):.2f}% of total time</text>')
else: svg.append(f'<text x="742" y="190" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="25" font-weight="700">—</text>')
svg.append(f'<rect x="38" y="264" width="904" height="238" rx="16" fill="{PANEL}" stroke="{BORDER}"/><text x="62" y="298" fill="{TEXT}" font-family="Arial,Helvetica,sans-serif" font-size="17" font-weight="700">Most Used Languages</text><text x="918" y="298" text-anchor="end" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="11">ALL-TIME SHARE</text>')
colors=[CYAN,PINK,PURPLE,GREEN,"#d29922","#79c0ff"]
for i,lang in enumerate(languages):
    y=332+i*27; pct=float(lang.get("percent",0)); bw=max(5,min(520,520*pct/100))
    svg.append(f'<text x="62" y="{y}" fill="{TEXT}" font-family="Arial,Helvetica,sans-serif" font-size="12">{esc(lang.get("name","Unknown"))}</text><rect x="190" y="{y-11}" width="520" height="10" rx="5" fill="#21262d"/><rect x="190" y="{y-11}" width="{bw:.1f}" height="10" rx="5" fill="{colors[i%len(colors)]}"/><text x="735" y="{y}" fill="{TEXT}" font-family="Arial,Helvetica,sans-serif" font-size="12" text-anchor="end">{pct:.2f}%</text><text x="918" y="{y}" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="11" text-anchor="end">{esc(fmt(lang.get("total_seconds",0)))}</text>')
gy=535; gh=80; gx=62; gw=856; mx=max(activity) if activity else 1
pts=[]
for i,v in enumerate(activity): pts.append((gx+gw*i/max(1,len(activity)-1), gy+gh-(gh*v/mx if mx else 0)))
path="M "+" L ".join(f"{x:.1f} {y:.1f}" for x,y in pts); area=f"M {pts[0][0]:.1f} {gy+gh} L "+" L ".join(f"{x:.1f} {y:.1f}" for x,y in pts)+f" L {pts[-1][0]:.1f} {gy+gh} Z"
svg.append(f'<text x="62" y="518" fill="{TEXT}" font-family="Arial,Helvetica,sans-serif" font-size="15" font-weight="700">Last 30 Days Activity</text><text x="918" y="518" text-anchor="end" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="11">UPDATED DAILY</text><path d="{area}" fill="url(#line)" opacity="0.10"/><path d="{path}" fill="none" stroke="url(#line)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><line x1="62" y1="615" x2="918" y2="615" stroke="{BORDER}"/><text x="62" y="640" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="10">{start.strftime("%d %b")}</text><text x="918" y="640" text-anchor="end" fill="{MUTED}" font-family="Arial,Helvetica,sans-serif" font-size="10">{today.strftime("%d %b")}</text></svg>')
os.makedirs("assets",exist_ok=True)
with open("assets/wakatime-card.svg","w",encoding="utf-8") as f: f.write("\n".join(svg))
print("Generated assets/wakatime-card.svg")
