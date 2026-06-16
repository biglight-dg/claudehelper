@echo off
cd /d "%~dp0"
start /b "" "C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false --server.headless true
timeout /t 4 /nobreak > nul
start "" "http://localhost:8501"
