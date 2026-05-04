@echo off
cd /d "%~dp0"
echo.
echo === URL Style Extractor ===
echo.

py -c "import streamlit" 2>nul
if errorlevel 1 (
    echo First-time setup - installing dependencies...
    echo.
    py -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Pip install failed. Is Python installed? https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

py -c "from playwright.sync_api import sync_playwright; sync_playwright().start().chromium.launch().close()" 2>nul
if errorlevel 1 (
    echo Installing Chromium for Playwright...
    py -m playwright install chromium
)

echo.
echo Starting Streamlit - the browser will open automatically...
echo Press Ctrl+C to stop.
echo.
py -m streamlit run app.py
