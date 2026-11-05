@echo off
chcp 65001 >nul
echo ========================================
echo   Starting V4 Search Service
echo ========================================
echo.

REM Check Elasticsearch
echo [1/3] Checking Elasticsearch...
curl -k -s https://localhost:9200 >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Elasticsearch is NOT running!
    echo    Start it first: elasticsearch.bat
    echo.
    pause
    exit /b 1
)
echo ✓ Elasticsearch is running
echo.

REM Start Backend
echo [2/3] Starting Backend (port 8000)...
cd backend
start "Backend" cmd /c "python -m uvicorn app.main:app --reload --port 8000"
cd ..
timeout /t 3 /nobreak >nul
echo ✓ Backend started at http://localhost:8000
echo.

REM Start Frontend
echo [3/3] Starting Frontend (port 3000)...
cd frontend
start "Frontend" cmd /c "python -m http.server 3000"
cd ..
timeout /t 2 /nobreak >nul
echo ✓ Frontend started at http://localhost:3000
echo.

echo ========================================
echo   All services started!
echo ========================================
echo.
echo 🌐 Open in browser: http://localhost:3000
echo 📊 Backend API: http://localhost:8000/docs
echo 💚 Health check: http://localhost:8000/health
echo.
echo Press any key to open browser...
pause >nul
start http://localhost:3000
