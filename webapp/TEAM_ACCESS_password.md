# Team access with a single shared password

This replaces the Cloudflare Access (login) approach. Guests need no Cloudflare account. They open the address, type one shared password, and they are in.

## How it works now

The password is checked by the forecast server itself (HTTP Basic Auth), not by Cloudflare. Cloudflare's only job is the tunnel: carry `forecast.aviacortex.com` to `http://localhost:8000` on your machine. The password sits on the server behind it.

The password lives in one file:

    C:\Avia\avia_forecast_build\webapp\access_password.txt

The first line that is not a comment is the password. It currently reads:

    Cortex-Forecast-2026

Change it to whatever you want, save the file, restart the server. The file is git-ignored, so the secret never gets committed.

## One-time Cloudflare cleanup

You were part-way through adding a Cloudflare Access application for the forecast hostname. Don't. That is the thing that forces a Cloudflare login.

1. If you created an Access application for `forecast.aviacortex.com` under Zero Trust -> Access -> Applications, open it and delete it (or leave its policy empty and set to Bypass). If you never finished creating it, there is nothing to remove.
2. Keep the tunnel route. Under the Cortex tunnel's public hostnames, `forecast.aviacortex.com` must still point to `http://localhost:8000`. That is what serves the tool; the password is handled by the server, not here.

`app.aviacortex.com` (the QSI tool) is untouched. This only affects the forecast hostname.

## Starting it (your machine, leave running)

1. Windows key, type `powershell`, Enter.
2. Type and Enter: `cd C:\Avia\avia_forecast_build\webapp`
3. Type and Enter: `python qsi_service.py`
4. Wait for: `Avia Cortex server + QSI route service ...` and a line reading `access: shared password ON`. If instead it says `NO PASSWORD SET`, the password file is missing or empty, fix that and restart.
5. Leave this window open. Closing it takes the tool offline.

The tunnel (`cloudflared`) starts as it does for the QSI tool. Once both are running, the address is live.

## What to send a colleague

- Address: `https://forecast.aviacortex.com`
- Password: whatever is on the first line of `access_password.txt`
- Username: anything (leave the default, or type `team`). Only the password is checked.

Your own browser will ask for the password too, the server can't tell your machine apart from a guest coming down the tunnel. Type the same password.

## Changing or revoking the password

Edit the first non-comment line of `access_password.txt`, save, restart the server. Everyone then needs the new password. There is no per-person access at this stage; when you want to share more widely, we move to per-person identity (the Cloudflare Access route) so you can add and remove people individually.

## Security note

The shared password is the only thing standing in front of the licensed data (ACI, Sabre, OAG, Oxford Economics). Never run the server over the tunnel with `NO PASSWORD SET`. Pick a password that is not trivial to guess and share it out of band (not in the same email as the link).
