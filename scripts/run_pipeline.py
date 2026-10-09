"""Run the end-to-end PM2.5 data pipeline and validate the dashboard.

    python scripts/run_pipeline.py                  # fresh API download (typically 10–15 minutes)
    python scripts/run_pipeline.py --use-included   # offline: use the raw files included with this repository

The five stages are data collection, cleaning and quality summaries, suburb lookup generation,
health-advice table generation, and pytest validation. The pipeline compares the processed-data
summary before and after the run, then prints the dashboard launch instructions.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
SCRIPTS, RAW, PROCESSED = BASE / "scripts", BASE / "data" / "raw", BASE / "data" / "processed"
DASH = BASE / "dashboard"
ENV = {
    **os.environ,
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}  # safe output on Chinese-locale Windows


def step(title, args):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)
    t = time.time()
    code = subprocess.call([sys.executable, *map(str, args)], env=ENV, cwd=BASE)
    if code != 0:
        hint = (
            (
                "\nNo internet, or the NSW API is busy? Try again later, or run offline with:\n"
                "    python scripts/run_pipeline.py --use-included"
            )
            if "Step 1" in title
            else ""
        )
        sys.exit(
            f"\nSTOPPED: '{title}' failed (exit code {code}). Read the message above, fix it, and run again.{hint}"
        )
    print(f"-- done in {time.time() - t:.0f} s", flush=True)


def summary():
    """Row counts etc. of the processed files, to compare before/after."""
    out = {}
    try:
        d = pd.read_csv(PROCESSED / "pm25_daily.csv", parse_dates=["date"])
        h = pd.read_csv(PROCESSED / "pm25_hourly.csv")
        s = pd.read_csv(PROCESSED / "suburbs.csv")
        out = {
            "PM2.5 stations": d["site_id"].nunique(),
            "valid site-days": len(d),
            "first date": f"{d['date'].min():%Y-%m-%d}",
            "last date": f"{d['date'].max():%Y-%m-%d}",
            "valid site-hours": len(h),
            "suburbs": len(s),
        }
        out.update({f"days {c}": n for c, n in d["category"].value_counts().items()})
    except FileNotFoundError:
        pass
    return out


def main():
    use_included = "--use-included" in sys.argv
    print(f"Python {sys.version.split()[0]} at {sys.executable}\nProject folder: {BASE}")
    before = summary()

    if use_included:
        raw_folder = RAW
        print("\nStep 1 skipped (--use-included): using the raw files extracted on 6 Oct 2026.")
    else:
        step(
            "Step 1/5  Download PM2.5 data from the NSW Air Quality Data API (10–15 minutes)",
            [SCRIPTS / "fetch_pm25_data.py"],
        )
        raw_folder = max(RAW.glob("refetch_*"), key=lambda p: p.stat().st_mtime)
    step("Step 2/5  Clean the PM2.5 data", [SCRIPTS / "clean_pm25_data.py", raw_folder])
    step("Step 3/5  Build the suburb list (ABS ASGS 2021)", [SCRIPTS / "build_suburbs.py"])
    step("Step 4/5  Build health advice and alert thresholds", [SCRIPTS / "build_health_advice.py"])
    step("Step 5/5  Validate the dashboard", ["-m", "pytest", "-q", BASE / "tests"])

    after = summary()
    print(f"\n{'=' * 70}\nYour run compared with the data that was in the folder before\n{'=' * 70}")
    print(f"{'':22s}{'before':>14s}{'your run':>14s}")
    for k in after:
        b, a = before.get(k, "-"), after[k]
        flag = "" if str(b) == str(a) else "   <- different"
        print(f"{k:22s}{str(b):>14s}{str(a):>14s}{flag}")
    print(
        "\nSmall differences after a fresh download are possible if the NSW API has revised its data since"
        " 6 Oct 2026.\n\nAll steps finished. Start the dashboard with:\n"
        f'    cd "{DASH}"\n    python app.py\nthen open http://127.0.0.1:8050'
    )


if __name__ == "__main__":
    main()
