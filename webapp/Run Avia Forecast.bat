@echo off
rem Disarmed 16 August 2026. This launcher used to start serve.py, which has no
rem authentication, on the same port the Cloudflare tunnel forwards. One double-click
rem served the licensed ACI / Sabre / OAG / OEF bundle open. It now hands over to the
rem authenticated launcher; serve.py remains for localhost-only preview via
rem "python serve.py" by hand, and now binds 127.0.0.1 only.
echo This launcher is retired: it started an UNAUTHENTICATED server on the tunnel port.
echo Starting the authenticated service instead...
call "%~dp0Run Avia Forecast (with QSI service).bat"
