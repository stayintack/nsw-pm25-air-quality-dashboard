"""Clean NSW PM2.5 data for the personal dashboard project.

Inputs (data/raw/, or a folder given as the first argument), extracted from the NSW Air Quality Data API
(https://data.airquality.nsw.gov.au, CC BY 4.0):
  - raw_sites.csv          Site_Id, SiteName, Longitude, Latitude, Region (all 139 network sites)
  - raw_pm25_daily.csv     Site_Id, Date, Value, AirQualityCategory  (24h average derived from 1h average)
  - raw_pm25_hourly.csv    Site_Id, Date, Hour, Value, AirQualityCategory (hourly average, Sep 2026)

Outputs (data/processed/):
  - sites.csv              PM2.5 stations only, with first/last valid date and completeness
  - pm25_daily.csv         site_id, date, pm25, category (cleaned)
  - pm25_hourly.csv        site_id, datetime, pm25, category (cleaned)
  - data_quality_summary.csv  per-site quality and completeness summary

Cleaning rules:
  1. Keep only sites that report PM2.5.
  2. Drop rows with no measured value (station not operating / instrument offline).
  3. Small negative readings are instrument noise near zero: clip to 0 and flag.
  4. Category text is standardised to title case (Good, Fair, Poor, Very poor, Extremely poor).
  5. Hour h in the API is the hour ending at h (1 = 00:00–01:00); converted to a timestamp at the hour start.
"""

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
# Raw folder: data/raw by default, or the folder given on the command line, e.g. a fresh extract:
#   python clean_pm25_data.py ../data/raw/refetch_20261006_1530
RAW = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BASE / "data" / "raw"
OUT = BASE / "data" / "processed"
CAT = {
    "GOOD": "Good",
    "FAIR": "Fair",
    "POOR": "Poor",
    "VERY POOR": "Very poor",
    "EXTREMELY POOR": "Extremely poor",
}


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["Value"]).copy()
    df["clipped_negative"] = df["Value"] < 0
    df["pm25"] = df["Value"].clip(lower=0).round(2)
    df["category"] = df["AirQualityCategory"].map(CAT)
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Reading raw files from {RAW}")
    sites = pd.read_csv(RAW / "raw_sites.csv")
    daily_raw = pd.read_csv(RAW / "raw_pm25_daily.csv", parse_dates=["Date"])
    hourly_path = RAW / "raw_pm25_hourly.csv"
    hourly_raw = pd.read_csv(hourly_path, parse_dates=["Date"]) if hourly_path.exists() else None

    daily_raw = daily_raw.drop_duplicates(["Site_Id", "Date"])
    daily = clean(daily_raw)
    daily = daily.rename(columns={"Site_Id": "site_id", "Date": "date"})[
        ["site_id", "date", "pm25", "category", "clipped_negative"]
    ].sort_values(["site_id", "date"])

    hourly = None
    if hourly_raw is not None:
        hourly_raw = hourly_raw.drop_duplicates(["Site_Id", "Date", "Hour"])
        hourly = clean(hourly_raw)
        hourly["datetime"] = hourly["Date"] + pd.to_timedelta(hourly["Hour"] - 1, unit="h")
        hourly = hourly.rename(columns={"Site_Id": "site_id"})[
            ["site_id", "datetime", "pm25", "category", "clipped_negative"]
        ].sort_values(["site_id", "datetime"])

    # Per-site quality summary
    days_in_period = (daily_raw["Date"].max() - daily_raw["Date"].min()).days + 1
    q = daily_raw.groupby("Site_Id").agg(rows=("Value", "size"), valid_days=("Value", "count"))
    v = daily.groupby("site_id").agg(
        first_valid=("date", "min"),
        last_valid=("date", "max"),
        negatives_clipped=("clipped_negative", "sum"),
        mean_pm25=("pm25", "mean"),
        max_pm25=("pm25", "max"),
    )
    q = q.join(v, how="left")
    q["completeness_pct"] = (q["valid_days"] / days_in_period * 100).round(1)
    q = q.reset_index().rename(columns={"Site_Id": "site_id"})

    pm_sites = sites[sites["Site_Id"].isin(q.loc[q["valid_days"] > 0, "site_id"])]
    pm_sites = pm_sites.rename(
        columns={
            "Site_Id": "site_id",
            "SiteName": "site_name",
            "Longitude": "lon",
            "Latitude": "lat",
            "Region": "region",
        }
    )
    pm_sites["site_name"] = pm_sites["site_name"].str.title()
    pm_sites = pm_sites.merge(q[["site_id", "first_valid", "last_valid", "completeness_pct"]], on="site_id")
    q = q.merge(pm_sites[["site_id", "site_name", "region"]], on="site_id", how="left")

    outputs = [("sites.csv", pm_sites), ("pm25_daily.csv", daily)]
    if hourly is not None:
        outputs.append(("pm25_hourly.csv", hourly))
    for name, frame in outputs:
        frame.to_csv(OUT / name, index=False)
    q.to_csv(OUT / "data_quality_summary.csv", index=False)

    print(f"Sites with PM2.5: {len(pm_sites)} of {len(sites)}")
    print(
        f"Daily: {len(daily_raw):,} raw rows -> {len(daily):,} valid "
        f"({len(daily_raw) - len(daily):,} missing; {int(daily['clipped_negative'].sum())} negatives clipped)"
    )
    if hourly is not None:
        print(f"Hourly: {len(hourly_raw):,} raw rows -> {len(hourly):,} valid")
    print(f"Daily period: {daily['date'].min():%Y-%m-%d} to {daily['date'].max():%Y-%m-%d}")
    print(daily["category"].value_counts().to_string())


if __name__ == "__main__":
    sys.exit(main())
