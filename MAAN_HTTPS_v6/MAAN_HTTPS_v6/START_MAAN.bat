@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto fail
if not exist ".venv\installed-v6.ok" (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto fail
  echo installed>".venv\installed-v6.ok"
)
if "%~1"=="" goto online
if /I "%~1"=="--online" goto online
if /I "%~1"=="--public" goto online
".venv\Scripts\python.exe" app.py %*
goto end
:online
".venv\Scripts\python.exe" online.py
goto end
:fail
echo Setup failed. Send a screenshot for help.
:end
pause
