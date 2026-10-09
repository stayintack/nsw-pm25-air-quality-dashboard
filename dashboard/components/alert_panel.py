"""Let users set an alert threshold and inspect recent alert frequency.

The banner reports whether today's selected-location value reaches the profile's default or custom
threshold. Alert history is stored in this browser and limited to one entry per location per day.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dcc, html, no_update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow `python components/alert_panel.py`
import config  # noqa: E402
import data_loader as dl  # noqa: E402

TODAY = pd.Timestamp(config.DATA_AS_OF)
SLIDER_MIN, SLIDER_MAX, SLIDER_STEP = 5, 55, 0.25
TEAL, INK, MUTED = config.THEME["teal"], config.THEME["ink"], config.THEME["muted"]


# ---------- helpers ----------
def _profile(profile_data):
    key = (profile_data or {}).get("profile") or config.DEFAULT_PROFILE
    return key, config.PROFILES.get(key, key)


def level_for(profile_data) -> float:
    """User's alert level: their own setting if any, else the profile default."""
    key, _ = _profile(profile_data)
    custom = (profile_data or {}).get("threshold")
    if custom is not None:
        return float(custom)
    return dl.default_threshold(key) or dl.default_threshold(config.DEFAULT_PROFILE)


def _cut_label(level: float) -> str:
    """Where an alert level sits on the official scale, e.g. 'start of Fair' or 'within Good'."""
    starts = {upper: dl.CATEGORIES[dl.CATEGORIES.index(name) + 1] for upper, _inc, name in dl.AQC_BOUNDS["24h"]}
    return f"start of {starts[level]}" if level in starts else f"within {dl.category_for(level)}"


@lru_cache(maxsize=256)
def _year_series(kind: str, site_id, lat: float, lon: float) -> pd.DataFrame:
    """Last 12 months of daily PM2.5 for the location (station readings or the same IDW estimate)."""
    start = TODAY - pd.DateOffset(months=12) + pd.Timedelta(days=1)
    if kind == "station" and site_id is not None:
        d = dl.load_daily()
        d = d[(d["site_id"] == int(site_id)) & d["date"].between(start, TODAY)]
        s = d.set_index("date")["pm25"].reindex(pd.date_range(start, TODAY, freq="D"))
        return pd.DataFrame({"date": s.index, "pm25": s.to_numpy()})
    return dl.estimate_series(lat, lon, start, TODAY)[["date", "pm25"]]


def _series_for(location) -> pd.DataFrame:
    return _year_series(
        location.get("kind", "suburb"),
        location.get("site_id"),
        round(float(location["lat"]), 5),
        round(float(location["lon"]), 5),
    )


def _today(location) -> dict:
    if location.get("kind") == "station" and location.get("site_id") is not None:
        d = dl.load_daily()
        row = d[(d["site_id"] == int(location["site_id"])) & (d["date"] == TODAY)]
        if row.empty:
            return {"value": None, "category": None, "estimated": False}
        v = float(row["pm25"].iloc[0])
        return {"value": v, "category": dl.category_for(v), "estimated": False}
    return dl.estimate_at(location["lat"], location["lon"], TODAY)


# ---------- banner ----------
def build_banner(profile_data, location, log: dict):
    """Returns (children, className, updated log or no_update)."""
    _, prof_label = _profile(profile_data)
    level = level_for(profile_data)
    if not location or location.get("lat") is None:
        return (
            [html.P("Choose a suburb or click a station to check for alerts.")],
            "alert-banner alert-none",
            no_update,
        )
    name = location["name"]
    est = _today(location)
    if est["value"] is None:
        return (
            [html.P([html.B(name), ": no reliable reading nearby today, so no alert can be given."])],
            "alert-banner alert-none",
            no_update,
        )

    value, cat = est["value"], est["category"]
    style = config.CATEGORY_STYLE[cat]
    chip = html.Span(
        style["label"],
        className="alert-chip",
        style={"backgroundColor": style["color"], "color": style["text_on"]},
    )
    reading = [
        html.B(f"{value:.1f} µg/m³"),
        " ",
        chip,
        " (24-hour average",
        ", estimated" if est["estimated"] else "",
        ")",
    ]
    if value < level:
        return (
            [
                html.P(
                    [
                        html.Span("✓", className="alert-mark", **{"aria-hidden": "true"}),
                        html.B("No alert today. "),
                        f"{name}: ",
                        *reading,
                        f" is below your alert level of {level:g} µg/m³ ({prof_label}).",
                    ]
                )
            ],
            "alert-banner alert-ok",
            no_update,
        )

    key = f"{TODAY:%Y-%m-%d}|{name}"
    log = {k: v for k, v in (log or {}).items() if k.startswith(f"{TODAY:%Y-%m-%d}|")}  # keep only today's keys
    body = [
        f"{name}: ",
        *reading,
        f" has reached your alert level of {level:g} µg/m³ ({prof_label}). ",
        html.A("See what to do", href="#advice-panel"),
        ".",
    ]
    if key in log:  # frequency cap: already alerted for this place today → quiet reminder, no new alert
        return (
            [
                html.P(
                    [
                        html.Span("!", className="alert-mark", **{"aria-hidden": "true"}),
                        html.B("Alert already shown today. "),
                        *body,
                    ]
                ),
                html.P(
                    "To avoid alert fatigue, you get at most one alert per location per day.",
                    className="alert-cap muted",
                ),
            ],
            "alert-banner alert-active alert-seen",
            no_update,
        )
    log[key] = True
    return (
        [
            html.Div(
                role="alert",
                children=[
                    html.P(
                        [
                            html.Span("!", className="alert-mark", **{"aria-hidden": "true"}),
                            html.B(f"Air quality alert — {name}. "),
                            *body,
                        ]
                    )
                ],
            ),
            html.P(
                "New alert. You won't be alerted again for this location today.",
                className="alert-cap muted",
            ),
        ],
        "alert-banner alert-active alert-new",
        log,
    )


