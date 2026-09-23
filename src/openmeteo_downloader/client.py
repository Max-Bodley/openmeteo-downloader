"""Talk to a (local) Open-Meteo server and turn its responses into DataFrames."""

from __future__ import annotations

import sys
import time
from collections.abc import Iterable
from datetime import date, datetime, timedelta

import openmeteo_requests
import pandas as pd
import requests
from openmeteo_sdk.Unit import Unit
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .data import WeatherData
from .points import Point, PointsLike, to_points

DEFAULT_URL = "http://127.0.0.1:6000"
DEFAULT_VARIABLES = ("temperature_2m",)

_UNIT_NAMES = {value: name for name, value in vars(Unit).items() if not name.startswith("_")}

DateLike = str | int | date | datetime


class ServerNotRunningError(ConnectionError):
    """The Open-Meteo server could not be reached."""


class Client:
    """Downloads historical (ERA5) weather from an Open-Meteo server.

    Args:
        url: Base URL of the server. The bundled docker-compose file serves on
            ``http://127.0.0.1:6000``.
        timeout: Seconds to wait for one request. The first request for a region
            can be slow while the server pulls data from S3; later ones are fast.
        retries: Retries on connection errors and 5xx responses.
        batch_size: Sites per request. Keeps individual responses a sensible size.
    """

    def __init__(
        self,
        url: str = DEFAULT_URL,
        timeout: float = 600,
        retries: int = 3,
        batch_size: int = 10,
    ) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.batch_size = batch_size

        self._session = requests.Session()
        retry = Retry(total=retries, backoff_factor=0.5, status_forcelist=(500, 502, 503, 504))
        self._session.mount("http://", HTTPAdapter(max_retries=retry))
        self._session.mount("https://", HTTPAdapter(max_retries=retry))
        self._api = openmeteo_requests.Client(session=self._session)

    def is_running(self) -> bool:
        """True if something is answering at :attr:`url`."""
        try:
            self._session.get(self.url, timeout=5)
        except requests.ConnectionError:
            return False
        return True

    def ensure_running(self) -> None:
        """Raise :class:`ServerNotRunningError` with a helpful message if the server is down."""
        if not self.is_running():
            raise ServerNotRunningError(
                f"No Open-Meteo server is answering at {self.url}.\n"
                "Start it with:  docker compose up -d\n"
                "(Don't have a compose file? Run:  openmeteo-downloader compose)"
            )

    def fetch(
        self,
        points: PointsLike,
        start: DateLike,
        end: DateLike | None = None,
        variables: str | Iterable[str] = DEFAULT_VARIABLES,
        *,
        temperature_unit: str = "fahrenheit",
        wind_speed_unit: str = "kmh",
        precipitation_unit: str = "mm",
        timezone: str = "UTC",
        model: str = "era5",
        elevation_correction: bool = False,
        progress: bool = True,
        **params,
    ) -> WeatherData:
        """Download hourly weather for every point between ``start`` and ``end``.

        Args:
            points: Where to download. See :func:`to_points` for accepted inputs,
                e.g. ``{"Des Moines, IA": (41.5868, -93.6250)}`` or a CSV path.
            start: First day, e.g. ``"1985-01-01"``, ``1985`` (= Jan 1) or a date.
            end: Last day, inclusive. A bare year means Dec 31. Defaults to the
                latest available data.
            variables: Open-Meteo hourly variable name(s), e.g. ``"temperature_2m"``,
                ``["temperature_2m", "dew_point_2m", "wind_speed_10m"]``.
                See https://open-meteo.com/en/docs/historical-weather-api
            temperature_unit: ``"fahrenheit"`` or ``"celsius"``.
            wind_speed_unit: ``"kmh"``, ``"ms"``, ``"mph"`` or ``"kn"``.
            precipitation_unit: ``"mm"`` or ``"inch"``.
            timezone: ``"UTC"`` (ERA5's native time) or an IANA name such as
                ``"America/Chicago"``; applied to every site.
            model: ``"era5"`` (0.25 deg, 1940-present) or ``"era5_land"`` (0.1 deg, 1950-present).
            elevation_correction: ``False`` returns the raw value of the nearest
                ERA5 grid cell, which matches data pulled from Copernicus. ``True``
                lets Open-Meteo adjust temperature for each point's actual elevation.
            progress: Print progress to stderr.
            **params: Any other Open-Meteo API parameter, passed through as-is.
        """
        pts = to_points(points)
        variables = [variables] if isinstance(variables, str) else list(variables)
        if timezone.lower() == "auto":
            raise ValueError("timezone='auto' isn't supported; pass 'UTC' or an IANA name")
        start_date = _parse_date(start, is_end=False)
        end_date = _parse_date(end, is_end=True) if end is not None else date.today() - timedelta(days=1)
        if end_date < start_date:
            raise ValueError(f"end ({end_date}) is before start ({start_date})")

        self.ensure_running()
        log = _logger(progress)
        log(f"Fetching {', '.join(variables)} for {len(pts)} site(s), {start_date} to {end_date} ...")
        began = time.perf_counter()

        frames, locations, units = [], [], {}
        batches = [pts[i : i + self.batch_size] for i in range(0, len(pts), self.batch_size)]
        for n, batch in enumerate(batches, 1):
            query = {
                "latitude": ",".join(str(p.lat) for p in batch),
                "longitude": ",".join(str(p.lon) for p in batch),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "hourly": ",".join(variables),
                "models": model,
                "timezone": "GMT" if timezone.upper() in ("UTC", "GMT") else timezone,
                "temperature_unit": temperature_unit,
                "wind_speed_unit": wind_speed_unit,
                "precipitation_unit": precipitation_unit,
                **params,
            }
            if not elevation_correction:
                query["elevation"] = ",".join("nan" for _ in batch)

            responses = self._api.weather_api(f"{self.url}/v1/archive", params=query, timeout=self.timeout)
            for point, response in zip(batch, responses, strict=True):
                frame, point_units = _to_frame(point, response, variables)
                frames.append(frame)
                units.update(point_units)
                locations.append(
                    {
                        "site": point.name,
                        "lat": point.lat,
                        "lon": point.lon,
                        "grid_lat": round(response.Latitude(), 4),
                        "grid_lon": round(response.Longitude(), 4),
                        "grid_elevation_m": response.Elevation(),
                    }
                )
            if len(batches) > 1:
                log(f"  {min(n * self.batch_size, len(pts))}/{len(pts)} sites done")

        long = _trim_trailing_gaps(pd.concat(frames, ignore_index=True), variables)
        data = WeatherData(long=long, locations=pd.DataFrame(locations), units=units)
        log(f"Done in {time.perf_counter() - began:.1f} s: {len(long):,} rows.")
        return data


