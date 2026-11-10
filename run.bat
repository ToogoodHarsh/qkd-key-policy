@echo off
cd /d "%~dp0"
echo Starting the QKD key-usage dashboard ...
echo Keep this window open while you use the dashboard. Close it to stop.
start "" /b python -m streamlit run app.py --server.headless true --server.port 8501 --server.address localhost
timeout /t 6 /nobreak >nul
start "" http://localhost:8501
pause >nul
