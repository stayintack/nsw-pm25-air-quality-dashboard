"""Collect a raw PM2.5 snapshot from the NSW Air Quality Data API.

API docs: https://data.airquality.nsw.gov.au/docs/index.html  (NSW Government, CC BY 4.0)

The requests below reproduce the included 6 Oct 2026 snapshot parameters. The complete five-stage
workflow is documented in the root README.

Notes on the API (learned during extraction):
  - get_Observations is a POST; EndDate is EXCLUSIVE (to include 31 Dec, end on 1 Jan).
  - Large requests are slow (~40 s/year of daily data) and hourly requests for all sites at once
    return HTTP 502, so hourly data is requested one site at a time.

Usage:  python fetch_pm25_data.py   (writes CSVs to ../data/raw/refetch_<date>/; originals untouched)
Needs:  pandas, requests
"""

import sys
import time
from pathlib import Path

print("fetch_pm25_data.py started — full run takes about 10–15 minutes.", flush=True)
try:
    import pandas as pd
    import requests
except ImportError as e:
    sys.exit(f"Missing package: {e.name}. Install it with: python -m pip install pandas requests")

API = "https://data.airquality.nsw.gov.au/api/Data"
# Writes to a new dated subfolder so the original 6 Oct raw files are never overwritten.
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / f"refetch_{time.strftime('%Y%m%d_%H%M')}"
DAILY = {
    "Categories": ["Averages"],
    "SubCategories": ["Daily"],
    "Frequency": ["24h average derived from 1h average"],
}
HOURLY = {"Categories": ["Averages"], "SubCategories": ["Hourly"], "Frequency": ["Hourly average"]}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def observations(sites, start, end, kind, retries=4):
    body = {
        "Parameters": ["PM2.5"],
        "Sites": [int(s) for s in sites],
        "StartDate": start,
        "EndDate": end,
        **kind,
    }
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(f"{API}/get_Observations", json=body, timeout=180)
            if r.ok:
                return r.json()
            log(f"  HTTP {r.status_code}, retry {attempt}/{retries}")
        except requests.RequestException as e:
            log(f"  network error ({e.__class__.__name__}), retry {attempt}/{retries}")
        time.sleep(3)
    raise RuntimeError(f"API request failed after {retries} attempts: {start}–{end}")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    log(f"Output folder: {RAW}")

    # 1. Site metadata (all network sites)
    log("Downloading site list ...")
    sites = pd.DataFrame(requests.get(f"{API}/get_SiteDetails", timeout=60).json())
    sites[["Site_Id", "SiteName", "Longitude", "Latitude", "Region"]].to_csv(RAW / "raw_sites.csv", index=False)
    ids = sites["Site_Id"].tolist()
    log(f"  {len(ids)} sites saved to raw_sites.csv")

    # 2. Daily PM2.5, 1 Jan 2019 – 30 Sep 2026, one calendar year per request
    rows = []
    for year in range(2019, 2027):
        log(f"Downloading daily PM2.5 for {year} (about 40 s per year) ...")
        end = "2026-10-01" if year == 2026 else f"{year + 1}-01-01"
        for x in observations(ids, f"{year}-01-01", end, DAILY):
            rows.append([x["Site_Id"], x["Date"], x["Value"], x["AirQualityCategory"]])
        log(f"  {year} done, {len(rows):,} rows so far")
    daily = pd.DataFrame(rows, columns=["Site_Id", "Date", "Value", "AirQualityCategory"])
    daily.to_csv(RAW / "raw_pm25_daily.csv", index=False)

    # 3. Hourly PM2.5, September 2026, PM2.5 sites only, one site per request
    pm_sites = daily.dropna(subset=["Value"])["Site_Id"].unique()
    rows = []
    for i, sid in enumerate(pm_sites, 1):
        log(f"Downloading hourly PM2.5, site {sid} ({i}/{len(pm_sites)}) ...")
        for x in observations([sid], "2026-09-01", "2026-10-01", HOURLY):
            rows.append([x["Site_Id"], x["Date"], x["Hour"], x["Value"], x["AirQualityCategory"]])
    pd.DataFrame(rows, columns=["Site_Id", "Date", "Hour", "Value", "AirQualityCategory"]).to_csv(
        RAW / "raw_pm25_hourly.csv", index=False
    )
    log(f"Finished: sites {len(sites)}, daily rows {len(daily):,}, hourly rows {len(rows):,}")


if __name__ == "__main__":
    main()
