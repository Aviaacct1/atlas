@echo off
cd /d "%~dp0"
echo Starting Avia Cortex server WITH the on-demand QSI route service...
echo (this is the one that makes the "Run QSI candidates" button work)
echo Open http://localhost:8000 in your browser.
rem Call the interpreter inside the repository's own .venv by path. "python" is whatever
rem is first on PATH, which on a machine running several Avia tools is not necessarily
rem the one that has this tool's dependencies installed.
rem The QSI route service imports Meridian from AVIA_QSI_APP, which is C:\src\meridian\app.
if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" qsi_service.py
) else (
    echo No .venv found. Create one: py -3.12 -m venv .venv
    echo then: .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo Falling back to the system interpreter.
    python qsi_service.py
)
pause
