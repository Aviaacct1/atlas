# Team access via the existing Cloudflare tunnel (same pattern as the QSI tool)

You already run the QSI tool at app.aviacortex.com -> localhost:8010 through one cloudflared
tunnel with a password (Cloudflare Access). Add the global forecast to the SAME tunnel on its
own subdomain. No second tunnel, no second machine. Suggested split: aviacortex.com = QSI/Cortex,
avia-analytics.com = the global forecast (pick whatever subdomain you like).

The team then opens the URL, enters the password, and uses the dashboard AND the analyst cockpit,
including Run QSI, while your machine and the tunnel are running.

## Steps (on the machine running the tunnel)

1. Run the forecast SERVER (use qsi_service.py, not serve.py - it serves the site AND answers the
   cockpit's Run QSI button; serve.py cannot). QSI keeps running on 8010; this uses 8000:
      cd C:\Avia\avia_forecast_build\webapp
      python qsi_service.py

2. Add an ingress rule to the tunnel config (usually %USERPROFILE%\.cloudflared\config.yml).
   Specific hostnames first, catch-all last:

      tunnel: <your-tunnel-name-or-UUID>
      credentials-file: C:\Users\<you>\.cloudflared\<UUID>.json
      ingress:
        - hostname: app.aviacortex.com
          service: http://localhost:8010
        - hostname: app.avia-analytics.com
          service: http://localhost:8000
        - service: http_status:404

3. Point the new hostname at the tunnel (creates the DNS record):
      cloudflared tunnel route dns <your-tunnel-name> app.avia-analytics.com

4. Restart the tunnel so it picks up the new rule (or restart the Windows service if installed):
      cloudflared tunnel run <your-tunnel-name>

5. Cloudflare Zero Trust -> Access -> Applications: add app.avia-analytics.com and apply the SAME
   policy (password / one-time PIN / allowed emails) you use for cortex. This is required: the data
   is licensed (ACI, Sabre, OAG, Oxford Economics), so it must sit behind Access, never open.

## Keeping it up for the test stage (so it does not depend on a window staying open)

- cloudflared: install once as a Windows service so it runs at boot and survives logout:
      cloudflared service install
- the forecast server: run qsi_service.py at logon via Task Scheduler:
    Task Scheduler -> Create Task -> Trigger: At log on -> Action: Start a program
      Program:  C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe
      Arguments: qsi_service.py
      Start in: C:\Avia\avia_forecast_build\webapp
  (or use "Run Avia Forecast (with QSI service).bat" as the action). Set it to run whether or not
  you are logged on if you want it up after a reboot without signing in.
- The tool is reachable only while BOTH the tunnel and qsi_service.py are running on your machine.
  That is fine for the test stage; for always-on later, host the static site + data on Cloudflare
  Pages and keep only the QSI compute endpoint on your box.

## Refreshing the numbers after an engine change
      cd C:\Avia\avia_forecast_build
      python scripts\run_full_estimation.py     (or double-click the rebuild .bat)
  The server serves the updated data/*.json with no restart; the team just hard-refreshes (Ctrl+F5).
  All writes are atomic, so a mid-rebuild refresh never serves a half-written file.

## Notes
- Two local servers on different ports (8010 QSI, 8000 forecast) run side by side.
- Run QSI on the cockpit works over the tunnel because qsi_service.py is the server and the QSI tool
  + Sabre/OAG live on the same box.
- Landing page: app.avia-analytics.com/  ->  dashboard.html (client view) and cockpit.html (analyst).
