@echo off
cd /d "%~dp0"
echo Starting the Avia Global Forecast viewer...
echo Open http://localhost:8000 in your browser (it should open automatically).
python serve.py
if errorlevel 1 py serve.py
pause
