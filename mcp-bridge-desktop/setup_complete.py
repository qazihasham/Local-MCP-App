#!/usr/bin/env python3
"""
Complete setup script for MCP Bridge Desktop Application
This creates all necessary files and sets up the entire project structure
"""

import os
import json
import subprocess
import sys
from pathlib import Path

def create_file(filepath, content):
    """Create a file with the given content"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Created {filepath}")

def create_binary_placeholder(filepath, description):
    """Create a placeholder for binary files"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(f"# Placeholder for {description}\n# This file should be replaced with the actual binary\n")
    print(f"📄 Created placeholder: {filepath}")

def main():
    print("🚀 Setting up MCP Bridge Desktop Application...")
    
    # Create project directory
    project_dir = "mcp-bridge-desktop"
    os.makedirs(project_dir, exist_ok=True)
    os.chdir(project_dir)
    
    # Create directory structure
    directories = [
        "electron", "build", "templates", "python-dist", 
        "electron/assets", "src", "scripts"
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    print("📁 Created directory structure")
    
    # Create package.json (already provided in artifacts)
    package_json = {
        "name": "mcp-bridge-desktop",
        "version": "1.0.0",
        "description": "Desktop application for managing MCP servers",
        "main": "electron/main.js",
        "scripts": {
            "start": "electron .",
            "dev": "concurrently \"python main.py\" \"wait-on http://127.0.0.1:8765 && electron .\"",
            "build": "electron-builder",
            "build-all": "electron-builder -mwl",
            "build-mac": "electron-builder --mac",
            "build-win": "electron-builder --win",
            "build-linux": "electron-builder --linux",
            "pack": "electron-builder --dir",
            "dist": "npm run build",
            "postinstall": "electron-builder install-app-deps"
        },
        "build": {
            "appId": "com.mcpbridge.desktop",
            "productName": "MCP Bridge Desktop",
            "directories": {"output": "dist", "buildResources": "build"},
            "files": ["electron/**/*", "templates/**/*", "*.py", "requirements.txt", "package.json"],
            "extraResources": [{"from": "python-dist", "to": "python", "filter": ["**/*"]}],
            "mac": {
                "category": "public.app-category.developer-tools",
                "icon": "build/icon.icns",
                "target": [{"target": "dmg", "arch": ["x64", "arm64"]}]
            },
            "win": {
                "icon": "build/icon.ico",
                "target": [{"target": "nsis", "arch": ["x64"]}]
            },
            "linux": {
                "icon": "build/icon.png",
                "category": "Development",
                "target": [{"target": "AppImage", "arch": ["x64"]}]
            }
        },
        "devDependencies": {
            "electron": "^22.3.27",
            "electron-builder": "^24.6.4",
            "concurrently": "^8.2.0",
            "wait-on": "^7.0.1"
        },
        "dependencies": {"electron-updater": "^6.1.4"}
    }
    
    create_file("package.json", json.dumps(package_json, indent=2))
    
    # Create Python requirements
    requirements = """fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
starlette==0.27.0
mcp==1.0.0
aiofiles==23.2.1
python-multipart==0.0.6
pyinstaller==5.13.2"""
    
    create_file("requirements.txt", requirements)
    
    # Create .gitignore
    gitignore = """# Dependencies
node_modules/
venv/
env/
*.egg-info/

# Build outputs
dist/
build/
python-dist/
*.exe
*.dmg
*.deb
*.AppImage

# Logs
*.log
logs/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp

# Python
__pycache__/
*.pyc
*.pyo

# Electron
out/"""
    
    create_file(".gitignore", gitignore)
    
    # Create build scripts
    build_script_win = """@echo off
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
call venv\\Scripts\\activate.bat
pip install -r requirements.txt
pip install pyinstaller

echo Bundling Python backend...
pyinstaller main.py --onedir --name mcp-bridge-backend --distpath python-dist

echo Building Electron application...
call npm run build-win

echo Build complete! Check the dist/ directory.
pause"""
    
    create_file("scripts/build-win.bat", build_script_win)
    
    build_script_unix = """#!/bin/bash
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
"""
    
    create_file("scripts/build.sh", build_script_unix)
    os.chmod("scripts/build.sh", 0o755)
    
    # Create development script
    dev_script = """#!/bin/bash
# Development script

echo "🚀 Starting MCP Bridge Desktop in development mode..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install

# Start in development mode
npm run dev
"""
    
    create_file("scripts/dev.sh", dev_script)
    os.chmod("scripts/dev.sh", 0o755)
    
    # Create icon placeholders
    create_binary_placeholder("build/icon.icns", "macOS app icon (1024x1024 .icns)")
    create_binary_placeholder("build/icon.ico", "Windows app icon (256x256 .ico)")
    create_binary_placeholder("build/icon.png", "Linux app icon (512x512 .png)")
    create_binary_placeholder("electron/assets/icon.png", "Application icon (256x256 .png)")
    
    # Create README
    readme = """# MCP Bridge Desktop

A powerful desktop application for managing MCP (Model Context Protocol) servers with a beautiful UI and seamless integration.

## Features

- 🖥️ **Native Desktop App**: Built with Electron for cross-platform compatibility
- 🔌 **Universal MCP Bridge**: Connect any stdio-based MCP server to SSE
- 🎨 **Beautiful UI**: Modern, responsive interface inspired by VS Code and Claude Desktop
- 📋 **JSON Import**: Paste MCP configurations directly from Cursor/Claude Desktop
- ⚡ **Real-time Management**: Start, stop, and monitor MCP servers in real-time
- 🛠️ **Tool Discovery**: Automatically discover and display available tools
- 📱 **Responsive Design**: Works great on different screen sizes

## Quick Start

### For End Users
1. Download the installer for your platform from [Releases](releases)
2. Install and run the application
3. Add MCP servers using the "Add from JSON" button
4. Start servers and explore their tools

### For Developers
```bash
# Clone and setup
git clone <repo-url>
cd mcp-bridge-desktop

# Development mode
./scripts/dev.sh

# Build for distribution
./scripts/build.sh
```

## Screenshots

*Add screenshots here showing the application interface*

## Configuration

The app supports the same MCP server configurations as Cursor and Claude Desktop:

```json
{
  "mcpServers": {
    "pinecone": {
      "command": "npx",
      "args": ["-y", "@pinecone-database/mcp"],
      "env": {
        "PINECONE_API_KEY": "your-key"
      }
    }
  }
}
```

## Supported Platforms

- ✅ macOS (Intel & Apple Silicon)
- ✅ Windows (x64)
- ✅ Linux (x64)

## Architecture

- **Frontend**: React SPA with modern UI components
- **Backend**: Python FastAPI server with MCP bridge
- **Desktop**: Electron wrapper with native OS integration
- **Packaging**: Electron Builder with PyInstaller bundling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details
"""
    
    create_file("README.md", readme)
    
    # Create launch instructions
    instructions = """# MCP Bridge Desktop - Setup Instructions

## Prerequisites
- Node.js 16+ (https://nodejs.org/)
- Python 3.8+ (https://python.org/)
- Git (https://git-scm.com/)

## Files to Copy from Artifacts

You need to copy these files from the artifacts into your project:

1. **main.py** → root directory
2. **mcp_bridge.py** → root directory  
3. **sse_server.py** → root directory (updated SSE server)
4. **index.html** → templates/ directory (frontend UI)
5. **electron/main.js** → electron/ directory (already provided)

## Setup Steps

1. **Copy all artifacts** to the appropriate locations
2. **Install Node.js dependencies**:
   ```bash
   npm install
   ```

3. **Setup Python environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

4. **Run in development mode**:
   ```bash
   npm run dev
   ```

5. **Build for distribution**:
   ```bash
   ./scripts/build.sh  # Unix
   scripts\\build-win.bat  # Windows
   ```

## Directory Structure

```
mcp-bridge-desktop/
├── electron/
│   ├── main.js           # Electron main process
│   └── assets/           # App icons and assets
├── templates/
│   └── index.html        # Frontend UI
├── scripts/
│   ├── build.sh          # Unix build script
│   ├── build-win.bat     # Windows build script
│   └── dev.sh            # Development script
├── build/                # Electron builder assets
├── main.py               # Python backend
├── mcp_bridge.py         # MCP bridge core
├── sse_server.py         # SSE server
├── requirements.txt      # Python dependencies
├── package.json          # Node.js config
└── README.md             # Documentation
```

## Key Features Implemented

**Desktop Application**: Native Electron app
**JSON Configuration Parser**: Paste MCP configs directly
**Real-time Server Management**: Start/stop/edit servers
**Tool Discovery**: Automatic tool detection and display
**Modern UI**: React-based interface with smooth animations
**Cross-platform**: macOS, Windows, Linux support
**Packaging**: Complete build and distribution setup

## Next Steps

1. Copy the artifact files to their proper locations
2. Customize the app icons in build/ directory
3. Test the application thoroughly
4. Build and distribute to end users

The application will be a single executable that users can download and run without any technical setup!
"""
    
    create_file("SETUP.md", instructions)
    
    print("\n MCP Bridge Desktop setup complete!")
    print("\n Next steps:")
    print("1. Copy the artifact files (main.py, mcp_bridge.py, etc.) to their locations")
    print("2. Run: npm install")
    print("3. Run: ./scripts/dev.sh (for development)")
    print("4. Run: ./scripts/build.sh (to build distributable)")
    print("\n Project structure created in 'mcp-bridge-desktop/' directory")
    print("See SETUP.md for detailed instructions")

if __name__ == "__main__":
    main()