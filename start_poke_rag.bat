@echo off
chcp 65001 >nul
cd /d %~dp0
echo ============================================
echo    Poke-RAG · 宝可梦对战知识库问答系统
echo ============================================
echo.
echo [1/2] 检查后端服务...
curl -s --max-time 3 http://127.0.0.1:8765/api/health >nul 2>&1
if not errorlevel 1 (
    echo   后端已在运行，跳过启动。
    goto :ui
)
echo   正在启动后端（新窗口）...
start "Poke-RAG 后端" cmd /k "set EMBED_DISABLED=1&& .venv\Scripts\python.exe scripts\serve.py"
echo   等待后端就绪（约 8 秒）...
timeout /t 8 >nul

:ui
echo [2/2] 正在启动界面（新窗口）...
start "Poke-RAG 界面" cmd /k ".venv\Scripts\python.exe -m streamlit run scripts\serve_ui.py --server.port 8501"
timeout /t 8 >nul
start http://localhost:8501
echo.
echo 完成！浏览器已自动打开 http://localhost:8501
echo 关闭方法：直接关掉两个命令行窗口即可。
pause
