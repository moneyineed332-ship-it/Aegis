@echo off
REM AEGIS AI Quant - Start Both Backend and Frontend
REM Run this script to start both servers

echo ========================================
echo    AEGIS AI Quant - Starting All Services
echo ========================================
echo.

REM Start backend in a new window
echo Starting Backend API Server...
start "AEGIS Backend" cmd /k "cd /d "%~dp0" && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"

REM Wait a bit for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in a new window
echo Starting Frontend Dev Server...
start "AEGIS Frontend" cmd /k "cd /d "%~dp0" && npm run dev"

echo.
echo ========================================
echo    AEGIS AI Quant is starting!
echo ========================================
echo.
echo    Backend API:  http://localhost:8000
echo    Frontend:     http://localhost:5173
echo    API Docs:     http://localhost:8000/docs
echo.
echo    Press any key to open the frontend...
echo ========================================
pause >nul

REM Open frontend in default browser
start http://localhost:5173

echo.
echo Close the command windows to stop the servers.
