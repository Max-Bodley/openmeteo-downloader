"""Tests that don't need a running server."""

from datetime import date

import pandas as pd
import pytest

from openmeteo_downloader import Point, WeatherData, load_job, to_points
from openmeteo_downloader.client import _parse_date
from openmeteo_downloader.config import template


def test_points_from_dict_list_and_csv(tmp_path):
    from_dict = to_points({"A": (41.0, -93.0), "B": (36.0, 264.0)})
    assert from_dict == [Point("A", 41.0, -93.0), Point("B", 36.0, -96.0)]  # 0..360 normalised

    assert to_points([("A", 41, -93)])[0] == Point("A", 41.0, -93.0)
    assert to_points([(41, -93)])[0].name == "41.0000, -93.0000"

    csv = tmp_path / "sites.csv"
    csv.write_text("Site,Latitude,Longitude\nA,41,-93\nB,36,-96\n")
    assert [p.name for p in to_points(csv)] == ["A", "B"]


def test_points_validation():
    with pytest.raises(ValueError, match="latitude"):
        Point("bad", 95, 0)
    with pytest.raises(ValueError, match="unique"):
        to_points([("A", 1, 1), ("A", 2, 2)])


@pytest.mark.parametrize(
    ("value", "is_end", "expected"),
    [
        (1985, False, date(1985, 1, 1)),
        ("2025", True, date(2025, 12, 31)),
        ("2021-06-15", False, date(2021, 6, 15)),
    ],
)
def test_parse_date(value, is_end, expected):
    assert _parse_date(value, is_end) == expected


def _sample() -> WeatherData:
    times = pd.date_range("2021-01-01", periods=3, freq="h", tz="UTC")
    long = pd.DataFrame(
        {
            "site": ["A"] * 3 + ["B"] * 3,
            "lat": [41.0] * 3 + [36.0] * 3,
            "lon": [-93.0] * 3 + [-96.0] * 3,
            "datetime": list(times) * 2,
            "temperature_2m": [10.0, 11.0, 12.0, 20.0, 21.0, 22.0],
        }
    )
    locations = pd.DataFrame({"site": ["A", "B"], "lat": [41.0, 36.0], "lon": [-93.0, -96.0]})
    return WeatherData(long, locations, {"temperature_2m": "fahrenheit"})


def test_wide_has_sites_in_order_and_average():
    wide = _sample().wide()
    assert list(wide.columns) == ["A", "B", "All_Sites_Avg"]
    assert wide["All_Sites_Avg"].tolist() == [15.0, 16.0, 17.0]


def test_to_csv_writes_expected_files(tmp_path):
    paths = _sample().to_csv(tmp_path, "t")
    assert sorted(p.name for p in paths) == [
        "t_locations.csv",
        "t_long.csv",
        "t_temperature_2m_F_wide.csv",
    ]
    long = pd.read_csv(tmp_path / "t_long.csv")
    assert "temperature_2m_F" in long.columns
    assert long["datetime"][0] == "2021-01-01 00:00:00"  # UTC written without offset


def test_template_config_loads(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(template("config.toml"))
    job = load_job(path)
    assert [p.name for p in job.points] == ["Cedar Rapids, IA", "Des Moines, IA"]
    assert job.output_dir == tmp_path / "output"


def test_config_rejects_typos(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('start = 2000\nvariabels = ["x"]\n[points]\nA = [1, 1]\n')
    with pytest.raises(ValueError, match="variabels"):
        load_job(path)
