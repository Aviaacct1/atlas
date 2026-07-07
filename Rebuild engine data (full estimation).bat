@echo off
cd /d "%~dp0"
echo Checking Python packages (first run may take a minute)...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
echo.
echo Running full estimation + rebuild (needs E:\Avia\Global attached)...
python scripts\run_full_estimation.py
echo.
pause
