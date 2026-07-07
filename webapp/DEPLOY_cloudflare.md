# Deploying the forecast viewer via the existing Cloudflare tunnel

You already run the QSI tool at app.aviacortex.com -> localhost:8010 through one
cloudflared tunnel with a password (Cloudflare Access). Add the global forecast to the
SAME tunnel on its own domain. No second tunnel, no second machine.

Recommended split: aviacortex.com = QSI/Cortex, avia-analytics.com = global forecast.

## Steps (on the machine running the tunnel)
1. Start the forecast viewer, leaving QSI running:
      cd C:\Avia\avia_forecast_build\webapp
      python serve.py            (serves on localhost:8000; set a different port with:  set PORT=8000 )

2. Add an ingress rule to the tunnel config (usually %USERPROFILE%\.cloudflared\config.yml).
   List specific hostnames first, catch-all last:

      tunnel: <your-tunnel-name-or-UUID>
      credentials-file: C:\Users\<you>\.cloudflared\<UUID>.json
      ingress:
        - hostname: app.aviacortex.com
          service: http://localhost:8010
        - hostname: app.avia-analytics.com
          service: http://localhost:8000
        - service: http_status:404

3. Point the new hostname at the tunnel (creates the DNS record automatically):
      cloudflared tunnel route dns <your-tunnel-name> app.avia-analytics.com

4. Restart the tunnel so it picks up the new rule:
      (stop the running cloudflared, then)   cloudflared tunnel run <your-tunnel-name>
   or restart the Windows service if you installed it as one.

5. In Cloudflare Zero Trust > Access > Applications, add app.avia-analytics.com and apply
   the same policy (password / one-time PIN / allowed emails) you use for cortex.

The team then opens https://app.avia-analytics.com, enters the password, and uses the
forecast while your machine is running. Keep the serve.py window open; the tunnel only
reaches it while it is running.

## Notes
- Two local servers on different ports (8010 QSI, 8000 forecast) run happily side by side.
- To refresh the numbers after an engine change:
      cd C:\Avia\avia_forecast_build
      python scripts\build_webapp_data.py
  then just leave serve.py running (it serves the updated data/ files; no restart needed).
- The data is licensed (ACI, Sabre, OAG, Oxford Economics) so keep the Access password on.
- If you would rather it not depend on your laptop being on, the viewer is fully static
  (index.html + data/*.json) and can instead be hosted on any static host with the tunnel
  or a Cloudflare Pages deployment pointed at avia-analytics.com.
