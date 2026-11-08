@echo off
echo Stopping NOVA Workstation on port 46815...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":46815" ^| findstr "LISTENING"') do (
    echo Terminating PID: %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo NOVA workstation stopped.
timeout /t 2 >nul
