@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

title NOVA - Advanced Local AI Agent and Workstation
echo =====================================================================
echo   NOVA -- Advanced Local AI Agent and Workstation
echo =====================================================================
echo.

:: 1. Locate Python (.venv preferred if available)
set PYTHON_BIN=python
if exist "%~dp0.venv\Scripts\python.exe" set PYTHON_BIN="%~dp0.venv\Scripts\python.exe"
%PYTHON_BIN% --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not found in system PATH.
    echo Please install Python 3.11 or newer from https://www.python.org/
    pause
    exit /b 1
)

:: 2. Check Port 46815 availability
netstat -ano | findstr ":46815" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [ERROR] Port 46815 is already in use by another process.
    echo NOVA requires port 46815 to run. Please terminate the conflicting process.
    pause
    exit /b 1
)

:: 3. Set Working Directory and Python Path
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"
set PYTHONPATH=%SCRIPT_DIR%

:: 4. Start NOVA Server
echo [INFO] Starting NOVA Workstation on http://127.0.0.1:46815 ...
echo [INFO] Press Ctrl+C in this terminal to gracefully shut down.
echo.

:: Launch browser in background after 2 seconds
start /b cmd /c "timeout /t 2 >nul & start http://127.0.0.1:46815"

:: Run Uvicorn directly
%PYTHON_BIN% -m uvicorn backend.app.main:app --host 127.0.0.1 --port 46815 --log-level info

pause
