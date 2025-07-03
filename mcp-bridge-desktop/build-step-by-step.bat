@echo off
echo ============================================
echo MCP Bridge Desktop Build Script
echo ============================================

echo.
echo Step 1: Node.js dependencies (COMPLETED)
echo ✅ Node packages already installed

echo.
echo Step 2: Creating Python virtual environment...
if exist venv (
    echo Removing old virtual environment...
    rmdir /s /q venv
)
python -m venv venv
if %ERRORLEVEL% neq 0 (
    echo ❌ Failed to create virtual environment
    pause
    exit /b 1
)
echo ✅ Virtual environment created

echo.
echo Step 3: Installing Python packages...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
if %ERRORLEVEL% neq 0 (
    echo ❌ Failed to install Python packages
    pause
    exit /b 1
)
echo ✅ Python packages installed

echo.
echo Step 4: Building Python executable...
pyinstaller --onefile --name mcp-bridge-backend --distpath python-dist main.py
if %ERRORLEVEL% neq 0 (
    echo ❌ Failed to build Python executable
    pause
    exit /b 1
)
echo ✅ Python executable built

echo.
echo Step 5: Building Electron application...
call venv\Scripts\deactivate.bat
npm run build-win
if %ERRORLEVEL% neq 0 (
    echo ❌ Failed to build Electron app
    pause
    exit /b 1
)

echo.
echo ============================================
echo ✅ BUILD COMPLETED SUCCESSFULLY!
echo ============================================
echo.
echo Check the 'dist' folder for your installer:
dir dist\*.exe
echo.
pause