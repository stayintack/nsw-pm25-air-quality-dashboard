"""Render dashboard panels across representative location and profile settings."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT_DIR / "dashboard"
sys.path.insert(0, str(DASHBOARD_DIR))
warnings.simplefilter("error")

import app as dashboard_app  # noqa: E402
import config  # noqa: E402
import data_loader  # noqa: E402
from components import advice_panel, alert_panel, map_panel, profile_panel, trend_panel  # noqa: E402


@pytest.fixture(scope="module")
def representative_locations() -> dict[str, dict | None]:
    suburbs = data_loader.load_suburbs().set_index("suburb")

    def suburb_location(name: str) -> dict:
        suburb = suburbs.loc[name]
        return {
            "kind": "suburb",
            "site_id": None,
            "name": name,
            "lat": float(suburb.lat),
            "lon": float(suburb.lon),
            "estimated": True,
        }

    site = data_loader.load_sites().iloc[0]
    station_location = {
        "kind": "station",
        "site_id": int(site.site_id),
        "name": site.site_name,
        "lat": float(site.lat),
        "lon": float(site.lon),
        "estimated": False,
    }
    return {
        "Parramatta": suburb_location("Parramatta"),
        "Katoomba": suburb_location("Katoomba"),
        "Broken Hill": suburb_location("Broken Hill"),
        "monitoring station": station_location,
        "no selection": None,
    }


@pytest.mark.parametrize(
    "location_name",
    ["Parramatta", "Katoomba", "Broken Hill", "monitoring station", "no selection"],
)
@pytest.mark.parametrize("profile", list(config.PROFILES))
@pytest.mark.parametrize("threshold", [None, 5.0], ids=["profile default", "custom threshold"])
def test_dashboard_panels_render(
    representative_locations: dict[str, dict | None],
    location_name: str,
    profile: str,
    threshold: float | None,
) -> None:
    location = representative_locations[location_name]
    profile_state = {"profile": profile, "threshold": threshold}

    map_panel.build_figure(location)
    map_panel.build_summary(location)
    advice_panel.build_card(profile_state, location)
    for date_range in ("today", "7d", "30d"):
        trend_panel.render(location, profile_state, date_range)
    alert_panel.build_banner(profile_state, location, {})
    alert_panel.build_history(location, profile_state)


def test_suburb_search_ranks_exact_names_and_postcodes() -> None:
    assert profile_panel.suburb_options("Parramatta")[0]["value"] == "Parramatta"
    assert profile_panel.suburb_options("2780")[0]["value"] == "Katoomba"


def test_app_layout_includes_every_panel() -> None:
    layout_ids = repr(dashboard_app.app.layout)
    for name in dashboard_app.PANELS:
        assert f"area-{name}" in layout_ids
