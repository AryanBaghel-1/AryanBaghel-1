#!/usr/bin/env python3
"""
Generate a WakaTime coding-activity SVG card.

Expects the WAKATIME_API_KEY environment variable.
In GitHub Actions this comes from repository secrets.
For local runs, either export the variable or create a .env file
in the project root with:  WAKATIME_API_KEY=your_key_here
"""

import base64
import html
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ── Configuration ────────────────────────────────────────────

API_BASE = "https://wakatime.com/api/v1/users/current"

# SVG dimensions and palette
WIDTH, HEIGHT = 980, 650
COLOR_TEXT = "#f0f6fc"
COLOR_MUTED = "#8b949e"
COLOR_BORDER = "#30363d"
COLOR_PANEL = "#161b22"
COLOR_CYAN = "#58a6ff"
COLOR_PINK = "#f778ba"
COLOR_PURPLE = "#a371f7"
COLOR_GREEN = "#3fb950"

LANG_COLORS = [COLOR_CYAN, COLOR_PINK, COLOR_PURPLE, COLOR_GREEN, "#d29922", "#79c0ff"]
MAX_LANGUAGES = 6
ACTIVITY_DAYS = 30

FONT = "Arial,Helvetica,sans-serif"


# ── API Key ──────────────────────────────────────────────────

def load_api_key():
    """
    Load the WakaTime API key from environment or .env file.
    Returns the key string or exits with a clear error.
    """
    key = os.environ.get("WAKATIME_API_KEY")
    if key:
        return key

    # Try loading from .env in the project root
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "WAKATIME_API_KEY":
                value = value.strip().strip("\"'")
                if value:
                    return value

    print(
        "ERROR: WAKATIME_API_KEY is not set.\n"
        "\n"
        "  Option 1 — export it:   export WAKATIME_API_KEY=your_key\n"
        "  Option 2 — .env file:   create .env in project root with:\n"
        "                          WAKATIME_API_KEY=your_key\n"
        "\n"
        "  In GitHub Actions this is injected automatically from secrets.",
        file=sys.stderr,
    )
    sys.exit(1)


# ── WakaTime API ─────────────────────────────────────────────

def fetch_json(path, api_key, retries=4):
    """GET a JSON response from the WakaTime API with retry logic."""
    token = base64.b64encode(f"{api_key}:".encode()).decode()
    req = Request(
        API_BASE + path,
        headers={
            "Authorization": f"Basic {token}",
            "User-Agent": "github-profile-wakatime-card",
        },
    )

    for attempt in range(retries):
        try:
            with urlopen(req, timeout=30) as resp:
                return json.load(resp)

        except HTTPError as exc:
            if exc.code == 202 and attempt < retries - 1:
                time.sleep(8)       # WakaTime returns 202 while stats are processing
                continue
            raise

        except URLError:
            if attempt == retries - 1:
                raise
            time.sleep(5)

    raise RuntimeError("WakaTime API request failed after all retries")


# ── Helpers ──────────────────────────────────────────────────

def esc(value):
    """HTML-escape a value for safe SVG embedding."""
    return html.escape(str(value), quote=True)


def fmt_time(seconds):
    """Format seconds into a human-readable 'Xh XXm' or 'Xm' string."""
    seconds = int(seconds or 0)
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def svg_text(x, y, content, *, fill=COLOR_TEXT, size=12, weight="400", anchor=None):
    """Build a single <text> element string to reduce SVG boilerplate."""
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" '
        f'font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}"{anchor_attr}>'
        f'{content}</text>'
    )


def svg_rect(x, y, w, h, *, rx=16, fill=COLOR_PANEL, stroke=COLOR_BORDER):
    """Build a single <rect> element string."""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="{rx}" fill="{fill}" stroke="{stroke}"/>'
    )


# ── Data Fetching ────────────────────────────────────────────

