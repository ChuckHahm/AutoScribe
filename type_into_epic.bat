@echo off
cd /d "%~dp0"
.venv\Scripts\python tools\keystroke_helper.py %*
