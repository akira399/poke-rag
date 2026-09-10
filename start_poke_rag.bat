@echo off
cd /d %~dp0
echo ==================================================
echo    Poke-RAG  -  Pokemon Battle Knowledge Base
echo ==================================================
echo.
echo [1/2] Checking backend (port 8765) ...
curl -s --max-time 3 http://127.0.0.1:8765/api/health >nul 2>&1
if not errorlevel 1 (
    echo       Backend is already running. Skipped.
    goto ui
)
echo       Starting backend in a new window ...
start "Poke-RAG Backend" cmd /k "set EMBED_DISABLED=1&& .venv\Scripts\python.exe scripts\serve.py"
echo       Waiting for backend (8s) ...
timeout /t 8 /nobreak >nul

:ui
echo [2/2] Checking web UI (port 8501) ...
curl -s --max-time 3 http://localhost:8501/_stcore/health >nul 2>&1
if not errorlevel 1 (
    echo       UI is already running. Opening browser ...
    goto open
)
echo       Starting web UI in a new window ...
start "Poke-RAG UI" cmd /k ".venv\Scripts\python.exe -m streamlit run scripts\serve_ui.py --server.port 8501"
echo       Waiting for UI (10s) ...
timeout /t 10 /nobreak >nul

:open
start "" http://localhost:8501
echo.
echo Done.  Browser should open: http://localhost:8501
echo To stop: close the two new windows (Backend / UI).
pause
