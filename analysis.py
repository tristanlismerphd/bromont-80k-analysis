#!/usr/bin/env python3
"""
Bromont 80K Ultra — Training Analytics
=======================================
Performance Management Chart (PMC) and training load analysis
built on raw Strava API data.

Model
-----
hrTSS per activity:
    hrTSS = duration_hrs x (avg_HR / LTHR)^2 x 100

ATL (Acute Training Load / Fatigue):
    ATL[t] = ATL[t-1] + (TSS[t] - ATL[t-1]) x (1 - e^{-1/7})

CTL (Chronic Training Load / Fitness):
    CTL[t] = CTL[t-1] + (TSS[t] - CTL[t-1]) x (1 - e^{-1/42})

TSB (Training Stress Balance / Form):
    TSB[t] = CTL[t] - ATL[t]

LTHR estimated from Ottawa Half-Marathon effort (177 bpm avg).
Set to 175 bpm.

References
----------
- Banister et al. (1975) -- original impulse-response model
- Coggan (2003) -- PMC implementation
- Strava Fitness & Freshness (same model, different UI)
"""

import os, math, json, requests
from datetime import datetime, timedelta, date
from typing import Optional
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -- Config -------------------------------------------------------------------
LTHR         = 175          # Lactate threshold HR (bpm)
K_ATL        = 1 - math.exp(-1 / 7)   # ATL decay constant (7-day)
K_CTL        = 1 - math.exp(-1 / 42)  # CTL decay constant (42-day)
RACE_DATE    = date(2026, 10, 17)
RACE_NAME    = "Bromont 80K Ultra"

RUN_TYPES    = {"Run", "TrailRun"}
RIDE_TYPES   = {"Ride", "VirtualRide", "GravelRide"}

