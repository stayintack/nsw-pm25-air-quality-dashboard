"""Suburb/postcode search and browser-local health-profile selection.

Exact suburb matches rank ahead of partial matches, and only the top 40 results are sent to the
browser. Search and profile changes update shared dashboard state and provide visible feedback.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from dash import Input, Output, State, ctx, dcc, html, no_update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import data_loader as dl  # noqa: E402


MAX_OPTIONS = 40


def _option(row) -> dict:
    return {"label": f"{row.suburb} {row.postcode}".strip(), "value": row.suburb}


def suburb_options(query: str | None, current: str | None = None) -> list[dict]:
    """Best matches first: exact name, then names starting with the text, then a word starting with it,
    then anywhere in the name; digits match postcodes. Only MAX_OPTIONS are sent to the browser
    (instead of all 4,542), and the selected suburb is always kept so its label still shows."""
    subs = dl.load_suburbs()
    q = (query or "").strip().lower()
    if not q:
        hits = subs.head(MAX_OPTIONS)
    elif q.isdigit():
        hits = subs[subs["postcode"].str.startswith(q)].sort_values(["postcode", "suburb"]).head(MAX_OPTIONS)
    else:
        name = subs["suburb"].str.lower()
        rank = pd.Series(4, index=subs.index)
        rank[name.str.contains(q, regex=False)] = 3
        rank[name.str.contains(" " + q, regex=False)] = 2
        rank[name.str.startswith(q)] = 1
        rank[name == q] = 0
        hits = subs.assign(_r=rank)[rank < 4].sort_values(["_r", "suburb"]).head(MAX_OPTIONS)
    options = [_option(r) for r in hits.itertuples()]
    if current and current not in {o["value"] for o in options}:
        row = subs[subs["suburb"] == current]
        if not row.empty:
            options.append(_option(next(row.itertuples())))
    return options


def layout():
    return html.Section(
        id="profile-panel",
        className="panel profile-panel",
        **{"aria-labelledby": "profile-title"},
        children=[
            html.H2("Your location and health profile", id="profile-title", className="panel-title"),
            html.Div(
                className="profile-row",
                children=[
                    html.Div(
                        className="profile-field profile-field-location",
                        children=[
                            html.Label("Suburb or postcode", htmlFor="profile-suburb", className="profile-label"),
                            dcc.Dropdown(
                                id="profile-suburb",
                                options=suburb_options(None, config.DEFAULT_SUBURB),
                                value=config.DEFAULT_SUBURB,
                                search_order="original",  # keep our relevance order
                                placeholder="Type a suburb or postcode, e.g. Parramatta or 2150",
                                clearable=False,
                                searchable=True,
                                optionHeight=36,
                            ),
                        ],
                    ),
                    html.Fieldset(
                        className="profile-field profile-field-profile",
                        children=[
                            html.Legend("Health profile (choose one)", className="profile-label"),
                            dcc.RadioItems(
                                id="profile-choice",
                                options=[{"label": label, "value": key} for key, label in config.PROFILES.items()],
                                value=config.DEFAULT_PROFILE,
                                persistence=True,
                                persistence_type="local",
                                className="profile-chips",
                                inputClassName="profile-chip-input",
                                labelClassName="profile-chip",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="profile-status",
                children=[
                    html.Span(id="profile-current", className="profile-current"),
                    html.Span(
                        id="profile-feedback",
                        className="profile-feedback",
                        role="status",
                        **{"aria-live": "polite"},
                    ),
                ],
            ),
            html.P(
                "Your profile is saved only in this browser. Nothing is sent or stored on a server.",
                className="profile-privacy muted",
            ),
        ],
    )


def register_callbacks(app):
    @app.callback(
        Output("profile-suburb", "options"), Input("profile-suburb", "search_value"), State("profile-suburb", "value")
    )
    def _search(text, current):
        return suburb_options(text, current)

    @app.callback(
        Output("store-location", "data", allow_duplicate=True),
        Input("profile-suburb", "value"),
        prevent_initial_call=True,
    )
    def _choose_suburb(name):
        if not name:
            return no_update
        r = dl.load_suburbs().set_index("suburb").loc[name]
        return {
            "kind": "suburb",
            "site_id": None,
            "name": name,
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "estimated": True,
        }

    @app.callback(
        Output("store-profile", "data", allow_duplicate=True),
        Input("profile-choice", "value"),
        State("store-profile", "data"),
        prevent_initial_call=True,
    )
    def _choose_profile(profile, current):
        if not profile or (current and current.get("profile") == profile):
            return no_update
        return {
            "profile": profile,
            "threshold": None,
        }  # a new profile starts from its default threshold

    @app.callback(
        Output("profile-current", "children"),
        Output("profile-feedback", "children"),
        Input("store-location", "data"),
        Input("store-profile", "data"),
    )
    def _status(location, profile):
        prof_label = config.PROFILES.get((profile or {}).get("profile"), config.PROFILES[config.DEFAULT_PROFILE])
        where = "—"
        if location:
            where = (
                f"{location['name']} station (selected on the map)"
                if location.get("kind") == "station"
                else location["name"]
            )
        current = [
            html.Span("Showing: ", className="muted"),
            html.B(where),
            html.Span(" · ", className="muted"),
            html.Span(f"{prof_label} profile active", className="chip chip-profile"),
        ]
        if ctx.triggered_id == "store-profile":
            feedback = f"✓ Advice and alerts updated for {prof_label}."
        elif ctx.triggered_id == "store-location":
            feedback = f"✓ Map, trend, advice and alerts updated for {where}."
        else:
            feedback = ""
        return current, feedback


if __name__ == "__main__":
    from dash import Dash

    app = Dash(__name__, assets_folder=str(Path(__file__).resolve().parents[1] / "assets"))
    app.layout = html.Div(
        style={"maxWidth": "1100px", "margin": "20px auto"},
        children=[
            dcc.Store(
                id="store-profile",
                storage_type="local",
                data={"profile": "general", "threshold": None},
            ),
            dcc.Store(id="store-location"),
            layout(),
            html.Pre(id="test-out"),
        ],
    )

    @app.callback(
        Output("test-out", "children"),
        Input("store-profile", "data"),
        Input("store-location", "data"),
    )
    def _show(profile_state, location_state):
        return f"store-profile = {profile_state}\nstore-location = {location_state}"

    register_callbacks(app)
    app.run(debug=True)
