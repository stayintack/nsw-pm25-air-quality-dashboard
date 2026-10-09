"""Present source-linked, profile-specific health guidance for the selected location."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd
from dash import Input, Output, State, dcc, html

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import data_loader as dl  # noqa: E402


@lru_cache(maxsize=None)
def _advice_table() -> pd.DataFrame | None:
    """Load the profile-specific advice table through the shared data loader."""
    if hasattr(dl, "load_health_advice"):
        return dl.load_health_advice()
    path = dl.DATA_DIR / "health_advice.csv"
    return pd.read_csv(path) if path.exists() else None


def _advice_for(profile: str, category: str):
    table = _advice_table()
    if table is None:
        return None
    row = table[(table["profile"] == profile) & (table["category"] == category)]
    return None if row.empty else row.iloc[0]


def _pictograms(icon_field) -> html.Ul:
    keys = [k.strip() for k in str(icon_field).split(";") if k.strip() in config.ICONS]
    return html.Ul(
        className="advice-icons",
        children=[
            html.Li(
                className="advice-icon",
                children=[
                    html.Img(
                        src=f"/assets/icons/{k}.svg", alt="", className="advice-icon-img"
                    ),  # caption below carries meaning
                    html.Span(config.ICONS[k], className="advice-icon-caption"),
                ],
            )
            for k in keys
        ],
    )


def build_card(profile_data: dict | None, location: dict | None) -> list:
    profile = (profile_data or {}).get("profile") or config.DEFAULT_PROFILE
    prof_label = config.PROFILES.get(profile, profile)
    tailored = html.Span(f"Tailored to: {prof_label}", className="chip chip-profile")

    if not location or location.get("lat") is None:
        return [html.P("Choose a suburb or click a station to see advice."), tailored]

    est = dl.estimate_at(location["lat"], location["lon"], pd.Timestamp(config.DATA_AS_OF))
    if est["value"] is None:
        return [
            html.P(
                [
                    html.B(location["name"]),
                    ": no reliable reading nearby, so no local advice can be given. ",
                    "Check the nearest station on the map.",
                ]
            ),
            tailored,
        ]

    cat = est["category"]
    style = config.CATEGORY_STYLE[cat]
    head = html.Div(
        className="advice-head",
        children=[
            html.Span(
                style["label"],
                className="advice-category",
                style={"backgroundColor": style["color"], "color": style["text_on"]},
            ),
            html.Span(
                [html.B(f"{est['value']:.1f} µg/m³"), " PM2.5, 24-hour average"],
                className="advice-value",
            ),
            html.Span("Estimated", className="map-estimated-tag") if est["estimated"] else None,
        ],
    )

    row = _advice_for(profile, cat)
    if row is None:
        body = [
            html.P(
                f"Advice for {prof_label} when air quality is {cat} will appear here (health_advice.csv).",
                className="panel-placeholder",
            )
        ]
    else:
        body = [
            _pictograms(row["icon"]),
            html.P(row["advice"], className="advice-text"),
            html.P(f"Source: {row['source']}", className="advice-source muted"),
        ]
    return [head, *body, tailored]


def layout():
    return html.Section(
        id="advice-panel",
        className="panel",
        **{"aria-labelledby": "advice-title"},
        children=[
            html.H2("What this means for you", id="advice-title", className="panel-title"),
            html.Div(
                id="advice-card", className="advice-card"
            ),  # not live: A's status line announces updates (one message, not five)
        ],
    )


def register_callbacks(app):
    @app.callback(
        Output("advice-card", "children"),
        Output("advice-card", "className"),
        Input("store-profile", "data"),
        Input("store-location", "data"),
        State("advice-card", "className"),
    )
    def _render(profile, location, cls):
        # alternate between two identical animations so the highlight replays on every update
        pulse = "advice-card pulse-b" if cls and "pulse-a" in cls else "advice-card pulse-a"
        return build_card(profile, location), pulse


if __name__ == "__main__":
    from dash import Dash

    app = Dash(__name__, assets_folder=str(Path(__file__).resolve().parents[1] / "assets"))
    app.layout = html.Div(
        style={"maxWidth": "560px", "margin": "20px auto"},
        children=[
            dcc.Dropdown(
                id="t-profile",
                options=[{"label": v, "value": k} for k, v in config.PROFILES.items()],
                value="asthma_copd",
            ),
            dcc.Dropdown(id="t-suburb", options=["Parramatta", "Katoomba", "Broken Hill"], value="Katoomba"),
            dcc.Store(id="store-profile"),
            dcc.Store(id="store-location"),
            layout(),
        ],
    )

    @app.callback(
        Output("store-profile", "data"),
        Output("store-location", "data"),
        Input("t-profile", "value"),
        Input("t-suburb", "value"),
    )
    def _t(p, s):
        r = dl.load_suburbs().set_index("suburb").loc[s]
        return {"profile": p, "threshold": None}, {
            "kind": "suburb",
            "site_id": None,
            "name": s,
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "estimated": True,
        }

    register_callbacks(app)
    app.run(debug=True)
