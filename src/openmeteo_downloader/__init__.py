"""Fast ERA5 weather downloads from a local Open-Meteo server.

Quick start::

    from openmeteo_downloader import fetch_era5

    data = fetch_era5(
        {"Cedar Rapids, IA": (41.9779, -91.6656), "Des Moines, IA": (41.5868, -93.6250)},
        start=1985,
        end=2025,
    )
    data.wide()                      # one column per site + All_Sites_Avg (deg F, UTC)
    data.to_csv("output", "iowa")    # wide + long CSVs
"""

from .client import DEFAULT_URL, Client, ServerNotRunningError, fetch_era5
from .config import Job, load_job, run_job
from .data import WeatherData
from .points import Point, to_points

__all__ = [
    "DEFAULT_URL",
    "Client",
    "Job",
    "Point",
    "ServerNotRunningError",
    "WeatherData",
    "fetch_era5",
    "load_job",
    "run_job",
    "to_points",
]
