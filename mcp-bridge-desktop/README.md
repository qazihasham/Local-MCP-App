# MCP Bridge Desktop

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
