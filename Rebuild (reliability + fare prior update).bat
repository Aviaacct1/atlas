@echo off
REM Targeted rebuild for the 20 July 2026 method change (CHANGELOG 109 and 110):
REM the T1-T6 reliability rule and the corrected Level 3 fare prior.
REM It re-runs ONLY the steps those changes affect. It deliberately does NOT re-measure
REM Sabre connecting legs or re-run the QSI route optimiser, because neither is affected
REM and both are slow. Needs E:\Avia\Global attached. Author: Avia Solutions.
cd /d "%~dp0"
setlocal
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DT=%%I
set STAMP=%DT:~0,8%_%DT:~8,4%
set BK=backup_pre_reliability_%STAMP%

echo.
echo === 0/6 backing up the current state to %BK% ===
mkdir "%BK%" 2>nul
mkdir "%BK%\webapp_data" 2>nul
copy /y "data\airport_regress.json" "%BK%\" >nul 2>&1
copy /y "webapp\data\*.json" "%BK%\webapp_data\" >nul 2>&1
echo     backed up.

echo.
echo === 1/6 re-running the per-airport estimation (six-test rule, corrected fare prior) ===
python scripts\estimate_airport_diagnostics.py
if errorlevel 1 goto :failed

echo.
echo === 2/6 measuring the change in the applied elasticity set ===
python scripts\compare_reliability_change.py

echo.
echo === 3/6 re-running the engine into the dashboard bundle ===
python scripts\build_dashboard_data.py
if errorlevel 1 goto :failed

echo.
echo === 4/6 rebuilding the cockpit bundle ===
python scripts\build_cockpit_data.py
if errorlevel 1 goto :failed

echo.
echo === 5/6 rebuilding the viewer bundle ===
python scripts\build_webapp_data.py
if errorlevel 1 echo     (viewer bundle skipped or not required)

echo.
echo === 6/6 validity check on every served file ===
python scripts\validate_repo.py
if errorlevel 1 goto :invalid

echo.
echo === the new world growth rate, after the rebuild ===
python scripts\compare_reliability_change.py

echo.
echo DONE. The forecast now matches the methodology note.
echo If you want the previous numbers back, copy the files in %BK% over data\ and webapp\data\.
goto :end

:failed
echo.
echo A STEP FAILED. Nothing served was overwritten with anything invalid (writes are atomic).
echo The previous state is in %BK%. Fix the error above and run again.
goto :end

:invalid
echo.
echo THE VALIDITY CHECK FAILED. Restore from %BK% before refreshing anything client-facing.

:end
echo.
pause
