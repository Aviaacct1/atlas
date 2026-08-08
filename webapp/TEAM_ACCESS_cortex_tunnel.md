# Give the team access - your exact setup (Cortex tunnel, dashboard-managed)

Your "Cortex" tunnel already reaches your machine and serves app.aviacortex.com. We add a SECOND
web address on the SAME tunnel that points to the forecast server (port 8000), then put your
password in front of it. Nothing on the tunnel you already have changes.

Replace: FORECAST_URL = the address you want, e.g.  forecast.aviacortex.com  (same domain = least work).

--------------------------------------------------------------------------------------------------
## A. Start the forecast server (leave running)
A1. Windows key -> type  powershell  -> Enter.
A2. Type and Enter:      cd 'C:\Avia\avia_forecast_build\webapp'
A3. Type and Enter:      python qsi_service.py
A4. Wait for:  Avia Cortex server + QSI route service at http://localhost:8000/ . LEAVE THIS OPEN.
A5. Check locally: browser -> http://localhost:8000/dashboard.html . You should see the dashboard.

--------------------------------------------------------------------------------------------------
## B. Add the forecast address to the Cortex tunnel (a "Published application")
You are already on the right page: Networking -> Tunnels -> Cortex.
B1. Click the "Routes" tab at the top (next to "Overview"). (Or click "+ Add route" in the diagram.)
B2. Choose to add a PUBLIC hostname / published application (HTTP), NOT a private network route.
B3. Fill in:
      Subdomain:  forecast
      Domain:     aviacortex.com          (choose from the dropdown)
      Path:       (leave blank)
      Type / Service:  HTTP
      URL:        localhost:8000          (the forecast server from step A; QSI stays on 8010)
B4. Save / Publish. Cloudflare creates the DNS record automatically. Give it 1-2 minutes.

If the "Routes" tab only offers private-network routes (CIDRs), do it from the app side instead:
    Zero Trust -> Access -> Applications -> "Add an application" -> Self-hosted -> set the hostname
    (forecast + aviacortex.com); in the connection step point it at the Cortex tunnel, service
    http://localhost:8000. Saving there both publishes the hostname AND lets you set the password (Part C).

--------------------------------------------------------------------------------------------------
## C. Put your password in front of it (same as app.aviacortex.com)
C1. Left menu -> Access -> Applications.
C2. If FORECAST_URL is already listed (because Part B created it), click it -> Policies. Otherwise
    click "Add an application" -> Self-hosted -> Application domain: forecast + aviacortex.com -> Next.
C3. Add a policy: Name = Team, Action = Allow. Add a rule using the SAME method you use for
    app.aviacortex.com (the same emails, or the same one-time-PIN / password setup). Save.
C4. Required, not optional: the data is licensed (ACI, Sabre, OAG, Oxford Economics), so it must stay
    behind this password. Never remove it.

--------------------------------------------------------------------------------------------------
## D. Test
D1. Open a private/incognito browser window (so it does not reuse a login).
D2. Go to:  https://FORECAST_URL/dashboard.html  -> password prompt, then the dashboard.
D3. Try the cockpit:  https://FORECAST_URL/cockpit.html
D4. Send the team:  https://FORECAST_URL/  and the login method (two cards: dashboard, cockpit).
If D2 errors instead of prompting, wait 2-3 minutes (DNS/cert warm-up) and retry.

--------------------------------------------------------------------------------------------------
## E. Keep it up (survive reboots / closed window)
E1. The tunnel already runs as a service (your screenshot: healthy, 3 hours) - nothing to do.
E2. Auto-start the forecast server at logon: Windows key -> Task Scheduler -> "Create Task...":
      General: Name = Avia Forecast Server (tick "Run whether user is logged on or not" for after-reboot).
      Triggers: New -> "At log on".
      Actions:  New -> Start a program ->
        Program:  C:\Avia\avia_forecast_build\webapp\Run Avia Forecast (with QSI service).bat
        Start in: C:\Avia\avia_forecast_build\webapp
      OK to save.

--------------------------------------------------------------------------------------------------
## Refreshing the numbers later
    cd 'C:\Avia\avia_forecast_build'
    python scripts\run_full_estimation.py     (wait for "Rebuild complete and validated")
Tell the team to hard-refresh (Ctrl+F5). No restart; atomic writes mean a refresh mid-rebuild is safe.