# ---------- "how often would this alert?" ----------
def build_history(location, profile_data):
    level = level_for(profile_data)
    _, prof_label = _profile(profile_data)
    if not location or location.get("lat") is None:
        return go.Figure(), ""
    s = _series_for(location).dropna(subset=["pm25"])
    if s.empty:
        return go.Figure().update_layout(
            height=150, xaxis_visible=False, yaxis_visible=False
        ), "No readings near here in the last 12 months."
    hits = s[s["pm25"] >= level]
    months = pd.period_range(TODAY - pd.DateOffset(months=11), TODAY, freq="M")
    per_month = hits.groupby(hits["date"].dt.to_period("M")).size().reindex(months, fill_value=0)

    fig = go.Figure(
        go.Bar(
            x=[p.strftime("%b") for p in months],
            y=per_month.to_numpy(),
            marker_color=TEAL,
            text=[str(v) if v else "" for v in per_month],
            textposition="outside",
            cliponaxis=False,
            customdata=[p.strftime("%B %Y") for p in months],
            hovertemplate="%{customdata}: %{y} alert day(s)<extra></extra>",
        )
    )
    fig.update_layout(
        height=150,
        margin=dict(l=4, r=4, t=14, b=4),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family=config.THEME["font"], size=12, color=INK),
        bargap=0.25,
        showlegend=False,
    )
    fig.update_yaxes(visible=False, range=[0, max(3, per_month.max() * 1.3)], fixedrange=True)
    fig.update_xaxes(fixedrange=True, tickfont=dict(size=11, color=MUTED))

    n, total = len(hits), len(s)
    if n:
        last = hits.iloc[-1]
        text = (
            f"At {level:g} µg/m³, {location['name']} reached your alert level on {n} of {total} days with data "
            f"in the last 12 months (about {n / 12:.1f} a month). Most recent: {last['date'].day} "
            f"{last['date']:%b %Y}, {last['pm25']:.1f} µg/m³."
        )
    else:
        text = (
            f"At {level:g} µg/m³, {location['name']} did not reach your alert level on any of the {total} days "
            "with data in the last 12 months."
        )
    return fig, text


# ---------- layout ----------
def _marks():
    """Numbers only (category names would overlap on narrow screens); the text below the slider names the category."""
    marks = {SLIDER_MIN: f"{SLIDER_MIN}", SLIDER_MAX: f"{SLIDER_MAX}"}
    marks.update({upper: f"{upper:g}" for upper, _inc, _name in dl.AQC_BOUNDS["24h"]})
    return marks


def layout():
    return html.Section(
        id="alert-panel",
        className="panel alert-panel",
        **{"aria-labelledby": "alert-title"},
        children=[
            html.H2("Alerts", id="alert-title", className="panel-title"),
            html.Div(
                className="alert-row",
                children=[
                    html.Div(
                        className="alert-col alert-col-status",
                        children=[
                            html.H3("Today", className="alert-sub"),
                            html.Div(
                                id="alert-banner", className="alert-banner"
                            ),  # new alerts announce themselves (role="alert" inside)
                            html.Button(
                                "Clear alert history (this browser)",
                                id="alert-clear",
                                n_clicks=0,
                                className="alert-link-button",
                            ),
                        ],
                    ),
                    html.Div(
                        className="alert-col alert-col-level",
                        children=[
                            html.H3(
                                [
                                    html.Label(
                                        "Your alert level (24-hour PM2.5, µg/m³)",
                                        htmlFor="alert-threshold",
                                    )
                                ],
                                className="alert-sub",
                            ),
                            dcc.Slider(
                                id="alert-threshold",
                                min=SLIDER_MIN,
                                max=SLIDER_MAX,
                                step=SLIDER_STEP,
                                marks=_marks(),
                                value=None,
                                included=False,
                                updatemode="mouseup",
                            ),
                            html.P(
                                id="alert-threshold-text",
                                className="alert-threshold-text",
                                role="status",
                                **{"aria-live": "polite"},
                            ),
                            html.Button(
                                "Reset to my profile's default",
                                id="alert-reset",
                                n_clicks=0,
                                className="alert-button",
                            ),
                            html.P(
                                "Alerts appear here when you open the dashboard. Email and SMS are unavailable "
                                "because they require accounts; health information stays in this browser.",
                                className="alert-scope muted",
                            ),
                        ],
                    ),
                    html.Div(
                        className="alert-col alert-col-history",
                        children=[
                            html.H3("How often would this alert? (last 12 months)", className="alert-sub"),
                            html.Div(
                                **{"aria-hidden": "true"},
                                children=dcc.Graph(
                                    id="alert-history-graph",
                                    config={"displayModeBar": False, "responsive": True},
                                ),
                            ),
                            html.P(id="alert-history-text", className="alert-history-text"),
                        ],
                    ),
                ],
            ),
        ],
    )