def fetch_all_data(api_key):
    """Fetch all-time stats and last-30-day summaries. Returns (stats, summaries)."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=ACTIVITY_DAYS - 1)

    stats = fetch_json("/stats/all_time", api_key)["data"]
    summaries = fetch_json(
        f"/summaries?start={start.isoformat()}&end={today.isoformat()}", api_key
    ).get("data", [])

    return stats, summaries, today, start


# ── Language Aggregation ─────────────────────────────────────

def aggregate_languages(summaries):
    """Aggregate language seconds across all summary days, return sorted list."""
    totals = {}
    for day in summaries:
        for lang in day.get("languages", []):
            name = lang.get("name", "Unknown")
            totals[name] = totals.get(name, 0) + lang.get("total_seconds", 0)

    grand_total = sum(totals.values())
    languages = [
        {
            "name": name,
            "total_seconds": secs,
            "percent": (secs / grand_total * 100) if grand_total else 0,
        }
        for name, secs in totals.items()
    ]
    languages.sort(key=lambda x: x["total_seconds"], reverse=True)
    return languages[:MAX_LANGUAGES]


# ── Daily Activity ───────────────────────────────────────────

def build_daily_activity(summaries, start):
    """Return a list of total-seconds per day for the last 30 days."""
    by_date = {
        item.get("range", {}).get("date"): item.get("grand_total", {}).get("total_seconds", 0)
        for item in summaries
    }
    return [by_date.get((start + timedelta(days=i)).isoformat(), 0) for i in range(ACTIVITY_DAYS)]


# ── SVG Builder ──────────────────────────────────────────────

def build_svg(stats, languages, activity, today, start):
    """Assemble and return the complete SVG string."""
    total_secs = stats.get(
        "total_seconds_including_other_language",
        stats.get("total_seconds", 0),
    )
    daily_avg = stats.get("daily_average", 0)

    parts = []

    # ── Header & Background ──────────────────────────────────
    parts.append(f"""\
<svg xmlns="http://www.w3.org/2000/svg"
     width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">

<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#151b25"/>
    <stop offset="1" stop-color="#0d1117"/>
  </linearGradient>
  <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{COLOR_CYAN}"/>
    <stop offset="1" stop-color="{COLOR_PINK}"/>
  </linearGradient>
</defs>

<!-- Background -->
<rect width="{WIDTH}" height="{HEIGHT}" rx="22"
      fill="url(#bg)" stroke="{COLOR_BORDER}" stroke-width="2"/>

<!-- Window dots -->
<circle cx="32" cy="30" r="6" fill="{COLOR_PINK}"/>
<circle cx="52" cy="30" r="6" fill="{COLOR_PURPLE}"/>
<circle cx="72" cy="30" r="6" fill="{COLOR_CYAN}"/>

