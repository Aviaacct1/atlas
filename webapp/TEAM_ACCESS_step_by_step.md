# Give the team access - exact steps, nothing assumed

Goal: your colleagues open a web address, type a password, and use the Global Forecast dashboard
and the analyst cockpit. It runs on YOUR machine and reaches them through the Cloudflare tunnel you
already use for the QSI tool. They can use it whenever your machine and the tunnel are running.

You will do four things: (A) start the forecast server, (B) give it a web address on your tunnel,
(C) put a password in front of it, (D) test it. Then (E) make it stay running.

Throughout, replace the ALL-CAPS placeholders:
  FORECAST_URL   = the web address you want, e.g.  forecast.aviacortex.com
                   (using aviacortex.com is easiest - it is already in your Cloudflare account)
  YOU            = your Windows user name (the folder under C:\Users)

--------------------------------------------------------------------------------------------------
## A. Start the forecast server (leave it running)

A1. Press the Windows key, type  powershell  , click "Windows PowerShell".
A2. In the blue window, type this line and press Enter:

        cd 'C:\Avia\avia_forecast_build\webapp'

A3. Type this line and press Enter:

        python qsi_service.py

A4. You should see lines starting with:  Avia Cortex server + QSI route service at http://localhost:8000/
    LEAVE THIS WINDOW OPEN. Closing it stops the server. (Minimise it if you like.)
A5. Check it locally: open a browser, go to  http://localhost:8000/dashboard.html . You should see
    the dashboard. If you do, the server is good. Move on.

--------------------------------------------------------------------------------------------------
## B. Give it a web address on your existing tunnel

You set up the QSI tool one of two ways. Find out which, then follow B-DASHBOARD or B-FILE.

B0. FIND OUT WHICH:
    - Open a browser, go to  https://one.dash.cloudflare.com  (Cloudflare Zero Trust). Sign in.
    - Left menu: Networks -> Tunnels. Click the tunnel that runs your QSI tool.
    - If you see a tab called "Public Hostname" (or "Public Hostnames") that you can edit here,
      your tunnel is DASHBOARD-managed -> use B-DASHBOARD.
    - If it says the tunnel is "locally managed" / configured by a file, use B-FILE.

### B-DASHBOARD (most common - all clicks, no files)
B1. On that tunnel's page, open the "Public Hostname" tab.
B2. Click "Add a public hostname".
B3. Fill in:
      Subdomain:  forecast            (the part before your domain; use what suits FORECAST_URL)
      Domain:     aviacortex.com      (pick your domain from the dropdown)
      Path:       (leave blank)
      Type:       HTTP
      URL:        localhost:8000
B4. Click "Save hostname". Done - skip to Section C.

### B-FILE (only if B0 said locally managed)
B1. Open File Explorer. In the address bar at the top type this and press Enter:

        %USERPROFILE%\.cloudflared

B2. Right-click  config.yml  -> Open with -> Notepad.
B3. You will see an "ingress:" list with your QSI hostname. Add the two "- hostname" lines for the
    forecast BEFORE the final "- service: http_status:404" line, so it looks like this
    (keep your existing tunnel: and credentials-file: lines exactly as they are):

        ingress:
          - hostname: app.aviacortex.com
            service: http://localhost:8010
          - hostname: FORECAST_URL
            service: http://localhost:8000
          - service: http_status:404

B4. File -> Save. Close Notepad.
B5. Create the DNS record: open PowerShell (Windows key -> type powershell -> Enter) and run
    (replace YOUR_TUNNEL_NAME with your tunnel's name; find it by running  cloudflared tunnel list ):

        cloudflared tunnel route dns YOUR_TUNNEL_NAME FORECAST_URL

B6. Restart the tunnel so it reads the new file:
    - If cloudflared runs as a Windows service: press Windows key, type  services  , open "Services",
      find "cloudflared", right-click -> Restart.
    - If you normally run it in a window: close that window, then run  cloudflared tunnel run YOUR_TUNNEL_NAME

--------------------------------------------------------------------------------------------------
## C. Put a password in front of it (Cloudflare Access)

C1. Still in Zero Trust ( https://one.dash.cloudflare.com ): left menu -> Access -> Applications.
C2. Click "Add an application" -> choose "Self-hosted".
C3. Application name:  Avia Global Forecast
C4. Under "Application domain" set:
      Subdomain:  forecast          Domain:  aviacortex.com     (match FORECAST_URL exactly)
C5. Click Next to the policy step. Create a policy:
      Policy name:  Team
      Action:  Allow
      Add a rule. Two easy choices:
        (a) Emails: add each colleague's email address (they get a one-time code by email to log in), OR
        (b) if you specifically want a shared password, use the same method you set for the QSI tool.
      Use the SAME approach you already use for cortex so the team's experience is identical.
C6. Click Next, then "Add application" to save.
C7. This is required, not optional: the data is licensed (ACI, Sabre, OAG, Oxford Economics), so it
    must stay behind this password. Never remove the Access policy.

--------------------------------------------------------------------------------------------------
## D. Test it

D1. On your own machine, open a NEW private/incognito browser window (so it does not use a cached login).
D2. Go to:  https://FORECAST_URL/dashboard.html
D3. You should be asked for the password / email code (Cloudflare Access). Enter it.
D4. You should then see the dashboard. Try the cockpit too:  https://FORECAST_URL/cockpit.html
D5. Send your colleagues the address  https://FORECAST_URL/  and the login method. They will land on a
    page with two cards: "Global forecast dashboard" and "Analyst cockpit".

If step D3 shows an error instead of a password prompt, wait 2-3 minutes (DNS/cert warm-up) and retry.

--------------------------------------------------------------------------------------------------
## E. Make it stay running (so it survives a reboot and a closed window)

E1. cloudflared as a service (runs at boot). In PowerShell run once:

        cloudflared service install

E2. The forecast server at logon. Press Windows key, type  Task Scheduler , open it.
    - Right side: "Create Task..." (not "Basic Task").
    - General tab: Name =  Avia Forecast Server . Tick "Run whether user is logged on or not" if you
      want it up after a reboot without signing in.
    - Triggers tab: New -> Begin the task: "At log on" -> OK.
    - Actions tab: New ->
        Action: Start a program
        Program/script:   C:\Avia\avia_forecast_build\webapp\Run Avia Forecast (with QSI service).bat
        Start in:         C:\Avia\avia_forecast_build\webapp
      -> OK.
    - Click OK to save (it may ask for your Windows password).
E3. From now on the server starts automatically. To stop it, end the python window or disable the task.

--------------------------------------------------------------------------------------------------
## Refreshing the numbers later (after any model change)

1. Close nothing. Open PowerShell.
2. Run:
        cd 'C:\Avia\avia_forecast_build'
        python scripts\run_full_estimation.py
3. Wait for "Rebuild complete and validated."
4. Tell the team to hard-refresh their browser (Ctrl+F5). No restart needed; the server serves the
   new files, and the writes are atomic so a refresh mid-rebuild never shows a broken page.
