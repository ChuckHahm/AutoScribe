@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto run

echo First run: setting up the environment...
set "PYEXE=%LocalAppData%\Programs\Python\Python311\python.exe"

rem Use a real Python if one exists. A bare "python" on a fresh Windows is only a Microsoft Store stub, so do not rely on it.
py -3 --version >nul 2>nul && goto haspy
if exist "%PYEXE%" goto haspath

echo Installing Python 3.11 (one-time download from python.org, about 25 MB)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile \"$env:TEMP\python-installer.exe\" -UseBasicParsing"
if not exist "%TEMP%\python-installer.exe" goto fail
"%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0
if not exist "%PYEXE%" goto fail

:haspath
"%PYEXE%" setup.py
if errorlevel 1 goto fail
goto run

:haspy
py -3 setup.py
if errorlevel 1 goto fail
goto run

:fail
echo.
echo Setup failed. Check your internet connection and try again. See INSTALL.md for manual steps.
pause
exit /b 1

:run
.venv\Scripts\python run.py
