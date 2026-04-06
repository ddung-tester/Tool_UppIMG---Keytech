@echo off
echo =======================================================
echo Building FaceUploadTool Executable with Playwright
echo =======================================================
echo.

echo 1. Setting PLAYWRIGHT_BROWSERS_PATH=0 to force local browser installation
set PLAYWRIGHT_BROWSERS_PATH=0

echo 2. Installing/Updating dependencies...
pip install -r requirements.txt

echo 3. Downloading Chromium locally for PyInstaller to collect...
playwright install chromium

pyinstaller FaceUploadTool.spec --clean -y

echo.
echo =======================================================
echo Build complete! Check the "dist" folder for the executable.
echo =======================================================
pause
