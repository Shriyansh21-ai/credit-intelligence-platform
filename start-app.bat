@echo off
REM ============================================================
REM  AI Credit System - one-click local launcher
REM  Starts the backend (FastAPI) and frontend (Vite) in their
REM  own windows, then opens the app in your default browser.
REM  Close either window (or press Ctrl+C in it) to stop that server.
REM ============================================================

cd /d "%~dp0"

echo Starting backend on http://127.0.0.1:8000 ...
start "AI Credit - Backend"  cmd /k ".venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"

echo Starting frontend on http://127.0.0.1:5173 ...
REM Must run from the frontend folder so vite loads frontend\vite.config.ts
REM (the TanStack Start plugin lives there; without it every route 404s).
start "AI Credit - Frontend" cmd /k "cd /d "%~dp0frontend" && node node_modules\vite\bin\vite.js dev --host 127.0.0.1 --port 5173"

echo Waiting for the servers to boot ...
timeout /t 12 /nobreak >nul

echo Opening the app in your browser ...
start "" "http://127.0.0.1:5173/login"

echo.
echo Done. Two server windows are now running.
echo Keep them open while you use the app; close them to stop.
