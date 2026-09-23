"""Run downloads from a TOML job file, so no Python is needed for routine pulls."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from importlib.resources import files
from os import PathLike
from pathlib import Path

from .client import DEFAULT_URL, Client
from .points import Point, to_points


@dataclass
class Job:
    """Everything needed for one download. Mirrors the keys in the TOML file."""

    points: list[Point]
    start: str | int
    end: str | int | None = None
    variables: list[str] = field(default_factory=lambda: ["temperature_2m"])
    output_dir: Path = Path("output")
    name: str = "era5"
    formats: list[str] = field(default_factory=lambda: ["wide", "long"])
    temperature_unit: str = "fahrenheit"
    wind_speed_unit: str = "kmh"
    precipitation_unit: str = "mm"
    timezone: str = "UTC"
    model: str = "era5"
    elevation_correction: bool = False
    server: str = DEFAULT_URL
    api_params: dict = field(default_factory=dict)

    def run(self, progress: bool = True) -> list[Path]:
        """Download and write the CSVs; returns the files written."""
        data = Client(self.server).fetch(
            self.points,
            self.start,
            self.end,
            self.variables,
            temperature_unit=self.temperature_unit,
            wind_speed_unit=self.wind_speed_unit,
            precipitation_unit=self.precipitation_unit,
            timezone=self.timezone,
            model=self.model,
            elevation_correction=self.elevation_correction,
            progress=progress,
            **self.api_params,
        )
        return data.to_csv(self.output_dir, self.name, self.formats)


def load_job(path: str | PathLike) -> Job:
    """Read a TOML job file. Relative paths inside it are resolved from its folder."""
    path = Path(path)
    with path.open("rb") as f:
        raw = tomllib.load(f)
    base = path.parent

    points, points_file = raw.pop("points", None), raw.pop("points_file", None)
    if (points is None) == (points_file is None):
        raise ValueError(f"{path}: give exactly one of [points] or points_file")
    raw["points"] = to_points(base / points_file if points_file else points)

    if isinstance(raw.get("variables"), str):
        raw["variables"] = [raw["variables"]]
    if isinstance(raw.get("formats"), str):
        raw["formats"] = [raw["formats"]]
    raw["output_dir"] = base / raw.get("output_dir", "output")

    known = {f.name for f in fields(Job)}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ValueError(f"{path}: unknown setting(s) {unknown}; valid settings are {sorted(known)}")
    if "start" not in raw:
        raise ValueError(f"{path}: 'start' is required")
    return Job(**raw)


def run_job(path: str | PathLike, progress: bool = True) -> list[Path]:
    """Load a TOML job file and run it."""
    return load_job(path).run(progress=progress)


def template(name: str) -> str:
    """Contents of a bundled template: ``"config.toml"`` or ``"docker-compose.yml"``."""
    return files(__package__).joinpath("templates", name).read_text(encoding="utf-8")
