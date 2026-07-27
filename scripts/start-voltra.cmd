@echo off
REM ============================================================
REM Voltra autostart launcher (runs at Windows login)
REM Starts Docker Desktop if needed, waits for the daemon, then
REM brings up the compose stack. Idempotent + safe to run twice.
REM Installed to the Startup folder by scripts/install-autostart.ps1.
REM ============================================================
setlocal
set "DOCKER=C:\Program Files\Docker\Docker\Docker Desktop.exe"
set "DOCKERCLI=C:\Program Files\Docker\Docker\resources\bin\docker.exe"
set "PROJ=C:\Server\solsignal"
set "LOG=%PROJ%\user_data\logs\autostart.log"

echo [%date% %time%] autostart begin >> "%LOG%"

REM Start Docker Desktop if it isn't already running
tasklist /FI "IMAGENAME eq Docker Desktop.exe" | find /I "Docker Desktop.exe" >nul
if errorlevel 1 (
    echo [%date% %time%] launching Docker Desktop >> "%LOG%"
    start "" "%DOCKER%"
)

REM Wait up to ~3 minutes for the daemon to answer
set /a tries=0
:waitloop
"%DOCKERCLI%" info >nul 2>&1 && goto ready
set /a tries+=1
if %tries% geq 36 goto giveup
REM ping-based sleep (~5s): unlike `timeout`, works with no console /
REM redirected stdin, so this is robust under Task Scheduler too.
ping -n 6 127.0.0.1 >nul
goto waitloop

:ready
cd /d "%PROJ%"
"%DOCKERCLI%" compose up -d >> "%LOG%" 2>&1
echo [%date% %time%] compose up -d done >> "%LOG%"
goto end

:giveup
echo [%date% %time%] ERROR: Docker daemon did not come up in 3 min >> "%LOG%"

:end
endlocal
