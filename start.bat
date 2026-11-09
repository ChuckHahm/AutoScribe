@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo First run: setting up the environment...
  py -3 --version >nul 2>nul || winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
  py -3 setup.py || python setup.py || (echo Setup failed. If Python was just installed, close this window and run start.bat again. & pause & exit /b 1)
)
.venv\Scripts\python run.py
