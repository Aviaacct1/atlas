@echo off
cd /d "%~dp0"
echo Starting Avia Cortex server WITH the on-demand QSI route service...
echo (this is the one that makes the "Run QSI candidates" button work)
python qsi_service.py
pause
