"""Map NSW PM2.5 monitoring stations and location-level estimates.

Stations use their official air-quality category, with category names available in the legend and
hover labels. A selected suburb is shown as a labelled estimate connected to its contributing
stations when no monitoring station is within the measurement snap distance.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, dcc, html, no_update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow `python components/map_panel.py`
import data_loader as dl  # noqa: E402

# ---------- styling from the shared configuration ----------
import config  # noqa: E402

CATEGORY_STYLE = config.CATEGORY_STYLE
NO_DATA_COLOR = "#9e9e9e"
INK = "#1f1f1f"
NSW_VIEW = {"center": {"lat": -33.2, "lon": 149.5}, "zoom": 5.2}
# Free basemap with no API key; it needs internet. Set MAP_STYLE=white-bg to run fully offline.
MAP_STYLE = os.environ.get("MAP_STYLE", "carto-positron")


def _station_table(date) -> pd.DataFrame:
    """Stations with their reading on `date` (pm25/category NaN when the station had no reading)."""
    day = dl.load_daily()
    day = day[day["date"] == pd.Timestamp(date)][["site_id", "pm25", "category"]]
    return dl.load_sites().merge(day, on="site_id", how="left")


def build_figure(location: dict | None, date=None) -> go.Figure:
    date = pd.Timestamp(date) if date is not None else dl.latest_date()
    st = _station_table(date)
    fig = go.Figure()

    # 1. dark halo under every station: a ring that keeps light colours visible on the basemap
    fig.add_trace(
        go.Scattermap(
            lat=st["lat"],
            lon=st["lon"],
            mode="markers",
            hoverinfo="skip",
            marker={"size": 15, "color": INK},
            showlegend=False,
        )
    )

    # 2. one trace per category, in fixed order, so the legend lists the categories in order
    for cat, style in CATEGORY_STYLE.items():
        sub = st[st["category"] == cat]
        fig.add_trace(
            go.Scattermap(
                lat=sub["lat"],
                lon=sub["lon"],
                mode="markers",
                name=style["label"],
                showlegend=False,
                marker={"size": 11, "color": style["color"]},
                customdata=sub[["site_id", "site_name", "pm25", "category", "region"]].to_numpy(),
                hovertemplate=(
                    "<b>%{customdata[1]}</b> (%{customdata[4]})<br>"
                    "PM2.5 24-h average: %{customdata[2]:.1f} µg/m³<br>"
                    "Category: <b>%{customdata[3]}</b><br>Measured · click for trend<extra></extra>"
                ),
            )
        )
    missing = st[st["pm25"].isna()]
    if not missing.empty:
        fig.add_trace(
            go.Scattermap(
                lat=missing["lat"],
                lon=missing["lon"],
                mode="markers",
                name="No reading",
                showlegend=False,
                marker={"size": 9, "color": NO_DATA_COLOR},
                customdata=missing[["site_id", "site_name"]].to_numpy(),
                hovertemplate="<b>%{customdata[1]}</b><br>No reading on this day<extra></extra>",
            )
        )

    view = dict(NSW_VIEW)
    if location and location.get("lat") is not None:
        lat, lon = location["lat"], location["lon"]
        view = {"center": {"lat": lat, "lon": lon}, "zoom": 9}
        est = dl.estimate_at(lat, lon, date)
        if est["method"] == "idw":
            # lines from the estimate to each station used (the IDW "recipe", visible)
            lats, lons = [], []
            for c in est["contributors"]:
                s = st[st["site_id"] == c["site_id"]].iloc[0]
                lats += [lat, s["lat"], None]
                lons += [lon, s["lon"], None]
            fig.add_trace(
                go.Scattermap(
                    lat=lats,
                    lon=lons,
                    mode="lines",
                    hoverinfo="skip",
                    line={"width": 1.5, "color": "#555555"},
                    showlegend=False,
                )
            )
        if location.get("kind") == "suburb":
            colour = CATEGORY_STYLE.get(est["category"], {}).get("color", NO_DATA_COLOR)
            # short map label; the full value, category and method are in the summary below the map
            if est["value"] is None:
                label = f"{location['name']}: no estimate"
            elif est["estimated"]:
                label = f"{location['name']} (Estimated)"
            else:
                label = location["name"]
            # put the label on the side away from the stations so it does not sit on the lines
            east = (
                sum(
                    c["weight"] * (st.loc[st["site_id"] == c["site_id"], "lon"].iloc[0] - lon)
                    for c in est["contributors"]
                )
                if est["contributors"]
                else -1
            )
            text_pos = "middle left" if east > 0 else "middle right"
            fig.add_trace(
                go.Scattermap(
                    lat=[lat],
                    lon=[lon],
                    mode="markers",
                    hoverinfo="skip",
                    marker={"size": 22, "color": INK},
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Scattermap(
                    lat=[lat],
                    lon=[lon],
                    mode="markers+text",
                    text=[label],
                    textposition=text_pos,
                    textfont={"size": 13, "color": INK},
                    marker={"size": 16, "color": colour},
                    name="Your location",
                    showlegend=False,
                    hovertemplate=label + "<extra></extra>",
                )
            )
        else:  # a selected station: emphasise it with a larger ring
            fig.add_trace(
                go.Scattermap(
                    lat=[lat],
                    lon=[lon],
                    mode="markers+text",
                    text=[location["name"]],
                    textposition="top right",
                    textfont={"size": 13, "color": INK},
                    marker={"size": 24, "color": INK, "opacity": 0.35},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    fig.update_layout(
        map={"style": MAP_STYLE, **view},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        showlegend=False,  # the key is an HTML legend under the map (always lists all five categories)
        hoverlabel={"bgcolor": "white", "font_size": 13},
        uirevision=str(location.get("name") if location else "nsw"),  # keep user zoom until location changes
    )
    return fig


def build_summary(location: dict | None, date=None) -> list:
    """Plain-language description of what the map shows (read by screen readers)."""
    date = pd.Timestamp(date) if date is not None else dl.latest_date()
    asof = f"{date.day} {date:%b %Y}"
    if not location or location.get("lat") is None:
        st = _station_table(date)
        counts = st["category"].value_counts()
        parts = [f"{counts.get(c, 0)} {c}" for c in CATEGORY_STYLE if counts.get(c, 0)]
        return [
            html.P(f"{st['pm25'].notna().sum()} stations reported on {asof}: " + ", ".join(parts) + "."),
            html.P("Search a suburb or click a station to see local air quality.", className="map-hint"),
        ]

    est = dl.estimate_at(location["lat"], location["lon"], date)
    name = location["name"]
    if est["method"] == "none":
        near = f"{est['nearest_km']:.0f} km" if est["nearest_km"] is not None else "too far"
        return [
            html.P([html.B(name), f": no reliable estimate on {asof}."]),
            html.P(
                f"The nearest station with a reading is {near} away (limit {dl.MAX_KM:.0f} km). "
                "Regional NSW has few monitoring stations.",
                className="map-caveat",
            ),
        ]
    head = [html.B(name), f" · {asof}: PM2.5 {est['value']:.1f} µg/m³ — ", html.B(est["category"])]
    if est["method"] == "station":
        c = est["contributors"][0]
        detail = f"Measured at {c['site_name']} station ({c['km']:.1f} km away)."
        return [html.P(head), html.P(detail)]
    used = ", ".join(f"{c['site_name']} {c['km']:.0f} km ({c['weight'] * 100:.0f}%)" for c in est["contributors"])
    return [
        html.P(head + [html.Span(" Estimated", className="map-estimated-tag")]),
        html.P(f"Estimated from {len(est['contributors'])} station(s) by inverse-distance weighting: {used}."),
        html.P(
            "Estimates ignore terrain and weather and may be less reliable during smoke events.",
            className="map-caveat",
        ),
    ]


def legend():
    """Always lists all five categories in order, plus the two special markers, as text + swatch."""

    def item(color, text, ring=True, big=False):
        size = "16px" if big else "12px"
        return html.Li(
            className="map-legend-item",
            children=[
                html.Span(
                    className="map-swatch",
                    **{"aria-hidden": "true"},
                    style={
                        "backgroundColor": color,
                        "width": size,
                        "height": size,
                        "borderRadius": "50%",
                        "display": "inline-block",
                        "border": f"2px solid {INK}" if ring else "none",
                        "marginRight": "6px",
                        "verticalAlign": "middle",
                    },
                ),
                html.Span(text),
            ],
        )

    items = [item(st["color"], st["label"]) for st in CATEGORY_STYLE.values()]
    items += [
        item(NO_DATA_COLOR, "No reading"),
        item("#ffffff", "Your location (estimate joined to stations used)", big=True),
    ]
    return html.Div(
        className="map-legend",
        children=[
            html.Span("Air quality category, 24-hour PM2.5:", className="map-legend-title"),
            html.Ul(
                items,
                style={
                    "listStyle": "none",
                    "display": "flex",
                    "flexWrap": "wrap",
                    "gap": "14px",
                    "padding": 0,
                    "margin": "4px 0 0 0",
                },
            ),
        ],
    )


def layout():
    return html.Section(
        id="map-panel",
        className="panel",
        **{"aria-labelledby": "map-title"},
        children=[
            html.H2("Air quality near you", id="map-title", className="panel-title"),
            dcc.Graph(
                id="map-graph",
                figure=build_figure(None),
                config={"displayModeBar": False, "scrollZoom": True},
                style={"height": "460px"},
            ),
            legend(),
            html.Div(
                id="map-summary", className="map-summary", children=build_summary(None)
            ),  # read on demand; A announces updates
        ],
    )


def register_callbacks(app):
    @app.callback(Output("map-graph", "figure"), Output("map-summary", "children"), Input("store-location", "data"))
    def _render(location):
        return build_figure(location), build_summary(location)

    @app.callback(
        Output("store-location", "data", allow_duplicate=True),
        Input("map-graph", "clickData"),
        prevent_initial_call=True,
    )
    def _click_station(click):
        if not click or not click.get("points"):
            return no_update
        cd = click["points"][0].get("customdata")
        if cd is None:  # clicked the estimate point or a line, not a station
            return no_update
        site = dl.load_sites().set_index("site_id").loc[int(cd[0])]
        return {
            "kind": "station",
            "site_id": int(cd[0]),
            "name": site["site_name"],
            "lat": float(site["lat"]),
            "lon": float(site["lon"]),
            "estimated": False,
        }


if __name__ == "__main__":
    # Standalone preview with a minimal location control.
    from dash import Dash

    subs = dl.load_suburbs()
    app = Dash(__name__)
    app.layout = html.Div(
        style={"maxWidth": "900px", "margin": "20px auto", "fontFamily": "Arial"},
        children=[
            html.P("Standalone map preview — select a suburb to inspect nearby air quality."),
            dcc.Dropdown(
                id="test-suburb",
                options=[{"label": f"{r.suburb} {r.postcode}", "value": i} for i, r in subs.iterrows()],
                placeholder="Pick a suburb",
            ),
            dcc.Store(id="store-location"),
            dcc.Store(id="store-profile"),
            layout(),
        ],
    )

    @app.callback(Output("store-location", "data"), Input("test-suburb", "value"), prevent_initial_call=True)
    def _pick(i):
        if i is None:
            return None
        r = subs.loc[i]
        return {
            "kind": "suburb",
            "site_id": None,
            "name": r["suburb"],
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "estimated": True,
        }

    register_callbacks(app)
    app.run(debug=True)
