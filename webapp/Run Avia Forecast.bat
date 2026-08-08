@echo off
cd /d "%~dp0"
echo Starting the Avia Global Forecast viewer...
echo Open http://localhost:8000 in your browser (it should open automatically).
rem Use the interpreter inside the repository's own .venv. "python" is whatever is first
rem on PATH, which on a machine running several Avia tools is not necessarily the one
rem with this tool's dependencies. No parenthesised if/else block: cmd.exe handles those
rem badly, and this file must be CRLF for the same reason.
set "PY=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PY%" goto novenv
goto run
:novenv
echo No .venv found at %~dp0..\.venv
echo Create one:  py -3.12 -m venv .venv
echo Then:        .venv\Scripts\python.exe -m pip install -r requirements.txt
echo Falling back to the system interpreter.
set "PY=python"
:run
"%PY%" serve.py
pause
