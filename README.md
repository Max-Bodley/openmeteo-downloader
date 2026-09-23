# openmeteo-downloader

Get decades of hourly ERA5 weather for any set of sites in **seconds instead of days**.

Downloading from the Copernicus CDS means queueing one request per year, fetching
NetCDF files, and extracting points yourself. This package gets the same ERA5
reanalysis from a local [Open-Meteo](https://open-meteo.com) server running in
Docker. It returns point data directly as pandas DataFrames or CSVs.

| | CDS API | openmeteo-downloader |
|---|---|---|
| 46 years × 2 sites, hourly temperature | hours to days (queued requests) | ~1 min first time, **~3 s** after that |
| Account / API key | required | none |
| Output | NetCDF grids to post-process | point time series, ready for pandas or Excel |

## Setup (once)

**1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and [uv](https://docs.astral.sh/uv/getting-started/installation/).**
uv manages Python and all the dependencies for you:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**2. Get the code and install it:**

```bash
git clone <repo url> openmeteo-downloader    # or unzip the folder you were sent
cd openmeteo-downloader
uv sync                                      # installs Python 3.13 + dependencies into .venv
```

**3. Start the weather server** from the same folder:

```bash
docker compose up -d             # starts the server on http://127.0.0.1:6000
```

The server streams data from Open-Meteo's public S3 bucket as it's needed and
caches it. There is no large up-front download. The first request for a region
takes about a minute; repeat requests take seconds. The container restarts
automatically with Docker.

## Quickest: the ready-made script

Edit the CONFIG block at the top of `download_era5.py` (output folder, sites,
dates, variables), then from the project folder run:

```bash
uv run download_era5.py
```

## Option A: Python

```python
from openmeteo_downloader import fetch_era5

sites = {
    "Cedar Rapids, IA": (41.9779, -91.6656),
    "Des Moines, IA":   (41.5868, -93.6250),
}

data = fetch_era5(sites, start="1980-01-01", end="2025-12-31")   # hourly temperature_2m, deg F, UTC
print(data)
# WeatherData(2 sites, 806,496 rows, 1980-01-01 00:00 to 2025-12-31 23:00)
#   sites:     Cedar Rapids, IA, Des Moines, IA
#   variables: temperature_2m (F)

data.wide()                  # DataFrame: datetime x site, plus All_Sites_Avg
data.long                    # DataFrame: site, lat, lon, datetime, temperature_2m
data.site("Des Moines, IA")  # one site, indexed by datetime
data.locations               # which ERA5 grid cell each site was matched to

data.to_csv(r"T:\Python Tools\Load Analysis Programs\Test Pull", name="iowa")
```

More variables, other units, or local time:

```python
data = fetch_era5(
    "sites.csv",                                  # CSV with name, lat, lon columns
    start="1990-06-01", end="2020-08-31",
    variables=["temperature_2m", "dew_point_2m", "relative_humidity_2m", "wind_speed_10m"],
    temperature_unit="celsius",
    wind_speed_unit="mph",
    timezone="America/Chicago",
)
data.wide("dew_point_2m")
```

To pull repeatedly or use a non-default server, create a `Client`:

```python
from openmeteo_downloader import Client

client = Client("http://127.0.0.1:6000")
summer = client.fetch(sites, "2024-06-01", "2024-08-31", "shortwave_radiation")
```

## Option B: Job file (no code)

From the project folder:

```bash
uv run openmeteo-downloader init            # writes an example config.toml
# edit sites / dates / variables in config.toml
uv run openmeteo-downloader run config.toml
uv run openmeteo-downloader check           # is the server up?
uv run openmeteo-downloader compose         # writes docker-compose.yml if you've lost it
```

```toml
output_dir = "output"
name       = "era5"
formats    = ["wide", "long"]

start     = "1980-01-01"
end       = "2025-12-31"
variables = ["temperature_2m"]

temperature_unit = "fahrenheit"
timezone         = "UTC"

[points]
"Cedar Rapids, IA" = [41.9779, -91.6656]
"Des Moines, IA"   = [41.5868, -93.6250]
```

Instead of `[points]` you can give `points_file = "sites.csv"`. The generated
`config.toml` documents every option.

## Output files

| File | Contents |
|---|---|
| `{name}_{variable}_{unit}_wide.csv` | `datetime`, one column per site, `All_Sites_Avg` (one file per variable) |
| `{name}_long.csv` | `site, lat, lon, datetime, temperature_2m_F, ...` (one row per site-hour) |
| `{name}_locations.csv` | each site with the ERA5 grid cell (`grid_lat`, `grid_lon`, `grid_elevation_m`) it was matched to |

UTC timestamps are written without an offset (`1980-01-01 00:00:00`), so Excel
reads them as dates.

## Variables

Any hourly variable from the
[Open-Meteo historical API](https://open-meteo.com/en/docs/historical-weather-api) works. Common ones:

`temperature_2m`, `dew_point_2m`, `relative_humidity_2m`, `apparent_temperature`,
`precipitation`, `snowfall`, `cloud_cover`, `wind_speed_10m`, `wind_direction_10m`,
`wind_gusts_10m`, `shortwave_radiation`, `direct_normal_irradiance`, `surface_pressure`

## Good to know

- **Same data as Copernicus.** `model="era5"` is the ECMWF ERA5 reanalysis on a
  0.25° grid, 1940 to about 5 days ago. Each site gets the value of its
  nearest grid cell, like `method="nearest"` in xarray. `model="era5_land"` gives a finer 0.1° grid from 1950.
- **Elevation correction is off by default,** so values match raw ERA5.
  Pass `elevation_correction=True` to let Open-Meteo adjust temperature to each
  site's actual elevation.
- **Times are UTC by default** (ERA5's native time). Pass an IANA timezone
  such as `"America/Chicago"` to get local time for all sites.
- **Recent days** that ERA5 hasn't published yet are trimmed off the end.
- **Many sites** are split into batches of 10 per request (`Client(batch_size=...)`).

## Coming from the CDS script

| CDS script | Here |
|---|---|
| `POINTS = {label: (lat, lon)}` | same dict, passed to `fetch_era5(...)` or `[points]` |
| `YEARS = range(2021, 2026)` | `start="2021-01-01", end="2025-12-31"` |
| `variable: "2m_temperature"` + K → °F | `variables="temperature_2m"` (°F by default) |
| `INTERP_METHOD = "nearest"` | always nearest grid cell |
| wide CSV with `All_Sites_Avg` / `_long.csv` | `data.to_csv(...)` writes both |
| `~/.cdsapirc`, per-year NetCDF files | not needed |

## Development

```bash
uv sync
uv run pytest          # server tests are skipped if the server isn't running
uv build               # optional: makes dist/*.whl
```
