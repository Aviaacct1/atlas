# Global Aviation Forecast: how it all fits together
**Avia Solutions | 6 July 2026 | A plain walkthrough of where everything lives, what feeds it, and how to run and share it.**

## The two places everything lives
Everything moved off OneDrive because the sync kept corrupting files. There are now two homes.

The code lives on your C: drive at **C:\Avia\avia_forecast_build**. This is the whole engine: the Python that turns raw data into the forecast, the tests, the ingest scripts, and the web viewer. It is small and always on your machine.

The heavy data lives on your E: drive at **E:\Avia\Global**. Raw source files sit in subfolders (ACI, OEF), and everything the engine generates lands in **E:\Avia\Global\data**. E: is your portable drive, so it needs to be plugged in when you run anything that touches the data.

The old OneDrive project folder still holds the earlier write-up documents, but the live build is no longer there.

## The data that feeds it
Five sources, each doing one job.

Sabre O&D (the true origin-and-destination journeys) is the demand base. It lives in the QSI tool's database and in C:\Avia\sabre.duckdb. It tells us how many people actually travel between each pair of airports.

ACI traffic (true terminal throughput per airport, 1991 to 2024) is the anchor. It lives in E:\Avia\Global\ACI. Terminal passengers minus Sabre O&D is the connecting traffic, which is how we identify the hubs and size their transfer flows.

OAG schedules (every flight, with seats) give the route structure. They live in C:\Avia\oag.duckdb. From these we work out each hub's onward network: which regions it feeds and in what proportion.

Oxford Economics GDP (every country, history and forecast to 2050) is the growth driver. It lives in E:\Avia\Global\OEF. Each country's air traffic grows in line with its own economy.

The airport reference and catchments come from the QSI tool, which is a connected folder.

## What the engine does, in plain terms
It starts from Sabre O&D for the base year and grows each airport's local traffic in line with its home country's OEF GDP, softened as mature markets approach saturation. It then anchors the whole thing to ACI's real 2024 throughput and adds the connecting passengers on top, routing each hub's transfers across the regions its OAG network actually serves. The result is terminal passengers with transfers for every airport out to 2050, which is the number airports and investors use. It comes out at 3.05 per cent a year worldwide, right alongside ACI's own 3.4 per cent forecast.

There is one modelling choice left open for Jess: whether to use the income elasticities we estimated from the long ACI history (which push growth to about 4 per cent) or the more conservative literature values (which give the 3.05 per cent the model currently ships with). It is a single setting in the configuration file.

## Running the viewer on your machine
The viewer is a small web page backed by the forecast data. To run it:

1. Make sure E: is plugged in (only needed if you also want to refresh the numbers).
2. Go to **C:\Avia\avia_forecast_build\webapp** and double-click **Run Avia Forecast.bat**.
3. Your browser opens **http://localhost:8000**. If it does not, type that address in.
4. Leave the small black window open while you use it. Ctrl+C in that window stops it.

The page shows the world and regional forecast, a Baseline / High / Low scenario switch, and an airport explorer where you type any code or city and see that airport's forecast, its connecting share, and its hub network. There is a top-airports table you can click through.

## Refreshing the numbers after an engine change
If the engine or its inputs change, rebuild the viewer's data from **C:\Avia\avia_forecast_build**:

    python scripts\build_webapp_data.py

That rewrites the files in webapp\data. If the viewer is already running, just refresh the browser; no restart needed.

## Sharing it with the team and clients
Two ways, both using the Cloudflare tunnel you already run for the QSI tool.

While your machine is on, add one hostname to your existing tunnel so the team reaches the forecast at its own address. The full steps are in **webapp\DEPLOY_cloudflare.md**, but in short: run the viewer on port 8000, add an ingress rule mapping **app.avia-analytics.com** to **localhost:8000** in the tunnel config, run the one DNS command, restart the tunnel, and apply the same password policy you use for cortex. QSI stays on aviacortex.com, the forecast gets avia-analytics.com, and aviaintellect stays spare. Both run side by side because they are on different ports.

If you would rather it not depend on your laptop being on, the viewer is entirely static files, so it can instead sit on Cloudflare Pages pointed at avia-analytics.com and run around the clock with no machine involved.

Either way keep the password on, because the underlying ACI, Sabre, OAG and Oxford Economics data is licensed for internal use.

## The one-line summary
Code on C:, data on E:, five real data sources feeding one engine, a forecast that matches the industry, a viewer you run with a double-click, and a tunnel that puts it on avia-analytics.com behind a password for the team and prospects.
