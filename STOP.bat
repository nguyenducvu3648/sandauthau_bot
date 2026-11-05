@echo off
chcp 65001 >nul
echo Stopping all services...
echo.

REM Kill Backend
taskkill /FI "WINDOWTITLE eq Backend*" /F >nul 2>&1
echo ✓ Backend stopped

REM Kill Frontend
taskkill /FI "WINDOWTITLE eq Frontend*" /F >nul 2>&1
echo ✓ Frontend stopped

echo.
echo All services stopped.
pause
