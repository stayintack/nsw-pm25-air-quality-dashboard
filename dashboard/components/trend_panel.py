"""Show daily and hourly PM2.5 trends for the selected location.

Category bands and point labels keep the official scale visible. The chart distinguishes measured
and estimated values, shows the active alert threshold, and provides an equivalent text summary and
data table. Location or profile changes update the chart automatically.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, dcc, html

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow `python components/trend_panel.py`
import config  # noqa: E402
import data_loader as dl  # noqa: E402

RANGES = {"today": "Today (hourly)", "7d": "7 days", "30d": "30 days"}
DEFAULT_RANGE = "7d"
NAVY, TEAL, INK, MUTED, GRID = (
    config.THEME["navy"],
    config.THEME["teal"],
    config.THEME["ink"],
    config.THEME["muted"],
    "#e6e9ed",
)


# ---------- data ----------
@lru_cache(maxsize=None)
def _thresholds() -> dict:
    """Return the default alert level per profile from thresholds.csv."""
    if hasattr(dl, "load_thresholds"):
        t = dl.load_thresholds()
    else:
        path = dl.DATA_DIR / "thresholds.csv"
        if not path.exists():
            return {}
        t = pd.read_csv(path)
    return dict(zip(t["profile"], t["default_threshold_ugm3"].astype(float)))


def alert_level(profile_data: dict | None) -> tuple[float | None, str]:
    """Return the active threshold and its profile label."""
    profile = (profile_data or {}).get("profile") or config.DEFAULT_PROFILE
    label = config.PROFILES.get(profile, profile)
    custom = (profile_data or {}).get("threshold")
    return (float(custom) if custom is not None else _thresholds().get(profile)), label


def _hourly_station(site_id: int, day: pd.Timestamp) -> pd.Series:
    h = dl.load_hourly()
    h = h[(h["site_id"] == site_id) & (h["datetime"].dt.normalize() == day)]
    return h.set_index("datetime")["pm25"]


def daily_series(location: dict, days: int) -> pd.DataFrame:
    """date, pm25, category, estimated — one row per day (missing days kept as gaps)."""
    end = pd.Timestamp(config.DATA_AS_OF)
    start = end - pd.Timedelta(days=days - 1)
    if location.get("kind") == "station" and location.get("site_id") is not None:
        d = dl.load_daily()
        d = d[(d["site_id"] == int(location["site_id"])) & d["date"].between(start, end)]
        s = d.set_index("date")["pm25"].reindex(pd.date_range(start, end, freq="D"))
        out = pd.DataFrame({"date": s.index, "pm25": s.to_numpy(), "estimated": False})
        out["category"] = [dl.category_for(v) for v in out["pm25"]]
        return out
    return dl.estimate_series(location["lat"], location["lon"], start, end)


def hourly_series(location: dict) -> pd.DataFrame:
    """time, pm25, category (1-hour categories), estimated — for the latest day in the data.

    A station uses its own hourly readings. A suburb uses the SAME stations and weights as its
    24-hour estimate used by the map and advice panels, re-normalised over the stations reporting in that hour,
    so all panels tell one consistent story.
    """
    day = pd.Timestamp(config.DATA_AS_OF)
    hours = pd.date_range(day, periods=24, freq="h")
    if location.get("kind") == "station" and location.get("site_id") is not None:
        s = _hourly_station(int(location["site_id"]), day).reindex(hours)
        estimated = False
    else:
        est = dl.estimate_at(location["lat"], location["lon"], day)
        if not est["contributors"]:
            s, estimated = pd.Series(np.nan, index=hours), True
        else:
            table = pd.DataFrame(
                {c["site_id"]: _hourly_station(c["site_id"], day).reindex(hours) for c in est["contributors"]}
            )
            w = pd.Series({c["site_id"]: c["weight"] for c in est["contributors"]})
            have = table.notna()
            s = (table.fillna(0) * w).sum(axis=1) / have.mul(w).sum(axis=1).replace(0, np.nan)
            estimated = est["estimated"]
    out = pd.DataFrame({"date": hours, "pm25": s.to_numpy(), "estimated": estimated})
    out["category"] = [dl.category_for(v, "1h") for v in out["pm25"]]
    return out


def series_for(location: dict, rng: str) -> pd.DataFrame:
    if rng == "today":
        return hourly_series(location)
    return daily_series(location, 30 if rng == "30d" else 7)


# ---------- chart ----------
def _bands(period: str) -> list[tuple[str, float, float]]:
    """(category, lower, upper) for the background bands; the last band is open-ended."""
    bounds, lower, out = dl.AQC_BOUNDS[period], 0.0, []
    for upper, _inc, name in bounds:
        out.append((name, lower, upper))
        lower = upper
    out.append(("Extremely poor", lower, float("inf")))
    return out


def _fmt_x(ts: pd.Timestamp, hourly: bool) -> str:
    if hourly:
        h = ts.hour % 12 or 12
        return f"{h} {'am' if ts.hour < 12 else 'pm'}"
    return f"{ts:%a} {ts.day} {ts:%b}"


def build_figure(df: pd.DataFrame, rng: str, threshold: float | None) -> go.Figure:
    hourly = rng == "today"
    period = "1h" if hourly else "24h"
    bands = _bands(period)
    valid = df.dropna(subset=["pm25"])
    data_max = float(valid["pm25"].max()) if not valid.empty else 0.0
    fair_top = bands[1][2]  # 25 (24-h) or 50 (1-h)
    show_threshold = threshold is not None and not hourly  # thresholds are 24-hour values
    ymax = max(data_max * 1.15, fair_top * 1.08, (threshold or 0) * 1.1 if show_threshold else 0)

    fig = go.Figure()
    x0, x1 = df["date"].min(), df["date"].max()
    pad = pd.Timedelta(minutes=30) if hourly else pd.Timedelta(hours=12)

    # category bands, each labelled with its name (text, not colour alone)
    for name, lo, hi in bands:
        if lo >= ymax:
            break
        top = min(hi, ymax)
        fig.add_shape(
            type="rect",
            xref="paper",
            x0=0,
            x1=1,
            y0=lo,
            y1=top,
            layer="below",
            line_width=0,
            fillcolor=config.CATEGORY_STYLE[name]["color"],
            opacity=0.13,
        )
        if top - lo > ymax * 0.06:  # skip a label if the visible band is too thin
            fig.add_annotation(
                xref="paper",
                x=0.005,
                y=top,
                yshift=-2,
                text=name,
                showarrow=False,
                xanchor="left",
                yanchor="top",
                font=dict(size=12, color=MUTED),
            )

    # measured vs estimated, same visual rule as the map: dashed line when the whole series is estimated;
    # each estimated point is drawn hollow (white centre, category-coloured ring), each measured point solid.
    all_est = bool(df.dropna(subset=["pm25"])["estimated"].all())
    colors = [config.CATEGORY_STYLE[c]["color"] if isinstance(c, str) else config.NO_DATA_COLOR for c in df["category"]]
    fills = ["#ffffff" if e else c for e, c in zip(df["estimated"], colors)]
    rings = [c if e else INK for e, c in zip(df["estimated"], colors)]
    ring_w = [2.5 if e else 1 for e in df["estimated"]]
    status = ["Estimated" if e else "Measured" for e in df["estimated"]]
    labels = [_fmt_x(t, hourly) for t in df["date"]]
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["pm25"],
            mode="lines+markers",
            connectgaps=False,
            line=dict(color=NAVY, width=2.5, dash="dash" if all_est else "solid"),
            marker=dict(size=9 if len(df) <= 30 else 7, color=fills, line=dict(color=rings, width=ring_w)),
            customdata=np.column_stack([labels, df["category"].fillna("No reading"), status]),
            hovertemplate="%{customdata[0]}<br><b>%{y:.1f} µg/m³</b> · %{customdata[1]}"
            "<br>%{customdata[2]}<extra></extra>",
            name="PM2.5",
        )
    )

    # emphasise the latest available point (focus + context)
    if not valid.empty:
        last = valid.iloc[-1]
        fig.add_trace(
            go.Scatter(
                x=[last["date"]],
                y=[last["pm25"]],
                mode="markers",
                hoverinfo="skip",
                showlegend=False,
                marker=dict(
                    size=16,
                    color="#ffffff" if last["estimated"] else config.CATEGORY_STYLE[last["category"]]["color"],
                    line=dict(
                        color=config.CATEGORY_STYLE[last["category"]]["color"] if last["estimated"] else INK,
                        width=3.5 if last["estimated"] else 2,
                    ),
                ),
            )
        )
        fig.add_annotation(
            x=last["date"],
            y=last["pm25"],
            ax=-12,
            ay=-34,
            arrowcolor=INK,
            arrowwidth=1,
            text=f"<b>{last['pm25']:.1f}</b> · {last['category']}",
            font=dict(size=13, color=INK),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor=INK,
            borderwidth=1,
            borderpad=3,
            xanchor="right",
        )

    if show_threshold:
        fig.add_hline(
            y=threshold,
            line=dict(color=TEAL, width=2, dash="dot"),
            annotation=dict(
                text=f"Your alert level {threshold:g}",
                font=dict(color=TEAL, size=12),
                xanchor="right",
                yanchor="bottom",
                x=1,
            ),
        )

    fig.update_layout(
        height=290,
        margin=dict(l=8, r=12, t=10, b=8),
        showlegend=False,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        hovermode="closest",
        font=dict(family=config.THEME["font"], size=13, color=INK),
        hoverlabel=dict(bgcolor="#ffffff", font=dict(color=INK)),
        uirevision=rng,
    )
    fig.update_yaxes(
        range=[0, ymax],
        title_text="PM2.5 (µg/m³)",
        gridcolor=GRID,
        zeroline=False,
        title_font=dict(size=12, color=MUTED),
        fixedrange=True,
    )
    fig.update_xaxes(
        range=[x0 - pad, x1 + pad],
        gridcolor=GRID,
        fixedrange=True,
        showline=True,
        linecolor="#b9c1c9",
        tickformat="%-I %p" if hourly else ("%a %-d" if rng == "7d" else "%-d %b"),
        dtick=3 * 3600 * 1000 if hourly else (86400000 if rng == "7d" else 7 * 86400000),
    )
    return fig


# ---------- text equivalents ----------
def _est_note(df: pd.DataFrame, hourly: bool) -> str:
    valid = df.dropna(subset=["pm25"])  # a gap is "no reading", not an estimate
    n_est, n = int(valid["estimated"].sum()), len(valid)
    if n_est == 0:
        return ""
    if n_est == n:
        return " (estimated)"
    return f" (estimated on {n_est} of {n} {'hours' if hourly else 'days'}, hollow points)"


def build_summary(df: pd.DataFrame, rng: str, location: dict, threshold: float | None, prof_label: str):
    hourly = rng == "today"
    valid = df.dropna(subset=["pm25"])
    where = location.get("name", "this location") + _est_note(df, hourly)
    span = "On 30 Sep 2026 (hourly)" if hourly else f"Over the last {len(df)} days"
    if valid.empty:
        return [
            html.P(
                f"{span}: no reliable reading within {dl.MAX_KM:.0f} km of {location.get('name')}, "
                "so no trend can be shown. Click the nearest station on the map instead."
            )
        ]

    hi = valid.loc[valid["pm25"].idxmax()]
    counts = valid["category"].value_counts()
    order = [c for c in dl.CATEGORIES if c in counts]
    unit = "hours" if hourly else "days"
    mix = ", ".join(f"{counts[c]} {c}" for c in order)
    parts = [
        html.P(
            [
                f"{span} at ",
                html.B(where),
                f", PM2.5 ranged {valid['pm25'].min():.1f}–{valid['pm25'].max():.1f} µg/m³ ({mix} {unit}). ",
                f"Highest: {_fmt_x(hi['date'], hourly)}, {hi['pm25']:.1f} µg/m³ ({hi['category']}).",
            ]
        )
    ]
    missing = len(df) - len(valid)
    notes = []
    if missing:
        notes.append(f"{missing} {unit} had no reading (gap in the line).")
    if hourly:
        notes.append("Hourly values use the 1-hour categories, which have higher cut-offs than the 24-hour ones.")
    elif threshold is not None:
        above = int((valid["pm25"] >= threshold).sum())
        notes.append(f"{above} of {len(valid)} days reached your alert level ({threshold:g} µg/m³, {prof_label}).")
    if notes:
        parts.append(html.P(" ".join(notes), className="trend-note"))
    return parts


def build_table(df: pd.DataFrame, rng: str) -> html.Table:
    hourly = rng == "today"
    head = html.Thead(
        html.Tr(
            [
                html.Th("Hour" if hourly else "Date", scope="col"),
                html.Th("PM2.5 (µg/m³)", scope="col"),
                html.Th("Category", scope="col"),
                html.Th("Measured / estimated", scope="col"),
            ]
        )
    )
    rows = [
        html.Tr(
            [
                html.Td(_fmt_x(r.date, hourly)),
                html.Td("—" if pd.isna(r.pm25) else f"{r.pm25:.1f}"),
                html.Td(r.category if isinstance(r.category, str) else "No reading"),
                html.Td("Estimated" if r.estimated else "Measured"),
            ]
        )
        for r in df.itertuples()
    ]
    return html.Table(className="trend-table", children=[head, html.Tbody(rows)])


def render(location: dict | None, profile_data: dict | None, rng: str | None):
    rng = rng if rng in RANGES else DEFAULT_RANGE
    if not location or location.get("lat") is None:
        empty = go.Figure().update_layout(height=290, xaxis_visible=False, yaxis_visible=False)
        return (
            "Choose a location",
            empty,
            [html.P("Choose a suburb or click a station to see its trend.")],
            None,
        )
    threshold, prof_label = alert_level(profile_data)
    df = series_for(location, rng)
    est = df.dropna(subset=["pm25"])["estimated"]
    tag = None if est.empty or not est.any() else ("Estimated" if est.all() else "Partly estimated")
    where = [
        html.B(location["name"]),
        " station" if location.get("kind") == "station" else "",
        html.Span(tag, className="map-estimated-tag") if tag else None,
    ]
    return (
        where,
        build_figure(df, rng, threshold),
        build_summary(df, rng, location, threshold, prof_label),
        build_table(df, rng),
    )


# ---------- layout + callbacks ----------
def layout():
    return html.Section(
        id="trend-panel",
        className="panel",
        **{"aria-labelledby": "trend-title"},
        children=[
            html.Div(
                className="trend-head",
                children=[
                    html.H2(
                        ["PM2.5 trend · ", html.Span(id="trend-where")],
                        id="trend-title",
                        className="panel-title",
                    ),
                    html.Div(
                        role="radiogroup",
                        **{"aria-label": "Time range"},
                        children=dcc.RadioItems(
                            id="trend-range",
                            options=[{"label": v, "value": k} for k, v in RANGES.items()],
                            value=DEFAULT_RANGE,
                            persistence=True,
                            persistence_type="local",
                            className="trend-range",
                            inputClassName="trend-range-input",
                        ),
                    ),
                ],
            ),
            # the chart is a visual summary; the text summary and table below carry the same content for screen readers
            html.Div(
                **{"aria-hidden": "true"},
                children=dcc.Graph(id="trend-graph", config={"displayModeBar": False, "responsive": True}),
            ),
            html.Div(id="trend-summary", className="trend-summary", role="status", **{"aria-live": "polite"}),
            html.Details(
                className="trend-details",
                children=[html.Summary("Show the numbers as a table"), html.Div(id="trend-table")],
            ),
        ],
    )


def register_callbacks(app):
    @app.callback(
        Output("trend-where", "children"),
        Output("trend-graph", "figure"),
        Output("trend-summary", "children"),
        Output("trend-table", "children"),
        Input("store-location", "data"),
        Input("store-profile", "data"),
        Input("trend-range", "value"),
    )
    def _render(location, profile, rng):
        return render(location, profile, rng)


if __name__ == "__main__":  # standalone test: python components/trend_panel.py
    from dash import Dash

    app = Dash(__name__, assets_folder=str(Path(__file__).resolve().parents[1] / "assets"))
    sites = dl.load_sites()
    app.layout = html.Div(
        style={"maxWidth": "640px", "margin": "20px auto"},
        children=[
            dcc.Dropdown(
                id="t-profile",
                options=[{"label": v, "value": k} for k, v in config.PROFILES.items()],
                value="asthma_copd",
            ),
            dcc.Dropdown(
                id="t-where",
                value="sub:Parramatta",
                options=[
                    {"label": f"Suburb: {s}", "value": f"sub:{s}"} for s in ["Parramatta", "Katoomba", "Broken Hill"]
                ]
                + [{"label": f"Station: {r.site_name}", "value": f"st:{r.site_id}"} for r in sites.itertuples()],
            ),
            dcc.Store(id="store-profile"),
            dcc.Store(id="store-location"),
            layout(),
        ],
    )

    @app.callback(
        Output("store-profile", "data"),
        Output("store-location", "data"),
        Input("t-profile", "value"),
        Input("t-where", "value"),
    )
    def _t(p, where):
        kind, key = where.split(":", 1)
        if kind == "st":
            r = sites.set_index("site_id").loc[int(key)]
            loc = {
                "kind": "station",
                "site_id": int(key),
                "name": r["site_name"],
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "estimated": False,
            }
        else:
            r = dl.load_suburbs().set_index("suburb").loc[key]
            loc = {
                "kind": "suburb",
                "site_id": None,
                "name": key,
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "estimated": True,
            }
        return {"profile": p, "threshold": None}, loc

    register_callbacks(app)
    app.run(debug=True)
