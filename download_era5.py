# -*- coding: utf-8 -*-
"""
ERA5 hourly weather for specific coordinates, via a local Open-Meteo server.
Writes a wide CSV (one column per site + All_Sites_Avg) and a long-format CSV.

One-time setup:
    1. Install Docker Desktop:  https://www.docker.com/products/docker-desktop/
    2. Install uv (it manages Python and all dependencies for you):
           powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    3. Get the code and install it:
           git clone <repo url> openmeteo-downloader    (or unzip the folder you were sent)
           cd openmeteo-downloader
           uv sync
    4. Start the weather server from that folder (it keeps running after restarts):
           docker compose up -d

Each time:
    1. Edit the CONFIG block below.
    2. From the project folder, run:
           uv run download_era5.py
"""

from openmeteo_downloader import fetch_era5

# ============================== CONFIG ==============================
# Where to save files. Use a raw string or forward slashes on Windows.
OUTPUT_DIR = r"T:\Python Tools\Load Analysis Programs\Test Pull"        # <-- set folder here
OUTPUT_NAME = "era5"

# Points to Extract
POINTS = {
    "Cedar Rapids, IA": (41.9779, -91.6656),
    "Des Moines, IA": (41.5868, -93.6250),
}

START_DATE = "1980-01-01"                      # YYYY-MM-DD
END_DATE   = "2025-12-31"                      # YYYY-MM-DD, inclusive

# Full list: https://open-meteo.com/en/docs/historical-weather-api
VARIABLES = ["temperature_2m"]

TEMPERATURE_UNIT = "fahrenheit"                # or "celsius"
TIMEZONE         = "UTC"                       # or e.g. "America/Chicago"

WRITE_WIDE = True                              # one column per site + All_Sites_Avg
WRITE_LONG = True                              # one row per site-hour
# ===================================================================


if __name__ == "__main__":
    data = fetch_era5(
        POINTS,
        start=START_DATE,
        end=END_DATE,
        variables=VARIABLES,
        temperature_unit=TEMPERATURE_UNIT,
        timezone=TIMEZONE,
    )
    print(data)

    formats = [f for f, on in (("wide", WRITE_WIDE), ("long", WRITE_LONG)) if on]
    for path in data.to_csv(OUTPUT_DIR, OUTPUT_NAME, formats):
        print(f"Wrote {path}")
