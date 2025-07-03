#!/bin/bash
# Build script for Unix-like systems (macOS, Linux)

set -e

echo "🚀 Building MCP Bridge Desktop Application..."

# Check dependencies
command -v node >/dev/null 2>&1 || { echo "Error: Node.js is not installed" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Error: Python 3 is not installed" >&2; exit 1; }

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Setup Python environment
echo "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

# Bundle Python backend
echo "📦 Bundling Python backend..."
pyinstaller main.py --onedir --name mcp-bridge-backend --distpath python-dist

# Build Electron app
echo "⚡ Building Electron application..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    npm run build-mac
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    npm run build-linux
else
    npm run build
fi

echo "✅ Build complete! Check the dist/ directory."
