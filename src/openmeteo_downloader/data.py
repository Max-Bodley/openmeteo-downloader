"""Container for downloaded weather, with tidy/wide views and CSV export."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

import pandas as pd

AVERAGE_COLUMN = "All_Sites_Avg"

# Short, filename/Excel-friendly unit labels for column headers.
_UNIT_LABELS = {
    "fahrenheit": "F",
    "celsius": "C",
    "kelvin": "K",
    "percentage": "pct",
    "millimetre": "mm",
    "centimetre": "cm",
    "inch": "in",
    "metre": "m",
    "feet": "ft",
    "kilometres_per_hour": "kmh",
    "miles_per_hour": "mph",
    "metre_per_second": "ms",
    "knots": "kn",
    "hectopascal": "hPa",
    "kilopascal": "kPa",
    "watt_per_square_metre": "Wm2",
    "megajoule_per_square_metre": "MJm2",
    "degree_direction": "deg",
    "wmo_code": "wmo",
}


def unit_label(unit: str) -> str:
    return _UNIT_LABELS.get(unit, unit)


@dataclass
class WeatherData:
    """Hourly weather for one or more sites.

    Attributes:
        long: One row per site-hour: ``site, lat, lon, datetime, <variables...>``.
        locations: One row per site, including the ERA5 grid cell actually used.
        units: Variable name -> unit (e.g. ``{"temperature_2m": "fahrenheit"}``).
    """

    long: pd.DataFrame
    locations: pd.DataFrame
    units: dict[str, str]

    @property
    def variables(self) -> list[str]:
        return list(self.units)

    @property
    def sites(self) -> list[str]:
        return list(self.locations["site"])

    def wide(self, variable: str | None = None, average: bool = True) -> pd.DataFrame:
        """One column per site (indexed by datetime), plus an all-sites hourly mean."""
        variable = self._resolve(variable)
        wide = self.long.pivot(index="datetime", columns="site", values=variable)
        wide = wide[self.sites]  # keep the order the sites were given in
        wide.columns.name = None
        if average and len(self.sites) > 1:
            wide[AVERAGE_COLUMN] = wide.mean(axis=1).round(2)
        return wide

    def site(self, name: str) -> pd.DataFrame:
        """All variables for a single site, indexed by datetime."""
        if name not in self.sites:
            raise KeyError(f"Unknown site {name!r}; available: {self.sites}")
        rows = self.long[self.long["site"] == name]
        return rows.set_index("datetime")[self.variables]

    def to_csv(
        self,
        output_dir: str | PathLike = ".",
        name: str = "era5",
        formats: Iterable[str] = ("wide", "long"),
    ) -> list[Path]:
        """Write CSVs and return the paths written.

        * ``wide``: ``{name}_{variable}_{unit}_wide.csv`` per variable
        * ``long``: ``{name}_long.csv`` with every variable
        * a small ``{name}_locations.csv`` is always written alongside
        """
        formats = set(formats)
        unknown = formats - {"wide", "long"}
        if unknown:
            raise ValueError(f"Unknown format(s) {sorted(unknown)}; use 'wide' and/or 'long'")

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        written = []

        if "wide" in formats:
            for variable in self.variables:
                path = out / f"{name}_{variable}_{unit_label(self.units[variable])}_wide.csv"
                wide = self.wide(variable).reset_index()
                wide["datetime"] = _csv_datetimes(wide["datetime"])
                wide.to_csv(path, index=False)
                written.append(path)

        if "long" in formats:
            path = out / f"{name}_long.csv"
            long = self.long.rename(columns=self._labelled_columns())
            long["datetime"] = _csv_datetimes(long["datetime"])
            long.to_csv(path, index=False)
            written.append(path)

        path = out / f"{name}_locations.csv"
        self.locations.to_csv(path, index=False)
        written.append(path)
        return written

    def _resolve(self, variable: str | None) -> str:
        if variable is None:
            if len(self.variables) != 1:
                raise ValueError(f"Several variables downloaded; pick one of {self.variables}")
            return self.variables[0]
        if variable not in self.units:
            raise KeyError(f"{variable!r} was not downloaded; available: {self.variables}")
        return variable

    def _labelled_columns(self) -> dict[str, str]:
        return {v: f"{v}_{unit_label(u)}" for v, u in self.units.items()}

    def __repr__(self) -> str:
        times = self.long["datetime"]
        span = f"{times.min():%Y-%m-%d %H:%M} to {times.max():%Y-%m-%d %H:%M}" if len(times) else "empty"
        units = ", ".join(f"{v} ({unit_label(u)})" for v, u in self.units.items())
        return (
            f"WeatherData({len(self.sites)} sites, {len(self.long):,} rows, {span})\n"
            f"  sites:     {', '.join(self.sites)}\n"
            f"  variables: {units}"
        )


def _csv_datetimes(times: pd.Series) -> pd.Series:
    """UTC is written without an offset (Excel-friendly); other zones keep theirs."""
    if str(times.dt.tz) in ("UTC", "GMT"):
        return times.dt.tz_localize(None)
    return times
