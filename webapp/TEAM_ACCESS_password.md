# Team access with a single shared password

Rewritten 16 August 2026. The previous version of this file printed the live password in a git-tracked document, and the value it printed was stale, so anyone following it handed a colleague the wrong secret while the repository published an old one. No password value appears in this file or any tracked file; validate_repo should be extended to scan for that (workplan item 1.6).

## Where things stand

The live hostname is `https://atlas.aviacortex.com`. Two layers stand in front of the tool, and both are wanted: Cloudflare Access (one-time PIN) on the hostname, then the forecast server's own shared password (HTTP Basic Auth) in `qsi_service.py`. The section in the old version of this file that instructed deleting the Access application is withdrawn; Access stays.

The password lives in one file on the serving machine, and nowhere else:

    C:\src\atlas\webapp\access_password.txt

The first line that is not a comment is the password. The file is gitignored, so each machine sets its own and the secret never enters the repository. `FORECAST_PASSWORD` as an environment variable overrides the file.

Since 16 August 2026 the server fails closed: with no password set it refuses to start and names the remedy. The old open-with-a-warning behaviour is gone. Local development without a password needs `AVIA_ALLOW_OPEN=1`, which must never be set on a machine the tunnel reaches. `serve.py` now binds loopback only and is for local preview; it is not a serving path.

## Starting it (the workstation, leave running)

1. PowerShell: `cd C:\src\atlas\webapp`
2. `& '.\Run Avia Forecast (with QSI service).bat'`
3. Wait for `access: shared password ON`. If the server refuses to start, the password file is missing or empty; set it and go again.
4. `cloudflared` runs as a service with the tunnel token; once both are up the address is live.

## What to send a colleague

The address, and the password out of band (never in the same message as the address). Username can be anything; only the password is checked. They will also receive a one-time PIN from Cloudflare Access at their approved email on first visit.

## Changing or revoking the password

Edit the first non-comment line of `access_password.txt`, save, restart the server. Everyone then needs the new value. There is no per-person access at this stage; per-person identity is the Cloudflare Access policy, which is where individual adds and removes happen.

## Security note

The shared password and the Access PIN are what stand in front of the licensed data (ACI, Sabre, OAG, Oxford Economics). Pick a password that is not trivial to guess, share it out of band, and never commit a file containing it.

Copyright Avia Solutions Limited. All rights reserved.
