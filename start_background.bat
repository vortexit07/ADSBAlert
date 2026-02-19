@echo off
REM ADSBAlert background launcher
REM Run this batch file to start the app hidden; Flask will be accessible at http://localhost:5000

cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "" "%cd%\.venv\Scripts\pythonw.exe" tray.py
exit /b 0