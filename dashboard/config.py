"""Shared dashboard labels, thresholds, and visual tokens."""

APP_TITLE = "NSW Air Quality & Health Alert Dashboard"
DATA_AS_OF = "2026-09-30"  # last day in the bundled data; shown as "Data as of 30 Sep 2026"
DATA_SOURCE = "NSW Air Quality Data API (NSW Government, CC BY 4.0)"

# ---------- air-quality categories (official NSW order) ----------
# Colours checked with a colour-vision-deficiency validator: they pass the lightness, chroma and
# normal-vision separation checks; Good/Fair is weaker for protanopia (ΔE 8) and Fair has low contrast
# on white, so a category is ALWAYS shown with its name as text (legend, chip, label), never colour alone.
# "text_on" = text colour for a label placed ON that colour; every pair is >= 4.5:1 (WCAG AA).
CATEGORY_STYLE = {
    "Good": {"color": "#1b9e4b", "label": "Good", "text_on": "#1f1f1f", "rank": 1},
    "Fair": {"color": "#e3a008", "label": "Fair", "text_on": "#1f1f1f", "rank": 2},
    "Poor": {"color": "#e8590c", "label": "Poor", "text_on": "#1f1f1f", "rank": 3},
    "Very poor": {"color": "#a3122a", "label": "Very poor", "text_on": "#ffffff", "rank": 4},
    "Extremely poor": {
        "color": "#7b3294",
        "label": "Extremely poor",
        "text_on": "#ffffff",
        "rank": 5,
    },
}
NO_DATA_COLOR = "#9e9e9e"

# ---------- health profiles ----------
PROFILES = {
    "general": "General public",
    "asthma_copd": "Asthma / COPD",
    "heart_disease": "Heart disease",
    "pregnancy": "Pregnancy",
    "children": "Children",
    "older_adults": "Older adults (65+)",
}
DEFAULT_PROFILE = "general"

# ---------- default location on first visit ----------
DEFAULT_SUBURB = "Parramatta"

# ---------- theme tokens (match the draft design: navy header, teal accents) ----------
THEME = {
    "navy": "#1f3a5f",  # header bar
    "teal": "#0f766e",  # active profile chip, focus ring, primary buttons (5.5:1 on white)
    "teal_light": "#e6f4f2",
    "surface": "#ffffff",  # panel background
    "page": "#f3f5f7",  # page background
    "ink": "#1f1f1f",  # primary text (16.5:1 on white)
    "muted": "#5c6670",  # secondary text (5.9:1 on white)
    "border": "#d7dde3",
    "font": "Arial, 'Helvetica Neue', Helvetica, sans-serif",
}

# ---------- advice pictograms (assets/icons/<key>.svg) ----------
# The health-advice table uses these keys in its "icon" column (several allowed, separated by ";").
# Each pictogram is always shown with its caption as text (pictogram-first, not pictogram-only).
ICONS = {
    "outdoors_ok": "Outdoor activity is fine",
    "reduce_outdoor": "Cut down strenuous outdoor activity",
    "stay_indoors": "Stay indoors",
    "close_windows": "Close windows and doors",
    "medication": "Keep reliever medication with you",
    "see_doctor": "See a doctor if symptoms get worse",
}
