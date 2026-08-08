@echo off
cd /d "%~dp0"
echo Starting the Avia Global Forecast viewer...
echo Open http://localhost:8000 in your browser (it should open automatically).
rem Call the interpreter inside the repository's own .venv by path. "python" is whatever
rem is first on PATH, which on a machine running several Avia tools is not necessarily
rem the one that has this tool's dependencies installed.
if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" serve.py
) else (
    echo No .venv found. Create one: py -3.12 -m venv .venv
    echo then: .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo Falling back to the system interpreter.
    python serve.py
    if errorlevel 1 py serve.py
)
pause
