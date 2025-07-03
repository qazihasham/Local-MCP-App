#!/bin/bash
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
