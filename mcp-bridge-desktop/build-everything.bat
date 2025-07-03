@echo off
echo Starting MCP Bridge Desktop Build...

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed!
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python from https://python.org/
    pause
    exit /b 1
)

echo Step 1: Installing Node.js dependencies...
npm install
if errorlevel 1 (
    echo ERROR: Failed to install Node.js dependencies
    pause
    exit /b 1
)

echo Step 2: Creating Python virtual environment...
if exist venv rmdir /s /q venv
python -m venv venv
venv\Scripts\activate.bat && pip install --upgrade pip
venv\Scripts\activate.bat && pip install -r requirements.txt
venv\Scripts\activate.bat && pip install pyinstaller

echo Step 3: Building Python executable...
venv\Scripts\activate.bat && pyinstaller --onefile --name mcp-bridge-backend --distpath python-dist main.py

echo Step 4: Building Electron app...
npm run build-win

echo Build complete! Check the 'dist' folder for your installer.
pause