<!-- Title -->
{svg_text(38, 76, "Coding Activity", fill=COLOR_TEXT, size=25, weight="700")}
{svg_text(942, 76, "ALL TIME", fill=COLOR_MUTED, size=13, weight="700", anchor="end")}
<line x1="38" y1="94" x2="942" y2="94" stroke="{COLOR_BORDER}"/>""")

    # ── Stat Cards ───────────────────────────────────────────
    # Total coding time
    parts.append(f"""\
{svg_rect(38, 116, 430, 126)}
{svg_text(62, 148, "TOTAL CODING TIME", fill=COLOR_MUTED, size=12, weight="700")}
{svg_text(62, 192, esc(fmt_time(total_secs)), fill=COLOR_TEXT, size=34, weight="700")}
{svg_text(62, 219, "Since your WakaTime account started", fill=COLOR_MUTED, size=12)}""")

    # Daily average
    parts.append(f"""\
{svg_rect(486, 116, 214, 126)}
{svg_text(510, 148, "DAILY AVERAGE", fill=COLOR_MUTED, size=12, weight="700")}
{svg_text(510, 192, esc(fmt_time(daily_avg)), fill=COLOR_CYAN, size=30, weight="700")}
{svg_text(510, 219, "Average coding time", fill=COLOR_MUTED, size=12)}""")

    # Top language
    parts.append(f'{svg_rect(718, 116, 224, 126)}')
    parts.append(svg_text(742, 148, "TOP LANGUAGE", fill=COLOR_MUTED, size=12, weight="700"))
    if languages:
        top = languages[0]
        parts.append(svg_text(742, 190, esc(top["name"]), fill=COLOR_PINK, size=25, weight="700"))
        parts.append(svg_text(742, 219, f'{top["percent"]:.2f}% of last 30 days', fill=COLOR_MUTED, size=12))
    else:
        parts.append(svg_text(742, 190, "—", fill=COLOR_MUTED, size=25, weight="700"))

    # ── Language Bars ────────────────────────────────────────
    parts.append(f"""\
{svg_rect(38, 264, 904, 238)}
{svg_text(62, 298, "Most Used Languages", fill=COLOR_TEXT, size=17, weight="700")}
{svg_text(918, 298, "LAST 30 DAYS", fill=COLOR_MUTED, size=11, anchor="end")}""")

    for i, lang in enumerate(languages):
        y = 332 + i * 27
        pct = lang["percent"]
        bar_w = max(5, min(520, 520 * pct / 100))
        color = LANG_COLORS[i % len(LANG_COLORS)]

        parts.append(f"""\
{svg_text(62, y, esc(lang["name"]), size=12)}
<rect x="190" y="{y - 11}" width="520" height="10" rx="5" fill="#21262d"/>
<rect x="190" y="{y - 11}" width="{bar_w:.1f}" height="10" rx="5" fill="{color}"/>
{svg_text(735, y, f"{pct:.2f}%", anchor="end")}
{svg_text(918, y, esc(fmt_time(lang["total_seconds"])), fill=COLOR_MUTED, size=11, anchor="end")}""")

    # ── Activity Graph ───────────────────────────────────────
    graph_y, graph_h = 535, 80
    graph_x, graph_w = 62, 856
    peak = max(activity) if activity else 1

    points = []
    for i, val in enumerate(activity):
        x = graph_x + graph_w * i / max(1, len(activity) - 1)
        y = graph_y + graph_h - (graph_h * val / peak if peak else 0)
        points.append((x, y))

    line_path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
    area_path = (
        f"M {points[0][0]:.1f} {graph_y + graph_h} L "
        + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
        + f" L {points[-1][0]:.1f} {graph_y + graph_h} Z"
    )

    parts.append(f"""\
{svg_text(62, 518, "Last 30 Days Activity", fill=COLOR_TEXT, size=15, weight="700")}
{svg_text(918, 518, "UPDATED DAILY", fill=COLOR_MUTED, size=11, anchor="end")}
<path d="{area_path}" fill="url(#line)" opacity="0.10"/>
<path d="{line_path}" fill="none" stroke="url(#line)"
      stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
<line x1="62" y1="615" x2="918" y2="615" stroke="{COLOR_BORDER}"/>
{svg_text(62, 640, start.strftime("%d %b"), fill=COLOR_MUTED, size=10)}
{svg_text(918, 640, today.strftime("%d %b"), fill=COLOR_MUTED, size=10, anchor="end")}

</svg>""")

    return "\n".join(parts)


# ── Main ─────────────────────────────────────────────────────

def main():
    api_key = load_api_key()

    stats, summaries, today, start = fetch_all_data(api_key)
    languages = aggregate_languages(summaries)
    activity = build_daily_activity(summaries, start)

    svg = build_svg(stats, languages, activity, today, start)

    out_dir = Path(__file__).resolve().parent.parent / "assets"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "wakatime-card.svg"
    out_file.write_text(svg, encoding="utf-8")

    print(f"Generated {out_file}")


if __name__ == "__main__":
    main()