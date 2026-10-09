"""NSW Air Quality & Health Alert Dashboard.

Run:   python app.py     then open http://127.0.0.1:8050

This module creates the app and shared Stores, places each panel's layout in the page grid,
and registers each panel's callbacks. Panel code lives in components/.
"""

import pandas as pd
from dash import Dash, dcc, html

import config
import data_loader as dl
from components import advice_panel, alert_panel, map_panel, profile_panel, trend_panel

PANELS = {
    "profile": profile_panel,
    "map": map_panel,
    "trend": trend_panel,
    "advice": advice_panel,
    "alerts": alert_panel,
}


def _default_location():
    sub = dl.load_suburbs()
    row = sub[sub["suburb"] == config.DEFAULT_SUBURB].iloc[0]
    return {
        "kind": "suburb",
        "site_id": None,
        "name": row["suburb"],
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
        "estimated": True,
    }


def _area(panel_name):
    """Wrap a panel's layout in its page-grid area."""
    return html.Div(className=f"area-{panel_name}", children=PANELS[panel_name].layout())


asof = pd.Timestamp(config.DATA_AS_OF)

app = Dash(__name__, title=config.APP_TITLE, suppress_callback_exceptions=True)
server = app.server  # lets the app be deployed with a WSGI server if needed

# Page language (WCAG 3.1.1) so screen readers use Australian English pronunciation; Dash's default page has no lang.
app.index_string = app.index_string.replace("<html>", '<html lang="en-AU">', 1)

app.layout = html.Div(
    [
        html.A("Skip to main content", href="#main", className="skip-link"),
        # ---- shared state ----
        dcc.Store(
            id="store-profile",
            storage_type="local",
            data={"profile": config.DEFAULT_PROFILE, "threshold": None},
        ),
        dcc.Store(id="store-location", storage_type="memory", data=_default_location()),
        dcc.Store(id="store-alert-log", storage_type="local", data={}),
        # ---- page ----
        html.Header(
            className="app-header",
            children=[
                html.H1(config.APP_TITLE),
                html.Span(f"Data as of {asof.day} {asof:%b %Y} · daily PM2.5", className="asof"),
            ],
        ),
        html.Main(
            id="main",
            className="app-main",
            children=[
                _area("profile"),
                _area("map"),
                html.Div(className="area-right", children=[_area("trend"), _area("advice")]),
                _area("alerts"),
                html.Footer(
                    className="app-footer",
                    children=[
                        f"Source: {config.DATA_SOURCE}. Suburb locations: ABS ASGS 2021 (CC BY 4.0). ",
                        'Estimated values use inverse-distance weighting and are labelled "Estimated". '
                        "This dashboard gives general guidance and does not replace medical advice.",
                    ],
                ),
            ],
        ),
    ]
)

for panel in PANELS.values():
    panel.register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True)
