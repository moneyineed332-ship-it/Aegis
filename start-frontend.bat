@echo off
REM AEGIS AI Quant - Start Frontend Dev Server
REM Run this script to start the frontend development server

echo Starting AEGIS AI Quant Frontend...
echo.

cd /d "%~dp0"

REM Check if Node.js is available
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if dependencies are installed
if not exist "node_modules" (
    echo Installing dependencies...
    npm install
)

REM Start the frontend dev server
echo Starting Vite dev server on http://localhost:5173
echo.
npm run dev

pause