# ---------- callbacks ----------
def register_callbacks(app):
    # keep the slider and store-profile.threshold in sync (one callback, so the loop is safe)
    @app.callback(
        Output("store-profile", "data", allow_duplicate=True),
        Output("alert-threshold", "value"),
        Input("store-profile", "data"),
        Input("alert-threshold", "value"),
        Input("alert-reset", "n_clicks"),
        prevent_initial_call="initial_duplicate",
    )
    def _sync(profile, value, _reset):
        profile = dict(profile or {"profile": config.DEFAULT_PROFILE, "threshold": None})
        trig = ctx.triggered_id
        if trig == "alert-threshold" and value is not None:
            if profile.get("threshold") == value:
                return no_update, no_update
            profile["threshold"] = float(value)
            return profile, no_update
        if trig == "alert-reset":
            profile["threshold"] = None
            return profile, level_for(profile)
        return no_update, level_for(profile)  # first load or profile changed

    @app.callback(
        Output("alert-banner", "children"),
        Output("alert-banner", "className"),
        Output("store-alert-log", "data"),
        Output("alert-threshold-text", "children"),
        Output("alert-history-graph", "figure"),
        Output("alert-history-text", "children"),
        Input("store-profile", "data"),
        Input("store-location", "data"),
        Input("alert-clear", "n_clicks"),
        State("store-alert-log", "data"),
    )
    def _render(profile, location, _clear, log):
        cleared = ctx.triggered_id == "alert-clear"
        if cleared:
            log = {}
        banner, cls, new_log = build_banner(profile, location, log)
        if cleared and new_log is no_update:
            new_log = {}
        key, label = _profile(profile)
        level, default = level_for(profile), dl.default_threshold(key)
        own = (profile or {}).get("threshold") is not None and level != default
        level_text = [
            html.B(f"{level:g} µg/m³"),
            f" ({_cut_label(level)}) — ",
            "your own setting" if own else f"default for {label}",
            f" (default {default:g})" if own else "",
        ]
        fig, hist = build_history(location, profile)
        return banner, cls, new_log, level_text, fig, hist


if __name__ == "__main__":  # standalone test: python components/alert_panel.py
    from dash import Dash

    app = Dash(__name__, assets_folder=str(Path(__file__).resolve().parents[1] / "assets"))
    app.layout = html.Div(
        style={"maxWidth": "1200px", "margin": "20px auto"},
        children=[
            dcc.Dropdown(
                id="t-profile",
                options=[{"label": v, "value": k} for k, v in config.PROFILES.items()],
                value="asthma_copd",
            ),
            dcc.Dropdown(id="t-suburb", options=["Parramatta", "Katoomba", "Broken Hill"], value="Parramatta"),
            dcc.Store(
                id="store-profile",
                storage_type="local",
                data={"profile": "general", "threshold": None},
            ),
            dcc.Store(id="store-location"),
            dcc.Store(id="store-alert-log", storage_type="local", data={}),
            layout(),
            html.Pre(id="t-out"),
        ],
    )

    @app.callback(
        Output("store-profile", "data", allow_duplicate=True),
        Input("t-profile", "value"),
        prevent_initial_call=True,
    )
    def _p(p):
        return {"profile": p, "threshold": None}

    @app.callback(Output("store-location", "data"), Input("t-suburb", "value"))
    def _l(s):
        r = dl.load_suburbs().set_index("suburb").loc[s]
        return {
            "kind": "suburb",
            "site_id": None,
            "name": s,
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "estimated": True,
        }

    @app.callback(
        Output("t-out", "children"),
        Input("store-profile", "data"),
        Input("store-alert-log", "data"),
    )
    def _o(profile_state, alert_log):
        return f"store-profile = {profile_state}\nstore-alert-log = {alert_log}"

    register_callbacks(app)
    app.run(debug=True)
