# openmeteo-downloader

Downloads hourly ERA5 weather data for a list of sites and saves it as CSV.

## How it works

A local [Open-Meteo](https://open-meteo.com) server runs in Docker on your machine.
It serves the ECMWF ERA5 reanalysis (the same dataset as Copernicus CDS),
pulling data from Open-Meteo's public S3 bucket as needed and caching it locally.
This package asks that server for point time series and writes the results to CSV.
The first request for a region takes about a minute; repeat requests take seconds.

## Setup (once)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and
   [uv](https://docs.astral.sh/uv/getting-started/installation/).
2. Get the code and install it:
   ```bash
   git clone <repo url> openmeteo-downloader
   cd openmeteo-downloader
   uv sync
   ```
3. Start the weather server (it restarts automatically with Docker):
   ```bash
   docker compose up -d
   ```

## Usage

Edit the CONFIG block at the top of `download_era5.py` (output folder, sites,
dates, variables), then run:

```bash
uv run download_era5.py
```

The script writes these files to the output folder:

| File | Contents |
|---|---|
| `era5_temperature_2m_F_wide.csv` | one column per site, plus `All_Sites_Avg` |
| `era5_long.csv` | one row per site and hour |
| `era5_locations.csv` | the ERA5 grid cell each site was matched to |

Times are in UTC and temperatures in °F by default. Each site takes the value of
its nearest ERA5 grid cell (0.25°). Other variables such as `dew_point_2m`,
`relative_humidity_2m` and `wind_speed_10m` are listed in the
[Open-Meteo docs](https://open-meteo.com/en/docs/historical-weather-api).

## Using it from Python

```python
from openmeteo_downloader import fetch_era5

data = fetch_era5({"Des Moines, IA": (41.5868, -93.6250)}, "1980-01-01", "2025-12-31")
data.wide()                 # DataFrame: datetime x site
data.to_csv("output", "iowa")
```

## Attribution

Data: ERA5, Copernicus Climate Change Service, via Open-Meteo.com (CC BY 4.0).
