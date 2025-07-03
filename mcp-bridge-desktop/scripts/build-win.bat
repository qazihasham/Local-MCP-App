@echo off
echo Building MCP Bridge Desktop Application...

REM Check Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Node.js is not installed
    exit /b 1
)

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed
    exit /b 1
)

REM Install dependencies
echo Installing Node.js dependencies...
call npm install

echo Setting up Python environment...
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
pip install pyinstaller

echo Bundling Python backend...
pyinstaller main.py --onedir --name mcp-bridge-backend --distpath python-dist

echo Building Electron application...
call npm run build-win

echo Build complete! Check the dist/ directory.
pause