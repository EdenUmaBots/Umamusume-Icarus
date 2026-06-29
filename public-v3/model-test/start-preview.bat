@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  start "Seiun Sky PMX preview server" /min py -3 -m http.server 8765 --bind 127.0.0.1
) else (
  where python >nul 2>nul
  if %ERRORLEVEL% NEQ 0 (
    echo Python was not found. Install Python or run a local static HTTP server in this folder.
    pause
    exit /b 1
  )
  start "Seiun Sky PMX preview server" /min python -m http.server 8765 --bind 127.0.0.1
)

timeout /t 1 /nobreak >nul
start "" "http://127.0.0.1:8765/mini.html?v=5"
