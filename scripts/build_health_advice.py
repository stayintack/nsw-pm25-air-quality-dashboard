"""Build health_advice.csv and thresholds.csv.

Advice text is taken word-for-word from Air Quality NSW's activity guide (Health advice page, last updated
9 Dec 2025): 'sensitive groups' wording for the five sensitive profiles, 'everyone else' wording for the
general public. One extra profile-specific sentence is added from Air Quality NSW's bushfire smoke health
advice (asthma action plan / medication; Triple Zero for heart symptoms) and the Health advice page
(HealthDirect helpline). Icon keys match the dashboard's visual configuration.
"""

from pathlib import Path
import csv

OUT = Path(__file__).resolve().parents[1] / "data" / "processed"
SRC_GUIDE = "Air Quality NSW (2025), Health advice: activity guide"
SRC_BUSH = "Air Quality NSW, Bushfire smoke health advice"

SENSITIVE = {
    "Good": "NO CHANGE needed to your normal outdoor activities.",
    "Fair": "REDUCE outdoor physical activity if you develop symptoms such as cough or shortness of breath. "
    "Consider closing windows and doors until outdoor air quality is better.",
    "Poor": "AVOID outdoor physical activity if you develop symptoms such as cough or shortness of breath. "
    "When indoors, close windows and doors until outdoor air quality is better.",
    "Very poor": "STAY INDOORS as much as possible with windows and doors closed until outdoor air quality is better.",
    "Extremely poor": "STAY INDOORS with windows and doors closed until outdoor air quality is better "
    "and reduce indoor activity.",
}
EVERYONE = {
    "Good": "NO CHANGE needed to your normal outdoor activities.",
    "Fair": "NO CHANGE needed to your normal outdoor activities.",
    "Poor": "REDUCE outdoor physical activity if you develop symptoms such as cough or shortness of breath.",
    "Very poor": "AVOID outdoor physical activity if you develop symptoms such as cough or shortness of breath. "
    "When indoors, close windows and doors until outdoor air quality is better.",
    "Extremely poor": (
        "STAY INDOORS as much as possible with windows and doors closed until outdoor air quality is better."
    ),
}
ICONS_SENSITIVE = {
    "Good": "outdoors_ok",
    "Fair": "reduce_outdoor;close_windows",
    "Poor": "reduce_outdoor;close_windows;see_doctor",
    "Very poor": "stay_indoors;close_windows;see_doctor",
    "Extremely poor": "stay_indoors;close_windows;see_doctor",
}
ICONS_EVERYONE = {
    "Good": "outdoors_ok",
    "Fair": "outdoors_ok",
    "Poor": "reduce_outdoor",
    "Very poor": "reduce_outdoor;close_windows",
    "Extremely poor": "stay_indoors;close_windows",
}

# extra sentence per sensitive profile, shown from Fair upwards (advice changes for sensitive groups at Fair)
EXTRA = {
    "asthma_copd": (
        "Follow your Asthma Action Plan or other health action plan, and keep your medication with you.",
        "medication",
        SRC_BUSH,
    ),
    "heart_disease": (
        "Follow the treatment plan recommended by your doctor. Call Triple Zero (000) if you have "
        "trouble breathing or chest pain.",
        "",
        SRC_BUSH,
    ),
    "pregnancy": (
        "Follow the treatment plan recommended by your doctor; call the HealthDirect helpline on "
        "1800 022 222 if you are concerned.",
        "",
        SRC_GUIDE,
    ),
    "children": (
        "Infants and young children are more sensitive to air pollution: plan indoor play and watch for "
        "coughing or wheezing.",
        "",
        SRC_BUSH,
    ),
    "older_adults": (
        "People over 65 are more sensitive to air pollution: follow the treatment plan recommended by "
        "your doctor; call HealthDirect on 1800 022 222 if you are concerned.",
        "",
        SRC_GUIDE,
    ),
}
CATS = ["Good", "Fair", "Poor", "Very poor", "Extremely poor"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for cat in CATS:
        rows.append(
            {
                "profile": "general",
                "category": cat,
                "advice": EVERYONE[cat],
                "icon": ICONS_EVERYONE[cat],
                "source": SRC_GUIDE + " (everyone else)",
            }
        )
    for profile, (extra, extra_icon, extra_src) in EXTRA.items():
        for cat in CATS:
            advice, icon, source = (
                SENSITIVE[cat],
                ICONS_SENSITIVE[cat],
                SRC_GUIDE + " (sensitive groups)",
            )
            if cat != "Good":
                advice = f"{advice} {extra}"
                if extra_icon and extra_icon not in icon:
                    icon = f"{icon};{extra_icon}"
                if extra_src != SRC_GUIDE:
                    source = f"{source}; {extra_src}"
            rows.append(
                {
                    "profile": profile,
                    "category": cat,
                    "advice": advice,
                    "icon": icon,
                    "source": source,
                }
            )
    with open(OUT / "health_advice.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["profile", "category", "advice", "icon", "source"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # Default alert thresholds (24-hour PM2.5, µg/m³) = the level at which the official advice first changes:
    # sensitive groups at Fair (>= 16.75), everyone else at Poor (> 25.0).
    thr = [
        {
            "profile": "general",
            "default_threshold_ugm3": 25.0,
            "source": SRC_GUIDE + ": advice for everyone else changes at Poor (>25 µg/m³, 24-h)",
        }
    ]
    for p in EXTRA:
        thr.append(
            {
                "profile": p,
                "default_threshold_ugm3": 16.75,
                "source": SRC_GUIDE + ": advice for sensitive groups changes at Fair (>=16.75 µg/m³, 24-h)",
            }
        )
    with open(OUT / "thresholds.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["profile", "default_threshold_ugm3", "source"], lineterminator="\n")
        w.writeheader()
        w.writerows(thr)
    print(f"{len(rows)} advice rows, {len(thr)} thresholds written to {OUT}")


if __name__ == "__main__":
    main()
