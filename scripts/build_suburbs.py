"""Build suburbs.csv for the suburb/postcode search and IDW estimates.

Input  (data/raw/raw_nsw_suburbs_abs_sal2021.csv), produced on 6 Oct 2026 from the ABS ArcGIS services
       ASGS Edition 3 (2021) Suburbs and Localities (SAL) and Postal Areas (POA), CC BY 4.0
       (https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/SAL/MapServer and .../POA/MapServer):
         - one row per NSW suburb/locality (4,542 of 4,544; 2 non-spatial codes have no geometry)
         - lat/lon = area-weighted centroid of the locality's largest polygon (simplified to ~0.005°);
           if that centroid fell outside the polygon, a boundary vertex was used instead
         - postcode = the 2021 Postal Area containing that point (blank for 33 offshore/coastal points)
Output (data/processed/suburbs.csv):
         suburb, postcode, lat, lon, sal_code
"""

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RAW = BASE / "data" / "raw" / "raw_nsw_suburbs_abs_sal2021.csv"
OUT = BASE / "data" / "processed" / "suburbs.csv"


def main():
    df = pd.read_csv(RAW, dtype={"sal_code_2021": str, "postcode_poa2021": str})
    df = df.rename(
        columns={
            "sal_name_2021": "suburb",
            "postcode_poa2021": "postcode",
            "sal_code_2021": "sal_code",
        }
    )
    df["suburb"] = df["suburb"].str.strip()
    df["postcode"] = df["postcode"].fillna("").str.zfill(4).replace("0000", "")
    df = df.dropna(subset=["lat", "lon"])
    # sanity check: every point must fall inside NSW's bounding box
    inside = df["lat"].between(-37.6, -28.1) & df["lon"].between(140.9, 159.2)
    df = df[inside].sort_values("suburb")[["suburb", "postcode", "lat", "lon", "sal_code"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(
        f"{len(df):,} suburbs written; {int((df['postcode'] == '').sum())} without postcode; "
        f"{df['suburb'].duplicated().sum()} duplicate names"
    )


if __name__ == "__main__":
    main()
