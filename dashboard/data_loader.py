"""Shared data access for dashboard panels.

All panels load data through this module from the canonical processed-data directory.

    load_sites()      49 PM2.5 monitoring stations
    load_daily()      daily PM2.5 (24-h average) per station, 2019-01-01 .. 2026-09-30
    load_hourly()     hourly PM2.5 per station, September 2026
    load_suburbs()    4,542 NSW suburbs with postcode and centroid
    load_health_advice()  advice text + pictogram keys per profile and category
    load_thresholds()     default alert level per profile
    latest_date()     last date with data ("Data as of")
    category_for()    official NSW Air Quality Category for a PM2.5 value
    estimate_at()     PM2.5 at any point: nearby station reading or IDW estimate
    estimate_series() daily PM2.5 series at any point (for the trend chart)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

# Official NSW Air Quality Categories for PM2.5 (Air Quality NSW, "Air quality categories"), µg/m³.
#   24-h: Good <16.75 · Fair 16.75–25.0 · Poor 25.001–37.5 · Very poor 37.501–50.0 · Extremely poor >50
#   1-h : Good <25 · Fair 25–<50 · Poor 50–<100 · Very poor 100–<300 · Extremely poor ≥300
# Each entry: (upper bound, inclusive?, category). Values above the last bound are "Extremely poor".
AQC_BOUNDS = {
    "24h": [
        (16.75, False, "Good"),
        (25.0, True, "Fair"),
        (37.5, True, "Poor"),
        (50.0, True, "Very poor"),
    ],
    "1h": [
        (25.0, False, "Good"),
        (50.0, False, "Fair"),
        (100.0, False, "Poor"),
        (300.0, False, "Very poor"),
    ],
}
CATEGORIES = ["Good", "Fair", "Poor", "Very poor", "Extremely poor"]

# IDW settings shared by point and time-series estimates.
SNAP_KM = 2.0  # a station this close is reported as a measurement, not an estimate
MAX_KM = 50.0  # stations further than this are not used
MAX_STATIONS = 5  # nearest stations used in the weighted average
POWER = 2  # inverse-distance power (standard IDW)


# ---------- loading (cached: each file is read once per server process) ----------
@lru_cache(maxsize=None)
def load_sites() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "sites.csv", parse_dates=["first_valid", "last_valid"])


@lru_cache(maxsize=None)
def load_daily() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "pm25_daily.csv", parse_dates=["date"])


@lru_cache(maxsize=None)
def load_hourly() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "pm25_hourly.csv", parse_dates=["datetime"])


@lru_cache(maxsize=None)
def load_suburbs() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "suburbs.csv", dtype={"postcode": str, "sal_code": str}).fillna({"postcode": ""})


@lru_cache(maxsize=None)
def load_health_advice() -> pd.DataFrame:
    """profile, category, advice, icon, source — 6 profiles x 5 categories."""
    return pd.read_csv(DATA_DIR / "health_advice.csv")


@lru_cache(maxsize=None)
def load_thresholds() -> pd.DataFrame:
    """profile, default_threshold_ugm3, source — default 24-h alert level per health profile."""
    return pd.read_csv(DATA_DIR / "thresholds.csv")


def default_threshold(profile: str) -> float | None:
    t = load_thresholds()
    row = t[t["profile"] == profile]
    return None if row.empty else float(row["default_threshold_ugm3"].iloc[0])


def latest_date() -> pd.Timestamp:
    return load_daily()["date"].max()


# ---------- categories ----------
def category_for(value: float | None, period: str = "24h") -> str | None:
    """Map a PM2.5 concentration to its official NSW category ('24h' or '1h' thresholds)."""
    if value is None or pd.isna(value):
        return None
    for upper, inclusive, name in AQC_BOUNDS[period]:
        if value < upper or (inclusive and value == upper):
            return name
    return "Extremely poor"


# ---------- distance and IDW ----------
def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km; works element-wise on numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def _stations_with_reading(date) -> pd.DataFrame:
    day = load_daily()
    day = day[day["date"] == pd.Timestamp(date)][["site_id", "pm25"]]
    return load_sites().merge(day, on="site_id")


def estimate_at(lat: float, lon: float, date=None) -> dict:
    """PM2.5 (24-h average) at a point on a given date.

    Returns a dict:
      value, category      the reading/estimate (None if no station within MAX_KM)
      estimated            False if a station is within SNAP_KM, else True
      method               'station' | 'idw' | 'none'
      contributors         list of {site_id, site_name, km, pm25, weight} used
      nearest_km           distance to the nearest station with a reading
    """
    date = pd.Timestamp(date) if date is not None else latest_date()
    st = _stations_with_reading(date)
    if st.empty:
        return {
            "value": None,
            "category": None,
            "estimated": True,
            "method": "none",
            "contributors": [],
            "nearest_km": None,
            "date": date,
        }
    st = st.assign(km=haversine_km(lat, lon, st["lat"].to_numpy(), st["lon"].to_numpy())).sort_values("km")
    nearest = float(st["km"].iloc[0])

    if nearest <= SNAP_KM:
        row = st.iloc[0]
        return {
            "value": float(row["pm25"]),
            "category": category_for(row["pm25"]),
            "estimated": False,
            "method": "station",
            "nearest_km": nearest,
            "date": date,
            "contributors": [
                {
                    "site_id": int(row["site_id"]),
                    "site_name": row["site_name"],
                    "km": nearest,
                    "pm25": float(row["pm25"]),
                    "weight": 1.0,
                }
            ],
        }

    use = st[st["km"] <= MAX_KM].head(MAX_STATIONS)
    if use.empty:
        return {
            "value": None,
            "category": None,
            "estimated": True,
            "method": "none",
            "contributors": [],
            "nearest_km": nearest,
            "date": date,
        }

    w = 1.0 / use["km"].to_numpy() ** POWER
    w = w / w.sum()
    value = float(np.dot(w, use["pm25"].to_numpy()))
    contributors = [
        {
            "site_id": int(r.site_id),
            "site_name": r.site_name,
            "km": float(r.km),
            "pm25": float(r.pm25),
            "weight": float(wi),
        }
        for r, wi in zip(use.itertuples(), w)
    ]
    return {
        "value": value,
        "category": category_for(value),
        "estimated": True,
        "method": "idw",
        "contributors": contributors,
        "nearest_km": nearest,
        "date": date,
    }


def estimate_series(lat: float, lon: float, start, end) -> pd.DataFrame:
    """Daily series (date, pm25, category, estimated) at a point, using the same rules as estimate_at.

    Vectorised over dates (one distance calculation, then a small loop over days), so a year
    of estimates takes milliseconds; results are identical to calling estimate_at day by day.
    """
    dates = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")
    sites = load_sites()
    km = pd.Series(
        haversine_km(lat, lon, sites["lat"].to_numpy(), sites["lon"].to_numpy()),
        index=sites["site_id"],
    ).sort_values()
    day = load_daily()
    day = day[day["date"].between(dates[0], dates[-1])]
    grid = day.pivot_table(index="date", columns="site_id", values="pm25").reindex(index=dates, columns=km.index)
    values, estimated = [], []
    for row in grid.to_numpy():
        have = ~np.isnan(row)
        if not have.any():
            values.append(np.nan)
            estimated.append(True)
            continue
        d, v = km.to_numpy()[have], row[have]  # already sorted by distance
        if d[0] <= SNAP_KM:
            values.append(float(v[0]))
            estimated.append(False)
            continue
        use = d <= MAX_KM
        d, v = d[use][:MAX_STATIONS], v[use][:MAX_STATIONS]
        if len(d) == 0:
            values.append(np.nan)
            estimated.append(True)
            continue
        w = 1.0 / d**POWER
        values.append(float(np.dot(w / w.sum(), v)))
        estimated.append(True)
    out = pd.DataFrame({"date": dates, "pm25": values, "estimated": estimated})
    out["category"] = [category_for(v) for v in out["pm25"]]
    return out[["date", "pm25", "category", "estimated"]]


if __name__ == "__main__":  # quick self-check: python data_loader.py
    print(
        f"{len(load_sites())} stations, {len(load_daily()):,} daily rows, "
        f"{len(load_hourly()):,} hourly rows, {len(load_suburbs()):,} suburbs; data as of {latest_date():%d %b %Y}"
    )
    for name in ["Parramatta", "Katoomba", "Broken Hill", "Randwick"]:
        s = load_suburbs().query("suburb == @name").iloc[0]
        e = estimate_at(s.lat, s.lon)
        val = f"{e['value']:.1f} µg/m³ ({e['category']})" if e["value"] is not None else "no estimate"
        print(
            f"  {name:12s} {e['method']:7s} {val}; nearest station {e['nearest_km']:.1f} km; "
            f"{len(e['contributors'])} station(s) used"
        )