# -- Strava Auth --------------------------------------------------------------
def get_access_token() -> str:
    resp = requests.post("https://www.strava.com/oauth/token", data={
        "client_id":     os.environ["STRAVA_CLIENT_ID"],
        "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
        "refresh_token": os.environ["STRAVA_REFRESH_TOKEN"],
        "grant_type":    "refresh_token",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_activities(token: str, pages: int = 2) -> list[dict]:
    all_acts = []
    for page in range(1, pages + 1):
        resp = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {token}"},
            params={"per_page": 200, "page": page},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_acts.extend(batch)
    return all_acts


# -- TSS Calculation ----------------------------------------------------------
def hr_tss(duration_s: float, avg_hr: Optional[float], lthr: float = LTHR) -> float:
    """HR-based Training Stress Score."""
    if avg_hr and avg_hr > 0:
        return (duration_s / 3600) * (avg_hr / lthr) ** 2 * 100
    # Fallback: duration-based estimate
    return (duration_s / 3600) * 60


def compute_day_tss(activities: list[dict]) -> dict[str, float]:
    day_tss: dict[str, float] = {}
    for act in activities:
        dt  = datetime.fromisoformat(act["start_date_local"].replace("Z", ""))
        ds  = dt.strftime("%Y-%m-%d")
        dur = act.get("moving_time", 0)
        hr  = act.get("average_heartrate")
        tss = hr_tss(dur, hr)
        day_tss[ds] = day_tss.get(ds, 0) + tss
    return day_tss


# -- PMC ----------------------------------------------------------------------
def compute_pmc(day_tss: dict[str, float], start: date, end: date) -> list[dict]:
    pmc, atl, ctl = [], 0.0, 0.0
    cur = start
    while cur <= end:
        ds  = cur.strftime("%Y-%m-%d")
        tss = day_tss.get(ds, 0.0)
        atl = atl + (tss - atl) * K_ATL
        ctl = ctl + (tss - ctl) * K_CTL
        pmc.append({"date": ds, "tss": round(tss, 1),
                    "atl": round(atl, 1), "ctl": round(ctl, 1),
                    "tsb": round(ctl - atl, 1)})
        cur += timedelta(days=1)
    return pmc


# -- Weekly Aggregation -------------------------------------------------------
def weekly_summary(activities: list[dict]) -> list[dict]:
    weeks: dict[str, dict] = {}
    for act in activities:
        dt  = datetime.fromisoformat(act["start_date_local"].replace("Z", ""))
        wk  = (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
        t   = act.get("sport_type", act.get("type", ""))
        dk  = act["distance"] / 1000
        el  = act.get("total_elevation_gain", 0)
        dur = act.get("moving_time", 0)
        hr  = act.get("average_heartrate")
        tss = hr_tss(dur, hr)
        if wk not in weeks:
            weeks[wk] = {"week": wk, "run_km": 0, "ride_km": 0,
                         "vert_m": 0, "tss": 0, "long_run": 0}
        w = weeks[wk]
        w["tss"]   += tss
        w["vert_m"] += el
        if t in RUN_TYPES:
            w["run_km"]  += dk
            w["long_run"] = max(w["long_run"], dk)
        elif t in RIDE_TYPES:
            w["ride_km"] += dk
    return [{"week": k, "run_km": round(v["run_km"], 1),
             "ride_km": round(v["ride_km"], 1), "vert_m": round(v["vert_m"], 0),
             "tss": round(v["tss"], 0), "long_run": round(v["long_run"], 1)}
            for k, v in sorted(weeks.items())]


# -- Plotting -----------------------------------------------------------------
DARK_BG  = "#07070f"
ACCENT   = "#f5a623"
BLUE     = "#48cae4"
GREEN    = "#52d68a"
MUTED    = "rgba(234,234,242,0.45)"
TEXT     = "#eaeaf2"
GRID     = "rgba(255,255,255,0.07)"


def plot_pmc(pmc: list[dict]) -> go.Figure:
    today_str = date.today().strftime("%Y-%m-%d")
    dates = [p["date"] for p in pmc]
    ctl   = [p["ctl"]  for p in pmc]
    atl   = [p["atl"]  for p in pmc]
    tsb   = [p["tsb"]  for p in pmc]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # TSB bars
    fig.add_trace(go.Bar(
        x=dates, y=tsb, name="Form (TSB)",
        marker_color=[GREEN if v >= 0 else ACCENT for v in tsb],
        opacity=0.5, yaxis="y2"
    ))

    # CTL / ATL lines
    fig.add_trace(go.Scatter(x=dates, y=ctl, name="Fitness (CTL)",
        line=dict(color=BLUE, width=2.5)))
    fig.add_trace(go.Scatter(x=dates, y=atl, name="Fatigue (ATL)",
        line=dict(color=ACCENT, width=2, dash="dash")))

    # Race day
    fig.add_vline(x=RACE_DATE.strftime("%Y-%m-%d"),
        line_color=GREEN, line_width=1, line_dash="dot",
        annotation_text=RACE_NAME, annotation_font_color=GREEN,
        annotation_position="top left")

    # Today
    fig.add_vline(x=today_str, line_color=MUTED, line_width=1,
        annotation_text="Today", annotation_font_color=MUTED)

    fig.update_layout(
        title=dict(text="Performance Management Chart", font_color=TEXT),
        paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
        font=dict(family="monospace", color=MUTED),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor=GRID, showgrid=True),
        yaxis=dict(title="Load (AU)", gridcolor=GRID),
        yaxis2=dict(title="Form (TSB)", overlaying="y", side="right",
                    zeroline=True, zerolinecolor=MUTED),
        hovermode="x unified",
        margin=dict(t=60, b=40, l=60, r=60),
    )
    return fig


def plot_weekly(weeks: list[dict]) -> go.Figure:
    wk_labels = [w["week"] for w in weeks]
    run_km    = [w["run_km"] for w in weeks]
    ride_km   = [w["ride_km"] for w in weeks]
    vert      = [w["vert_m"] for w in weeks]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(x=wk_labels, y=run_km,
        name="Run (km)", marker_color=ACCENT, opacity=0.85))
    fig.add_trace(go.Bar(x=wk_labels, y=ride_km,
        name="Ride (km)", marker_color=BLUE, opacity=0.85))
    fig.add_trace(go.Scatter(x=wk_labels, y=vert, name="Vert (m)",
        line=dict(color=GREEN, width=2), yaxis="y2"), secondary_y=True)

    fig.update_layout(
        barmode="stack",
        title=dict(text="Weekly Volume -- 2026", font_color=TEXT),
        paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
        font=dict(family="monospace", color=MUTED),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor=GRID),
        yaxis=dict(title="Distance (km)", gridcolor=GRID),
        yaxis2=dict(title="Elevation (m)", overlaying="y", side="right"),
        hovermode="x unified",
        margin=dict(t=60, b=40, l=60, r=60),
    )
    return fig


# -- Main ---------------------------------------------------------------------
if __name__ == "__main__":
    print("Fetching Strava activities...")
    token = get_access_token()
    activities = fetch_activities(token, pages=2)
    print(f"Fetched {len(activities)} activities")

    day_tss = compute_day_tss(activities)

    # Start PMC from earliest activity date
    start = min(datetime.strptime(d, "%Y-%m-%d").date() for d in day_tss)
    pmc   = compute_pmc(day_tss, start, RACE_DATE)
    weeks = weekly_summary(activities)

    # Save data
    with open("training_analytics.json", "w") as f:
        json.dump({"lthr": LTHR, "race_date": str(RACE_DATE),
                   "race_name": RACE_NAME, "pmc": pmc, "weekly": weeks}, f, indent=2)
    print("Saved training_analytics.json")

    # Plot
    pmc_fig    = plot_pmc(pmc)
    weekly_fig = plot_weekly([w for w in weeks if w["week"] >= "2026-01-01"])

    pmc_fig.write_html("pmc.html")
    weekly_fig.write_html("weekly_volume.html")
    print("Saved pmc.html and weekly_volume.html")
    print(f"\nToday's stats (LTHR = {LTHR} bpm):")
    today_pmc = next(p for p in reversed(pmc) if p["date"] <= str(date.today()))
    print(f"  CTL (Fitness): {today_pmc['ctl']:.1f}")
    print(f"  ATL (Fatigue): {today_pmc['atl']:.1f}")
    print(f"  TSB (Form):    {today_pmc['tsb']:+.1f}")
    print(f"  Weeks to race: {(RACE_DATE - date.today()).days // 7}")