def fetch_era5(
    points: PointsLike,
    start: DateLike,
    end: DateLike | None = None,
    variables: str | Iterable[str] = DEFAULT_VARIABLES,
    *,
    url: str = DEFAULT_URL,
    **kwargs,
) -> WeatherData:
    """One-call shortcut for ``Client(url).fetch(...)``. See :meth:`Client.fetch`."""
    return Client(url).fetch(points, start, end, variables, **kwargs)


def _to_frame(point: Point, response, variables: list[str]) -> tuple[pd.DataFrame, dict[str, str]]:
    hourly = response.Hourly()
    times = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
    )
    tz = response.Timezone()
    tz = tz.decode() if isinstance(tz, bytes) else tz
    if tz and tz not in ("GMT", "UTC"):
        times = times.tz_convert(tz)

    frame = pd.DataFrame({"site": point.name, "lat": point.lat, "lon": point.lon, "datetime": times})
    units = {}
    for i, variable in enumerate(variables):
        series = hourly.Variables(i)
        # float32 on the wire; widen and round so CSVs read 23.72, not 23.720001.
        frame[variable] = series.ValuesAsNumpy().astype("float64").round(2)
        units[variable] = _UNIT_NAMES.get(series.Unit(), "unknown")
    return frame, units


def _trim_trailing_gaps(long: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """Drop hours at the end with no data anywhere (ERA5 lags real time by ~5 days)."""
    has_data = long[variables].notna().any(axis=1)
    if not has_data.any():
        return long
    last = long.loc[has_data, "datetime"].max()
    return long[long["datetime"] <= last].reset_index(drop=True)


def _parse_date(value: DateLike, is_end: bool) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if text.isdigit() and len(text) == 4:
        return date(int(text), 12, 31) if is_end else date(int(text), 1, 1)
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"Could not read {value!r} as a date; use YYYY or YYYY-MM-DD") from None


def _logger(enabled: bool):
    def log(message: str) -> None:
        if enabled:
            print(message, file=sys.stderr, flush=True)

    return log
