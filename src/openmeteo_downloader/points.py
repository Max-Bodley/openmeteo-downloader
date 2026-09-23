"""Locations to pull weather for, and helpers to build them from common inputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Point:
    """A named location. Longitude may be given as -180..180 or 0..360."""

    name: str
    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not -90 <= self.lat <= 90:
            raise ValueError(f"{self.name!r}: latitude {self.lat} is outside -90..90")
        if not -180 <= self.lon <= 360:
            raise ValueError(f"{self.name!r}: longitude {self.lon} is outside -180..360")
        # Normalise 0..360 longitudes to -180..180 so outputs are consistent.
        if self.lon > 180:
            object.__setattr__(self, "lon", self.lon - 360)


PointsLike = (
    Mapping[str, tuple[float, float]]
    | Iterable[Point | tuple[float, float] | tuple[str, float, float]]
    | pd.DataFrame
    | str
    | PathLike
)

_NAME_COLUMNS = ("name", "site", "label", "location")
_LAT_COLUMNS = ("lat", "latitude")
_LON_COLUMNS = ("lon", "lng", "long", "longitude")


def to_points(points: PointsLike) -> list[Point]:
    """Coerce any supported input into a list of :class:`Point`.

    Accepts:
      * ``{"Des Moines, IA": (41.59, -93.62), ...}``
      * ``[Point(...), ...]``, ``[(lat, lon), ...]`` or ``[(name, lat, lon), ...]``
      * a DataFrame, or a path to a CSV, with name/lat/lon columns
        (``site``/``latitude``/``longitude`` etc. are also recognised)
    """
    if isinstance(points, (str, PathLike)):
        return _from_frame(pd.read_csv(Path(points)))
    if isinstance(points, pd.DataFrame):
        return _from_frame(points)
    if isinstance(points, Mapping):
        result = [Point(str(name), *map(float, coords)) for name, coords in points.items()]
    else:
        result = [_from_item(item) for item in points]

    if not result:
        raise ValueError("No points were given")
    names = [p.name for p in result]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"Point names must be unique; duplicated: {duplicates}")
    return result


def _from_item(item: Point | tuple) -> Point:
    if isinstance(item, Point):
        return item
    if len(item) == 2:
        lat, lon = map(float, item)
        return Point(f"{lat:.4f}, {lon:.4f}", lat, lon)
    if len(item) == 3:
        name, lat, lon = item
        return Point(str(name), float(lat), float(lon))
    raise ValueError(f"Expected (lat, lon) or (name, lat, lon), got {item!r}")


def _from_frame(df: pd.DataFrame) -> list[Point]:
    columns = {c.strip().lower(): c for c in df.columns}

    def find(candidates: tuple[str, ...], required: bool = True) -> str | None:
        for candidate in candidates:
            if candidate in columns:
                return columns[candidate]
        if required:
            raise ValueError(
                f"Could not find a {candidates[0]!r} column (looked for {list(candidates)}); "
                f"columns present: {list(df.columns)}"
            )
        return None

    lat_col, lon_col = find(_LAT_COLUMNS), find(_LON_COLUMNS)
    name_col = find(_NAME_COLUMNS, required=False)
    if name_col is None:
        return to_points(list(zip(df[lat_col], df[lon_col])))
    return to_points(list(zip(df[name_col], df[lat_col], df[lon_col])))
