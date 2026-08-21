@echo off
REM AEGIS AI Quant - Start Backend Server
REM Run this script to start the backend API server

echo Starting AEGIS AI Quant Backend...
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check if dependencies are installed
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r backend\requirements.txt
)

REM Start the backend server
echo Starting API server on http://localhost:8000
echo.
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

pause
