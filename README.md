# Bromont 80K — Training Analytics

Performance Management Chart (PMC) pipeline for my Bromont 80K ultra marathon build, computed from raw Strava heart rate data.

## Model

The same model that powers Garmin Training Status, Strava Fitness & Freshness, and Wahoo SYSTM:

```
hrTSS = duration_hrs × (avg_HR / LTHR)² × 100

ATL[t] = ATL[t-1] + (TSS[t] - ATL[t-1]) × (1 - e^{-1/7})   # 7-day EMA  (Fatigue)
CTL[t] = CTL[t-1] + (TSS[t] - CTL[t-1]) × (1 - e^{-1/42})  # 42-day EMA (Fitness)
TSB[t] = CTL[t] - ATL[t]                                      # Form
```

**LTHR = 175 bpm** — estimated from Ottawa Half-Marathon average heart rate (177 bpm).

## References

- Banister et al. (1975) — original impulse-response model
- Coggan (2003) — PMC implementation for cycling
- Strava Fitness & Freshness (same model, different UI)

## Current stats (as of April 24, 2026)

| Metric | Value |
|--------|-------|
| CTL (Fitness) | 52.8 |
| ATL (Fatigue) | 47.6 |
| TSB (Form) | +5.1 |
| Weeks to race | 25 |
| Race date | Oct 17, 2026 |

## Usage

```bash
pip install requests plotly

export STRAVA_CLIENT_ID=your_id
export STRAVA_CLIENT_SECRET=your_secret
export STRAVA_REFRESH_TOKEN=your_token

python analysis.py
# → training_analytics.json
# → pmc.html
# → weekly_volume.html
```

## Output

- `training_analytics.json` — daily PMC values, weekly aggregates, long run log
- `pmc.html` — interactive Plotly PMC chart (CTL / ATL / TSB)
- `weekly_volume.html` — stacked bar chart of weekly run + ride volume

## Race

**Bromont 80K Ultra** — October 17, 2026, Bromont, QC
