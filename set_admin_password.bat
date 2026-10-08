@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Start the app with run_windows.bat first to prepare its Python environment.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" set_admin_password.py
pause
