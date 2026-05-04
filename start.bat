@echo off
cd /d "%~dp0"
echo.
echo === URL Style Extractor ===
echo.

py -c "import streamlit" 2>nul
if errorlevel 1 (
    echo Eerste keer opstarten - dependencies installeren...
    echo.
    py -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Pip install mislukt. Is Python geinstalleerd? https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

py -c "from playwright.sync_api import sync_playwright; sync_playwright().start().chromium.launch().close()" 2>nul
if errorlevel 1 (
    echo Chromium voor Playwright installeren...
    py -m playwright install chromium
)

echo.
echo Streamlit starten - de browser opent automatisch...
echo Druk Ctrl+C om te stoppen.
echo.
py -m streamlit run app.py
