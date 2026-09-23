"""Tests against a real local Open-Meteo server; skipped when it isn't running."""

import pytest

from openmeteo_downloader import Client

client = Client()
pytestmark = pytest.mark.skipif(not client.is_running(), reason="Open-Meteo server not running")


def test_fetch_one_day_matches_era5_grid():
    data = client.fetch({"Cedar Rapids, IA": (41.9779, -91.6656)}, "2021-01-01", "2021-01-01", progress=False)
    assert len(data.long) == 24
    assert data.units == {"temperature_2m": "fahrenheit"}
    # Nearest 0.25 deg ERA5 cell, no elevation downscaling.
    assert data.locations.loc[0, ["grid_lat", "grid_lon"]].tolist() == [42.0, -91.75]


def test_multiple_variables_and_timezone():
    data = client.fetch(
        [("A", 41.5868, -93.6250)],
        "2021-07-01",
        "2021-07-01",
        ["temperature_2m", "dew_point_2m", "relative_humidity_2m"],
        timezone="America/Chicago",
        progress=False,
    )
    assert data.variables == ["temperature_2m", "dew_point_2m", "relative_humidity_2m"]
    assert data.units["relative_humidity_2m"] == "percentage"
    assert str(data.long["datetime"].dt.tz) == "America/Chicago"
    assert data.long["datetime"].iloc[0].hour == 0
