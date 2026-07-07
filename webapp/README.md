# Avia Global Aviation Forecast - team viewer

An interactive view of the global forecast: world and regional terminal-passenger
projections to 2050, three scenarios, and every modelled airport with its growth and
hub connecting profile. Built from ACI throughput, Sabre O&D, OAG routing and Oxford
Economics GDP; Avia Solutions analysis.

## Run it locally (Windows)
1. Double-click **Run Avia Forecast.bat** (needs Python 3, already on this machine).
2. Your browser opens **http://localhost:8000**. If not, open that address manually.
3. Ctrl+C in the black window to stop.

No installation, no internet needed except the charting library (loaded from a CDN).

## Share it with the team on the office network
The server listens on all interfaces, so while it is running others can reach it at
**http://<your-computer-IP>:8000** (find your IP with `ipconfig`). Keep the window open.

## Put it on a test domain (e.g. avia-analytics)
The whole app is static: `index.html` plus the JSON files in `data/`. It needs no
server-side logic, so it can be hosted on any static host (an internal web server, S3 +
CloudFront, Netlify, or an Avia box) with the `avia-analytics` domain pointed at it.
Refresh the numbers by re-running `python scripts/build_webapp_data.py` in the engine
folder and re-uploading `webapp/data/`. (The underlying data is licensed - ACI, Sabre,
OAG, Oxford Economics - so keep any deployment access-controlled to the team.)

## Refresh the data after an engine change
From `C:\Avia\avia_forecast_build`:  `python scripts\build_webapp_data.py`
That rewrites `webapp/data/*.json` from the current engine run.
