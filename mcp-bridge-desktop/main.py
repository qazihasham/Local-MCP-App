# main.py - Complete integrated MCP Bridge Desktop with SSE MCP Server
import asyncio
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from mcp_bridge import MCPBridge
from sse_server import create_sse_server
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mcp_bridge.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Data models
class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = {}
    cwd: Optional[str] = None

class ServerStatus(BaseModel):
    name: str
    status: str
    pid: Optional[int] = None
    tools: List[Dict[str, Any]] = []
    last_update: str
    error_message: Optional[str] = None

class AppSettings(BaseModel):
    host: str = "localhost"
    port: int = 30001
    sse_path: str = "/sse"
    auto_start: bool = False

class MCPServerJSON(BaseModel):
    json_content: str

# Get application directory
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys._MEIPASS)
    DATA_DIR = Path.home() / ".mcp-bridge"
else:
    APP_DIR = Path(__file__).parent
    DATA_DIR = APP_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "servers.json"

# Global instances
bridge = MCPBridge()
server_configs: Dict[str, MCPServerConfig] = {}
server_statuses: Dict[str, ServerStatus] = {}
app_settings = AppSettings()
sse_mcp_bridge = None
external_sse_server = None

# SSE MCP Bridge that exposes tools like your original setup
class SSEMCPBridge:
    """Bridge that exposes stdio MCP tools as SSE MCP server"""
    
    def __init__(self, name: str = "MCP-Bridge-Server"):
        self.mcp = FastMCP(name)
        self.registered_tools = {}
        self.app = None
        
    async def initialize(self, bridge_instance: MCPBridge):
        """Initialize with the main bridge instance"""
        self.bridge = bridge_instance
        self._setup_base_tools()
        logger.info("SSE MCP Bridge initialized")
        
    def _setup_base_tools(self):
        """Setup base tools that are always available"""
        
        @self.mcp.tool()
        async def list_available_tools() -> List[Dict[str, Any]]:
            """List all available tools from connected MCP servers"""
            try:
                return await self.bridge.get_all_tools()
            except Exception as e:
                logger.error(f"Error listing tools: {e}")
                return []
        
        @self.mcp.tool()
        async def execute_mcp_tool(server_name: str, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
            """Execute a tool from a connected MCP server
            
            Args:
                server_name: Name of the MCP server
                tool_name: Name of the tool to execute
                arguments: Arguments to pass to the tool
                
            Returns:
                Result from tool execution
            """
            if arguments is None:
                arguments = {}
            return await self.bridge.execute_tool(server_name, tool_name, arguments)
    
    async def update_tools(self):
        """Update available tools when servers change"""
        try:
            all_tools = await self.bridge.get_all_tools()
            
            # Register each tool individually (like your @mcp.tool() approach)
            for tool in all_tools:
                tool_id = f"{tool['server']}_{tool['name']}"
                
                if tool_id not in self.registered_tools:
                    await self._register_individual_tool(tool)
                    self.registered_tools[tool_id] = tool
                    
            logger.info(f"Updated SSE MCP tools: {len(self.registered_tools)} total tools available")
                    
        except Exception as e:
            logger.error(f"Failed to update tools: {e}")
    
    async def _register_individual_tool(self, tool: Dict[str, Any]):
        """Register an individual tool as a FastMCP tool"""
        # Skip individual tool registration for now - use the base tools instead
        # The base tools (list_available_tools, execute_mcp_tool) handle everything
        server_name = tool['server']
        tool_name = tool['name']
        tool_id = f"{server_name}_{tool_name}"
        
        logger.info(f"Tool available: {tool_id}")
        # Individual tool registration disabled - using base tools instead
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI app with SSE server"""
        if self.app is None:
            self.app = FastAPI(title="MCP Bridge SSE Server")
            
            # Add CORS middleware
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            
            # Create the SSE server using your original working sse_server.py
            sse_server_app = create_sse_server(self.mcp)
            
            # Mount the entire SSE server at root - this preserves your original routes
            self.app.mount("/", sse_server_app)
            
        return self.app

# Load configuration
def load_config():
    global server_configs, app_settings
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if 'servers' in data:
                for server_data in data['servers']:
                    config = MCPServerConfig(**server_data)
                    server_configs[config.name] = config
                    server_statuses[config.name] = ServerStatus(
                        name=config.name,
                        status="stopped",
                        last_update=time.strftime("%Y-%m-%d %H:%M:%S")
                    )
            
            if 'settings' in data:
                app_settings = AppSettings(**data['settings'])
                
        logger.info(f"Loaded {len(server_configs)} server configurations")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")

def save_config():
    try:
        data = {
            'servers': [config.model_dump() for config in server_configs.values()],
            'settings': app_settings.model_dump()
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logger.info("Configuration saved")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")

# External SSE MCP server management
async def start_external_sse_server():
    """Start external SSE MCP server on configured port"""
    global external_sse_server, sse_mcp_bridge
    
    if external_sse_server is not None:
        await stop_external_sse_server()
    
    try:
        # Create SSE MCP Bridge
        sse_mcp_bridge = SSEMCPBridge("MCP-Bridge-Server")
        await sse_mcp_bridge.initialize(bridge)
        
        # Update tools from current servers
        await sse_mcp_bridge.update_tools()
        
        # Get the FastAPI app
        sse_app = sse_mcp_bridge.get_app()
        
        # Create server config
        config = uvicorn.Config(
            sse_app,
            host=app_settings.host,
            port=app_settings.port,
            log_level="info",
            access_log=False
        )
        
        external_sse_server = uvicorn.Server(config)
        
        # Start in background thread
        def run_external_server():
            asyncio.set_event_loop(asyncio.new_event_loop())
            loop = asyncio.get_event_loop()
            loop.run_until_complete(external_sse_server.serve())
        
        external_thread = threading.Thread(target=run_external_server, daemon=True)
        external_thread.start()
        
        # Wait a moment for server to start
        await asyncio.sleep(1)
        
        logger.info(f"SSE MCP Server started on {app_settings.host}:{app_settings.port}")
        logger.info(f"Your application can connect to: http://{app_settings.host}:{app_settings.port}{app_settings.sse_path}")
        
    except Exception as e:
        logger.error(f"Failed to start external SSE server: {e}")

async def stop_external_sse_server():
    """Stop external SSE server"""
    global external_sse_server
    
    if external_sse_server is not None:
        try:
            external_sse_server.should_exit = True
            await asyncio.sleep(0.5)
            external_sse_server = None
            logger.info("External SSE server stopped")
        except Exception as e:
            logger.error(f"Error stopping external SSE server: {e}")

# Update tools when servers change
async def update_sse_tools():
    """Update SSE MCP tools when servers change"""
    if sse_mcp_bridge:
        try:
            await sse_mcp_bridge.update_tools()
            logger.info("SSE MCP tools updated")
        except Exception as e:
            logger.error(f"Failed to update SSE tools: {e}")

# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting MCP Bridge Desktop Application...")
    load_config()
    await bridge.initialize()
    bridge.set_status_callback(update_server_status)
    
    # Start external SSE MCP server
    await start_external_sse_server()
    
    if app_settings.auto_start:
        for server_name in server_configs:
            try:
                logger.info(f"Auto-starting server: {server_name}")
                await bridge.start_server(server_name, server_configs[server_name])
                # Wait for tools discovery
                await asyncio.sleep(3)
                await update_sse_tools()
            except Exception as e:
                logger.error(f"Failed to auto-start {server_name}: {e}")
    
    logger.info("MCP Bridge Desktop Application started successfully")
    yield
    
    # Shutdown
    logger.info("Shutting down MCP Bridge Desktop Application...")
    await stop_external_sse_server()
    await bridge.cleanup()
    save_config()
    logger.info("Shutdown complete")

# Create main FastAPI app
app = FastAPI(title="MCP Bridge Desktop", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the main UI
@app.get("/", response_class=HTMLResponse)
async def get_ui():
    try:
        html_file = APP_DIR / "templates" / "index.html"
        if html_file.exists():
            with open(html_file, 'r', encoding='utf-8') as f:
                return HTMLResponse(f.read())
        else:
            return HTMLResponse("""
            <h1>MCP Bridge Desktop</h1>
            <p>UI file not found. Please copy index.html to templates/</p>
            <p>Management functionality is available via API endpoints.</p>
            <h2>Current Status:</h2>
            <p>SSE MCP Server running on port """ + str(app_settings.port) + """</p>
            """)
    except Exception as e:
        return HTMLResponse(f"<h1>Error</h1><p>Failed to load UI: {e}</p>")

# API Routes
@app.get("/api/settings")
async def get_settings():
    return app_settings.model_dump()

@app.post("/api/settings")
async def update_settings(settings: AppSettings):
    global app_settings
    old_settings = app_settings.model_dump()
    app_settings = settings
    save_config()
    
    # Restart external SSE server if settings changed
    if (old_settings['host'] != settings.host or 
        old_settings['port'] != settings.port or 
        old_settings['sse_path'] != settings.sse_path):
        
        logger.info("Settings changed, restarting SSE server...")
        await start_external_sse_server()
        logger.info("External SSE server restarted with new settings")
    
    return {"message": "Settings updated"}

@app.get("/api/servers")
async def get_servers():
    return {
        "servers": [
            {
                "config": config.model_dump(),
                "status": server_statuses.get(name, ServerStatus(
                    name=name,
                    status="stopped",
                    last_update=time.strftime("%Y-%m-%d %H:%M:%S")
                )).model_dump()
            }
            for name, config in server_configs.items()
        ]
    }

@app.post("/api/servers/parse")
async def parse_mcp_json(data: MCPServerJSON):
    try:
        # Parse the JSON
        json_data = json.loads(data.json_content)
        
        # Handle different formats
        servers_data = None
        
        # Check for Cursor/Claude Desktop format
        if "mcpServers" in json_data:
            servers_data = json_data["mcpServers"]
        # Check for VS Code MCP format
        elif "mcp" in json_data and "servers" in json_data["mcp"]:
            servers_data = json_data["mcp"]["servers"]
        # Direct server configuration
        else:
            servers_data = json_data
        
        if not servers_data:
            raise Exception("No server configurations found in JSON")
        
        parsed_servers = []
        for name, config in servers_data.items():
            # Handle VS Code input variables (replace with placeholder)
            env = config.get("env", {})
            for key, value in env.items():
                if isinstance(value, str) and value.startswith("${input:"):
                    env[key] = f"<REPLACE_WITH_YOUR_{key}>"
            
            server_config = {
                "name": name,
                "command": config.get("command", ""),
                "args": config.get("args", []),
                "env": env,
                "cwd": config.get("cwd")
            }
            parsed_servers.append(server_config)
        
        return {"servers": parsed_servers, "message": f"Parsed {len(parsed_servers)} server(s)"}
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        logger.error(f"Parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse: {str(e)}")

@app.post("/api/servers")
async def add_server(config: MCPServerConfig):
    if config.name in server_configs:
        raise HTTPException(status_code=400, detail="Server name already exists")
    
    server_configs[config.name] = config
    server_statuses[config.name] = ServerStatus(
        name=config.name,
        status="stopped",
        last_update=time.strftime("%Y-%m-%d %H:%M:%S")
    )
    save_config()
    return {"message": "Server added successfully"}

@app.put("/api/servers/{server_name}")
async def update_server(server_name: str, config: MCPServerConfig):
    if server_name not in server_configs:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if config.name != server_name and server_statuses[server_name].status == "running":
        await bridge.stop_server(server_name)
        await update_sse_tools()
    
    if config.name != server_name:
        del server_configs[server_name]
        del server_statuses[server_name]
    
    server_configs[config.name] = config
    server_statuses[config.name] = ServerStatus(
        name=config.name,
        status="stopped",
        last_update=time.strftime("%Y-%m-%d %H:%M:%S")
    )
    save_config()
    return {"message": "Server updated successfully"}

@app.post("/api/servers/{server_name}/start")
async def start_server(server_name: str, background_tasks: BackgroundTasks):
    if server_name not in server_configs:
        raise HTTPException(status_code=404, detail="Server not found")
    
    config = server_configs[server_name]
    
    async def start_and_update():
        try:
            logger.info(f"Starting server: {server_name}")
            await bridge.start_server(server_name, config)
            # Wait for tools to be discovered
            await asyncio.sleep(3)
            # Update SSE tools
            await update_sse_tools()
            logger.info(f"Server {server_name} started and tools updated")
        except Exception as e:
            logger.error(f"Failed to start server {server_name}: {e}")
    
    background_tasks.add_task(start_and_update)
    return {"message": f"Starting server {server_name}"}

@app.post("/api/servers/{server_name}/stop")
async def stop_server(server_name: str):
    if server_name not in server_configs:
        raise HTTPException(status_code=404, detail="Server not found")
    
    logger.info(f"Stopping server: {server_name}")
    await bridge.stop_server(server_name)
    server_statuses[server_name].status = "stopped"
    server_statuses[server_name].pid = None
    server_statuses[server_name].last_update = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Update SSE tools
    await update_sse_tools()
    
    return {"message": f"Server {server_name} stopped"}

@app.delete("/api/servers/{server_name}")
async def delete_server(server_name: str):
    if server_name not in server_configs:
        raise HTTPException(status_code=404, detail="Server not found")
    
    logger.info(f"Deleting server: {server_name}")
    await bridge.stop_server(server_name)
    del server_configs[server_name]
    if server_name in server_statuses:
        del server_statuses[server_name]
    
    save_config()
    
    # Update SSE tools
    await update_sse_tools()
    
    return {"message": f"Server {server_name} deleted"}

@app.get("/api/tools")
async def get_all_tools():
    try:
        all_tools = await bridge.get_all_tools()
        return {"tools": all_tools}
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        return {"tools": []}

@app.post("/api/tools/execute")
async def execute_tool(tool_data: Dict[str, Any]):
    tool_name = tool_data.get("name")
    server_name = tool_data.get("server")
    arguments = tool_data.get("arguments", {})
    
    if not tool_name or not server_name:
        raise HTTPException(status_code=400, detail="Tool name and server name required")
    
    try:
        result = await bridge.execute_tool(server_name, tool_name, arguments)
        return {"result": result}
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status():
    """Get overall system status"""
    running_servers = [name for name, status in server_statuses.items() if status.status == "running"]
    total_tools = len(await bridge.get_all_tools()) if bridge else 0
    
    return {
        "management_server": "running",
        "sse_server": "running" if external_sse_server else "stopped",
        "sse_endpoint": f"http://{app_settings.host}:{app_settings.port}{app_settings.sse_path}",
        "running_servers": running_servers,
        "total_servers": len(server_configs),
        "total_tools": total_tools,
        "settings": app_settings.model_dump()
    }

# Status update callback
def update_server_status(server_name: str, status: str, pid: Optional[int] = None, 
                        tools: List[Dict[str, Any]] = None, error: Optional[str] = None):
    if server_name in server_statuses:
        server_statuses[server_name].status = status
        server_statuses[server_name].pid = pid
        server_statuses[server_name].tools = tools or []
        server_statuses[server_name].last_update = time.strftime("%Y-%m-%d %H:%M:%S")
        server_statuses[server_name].error_message = error
        
        # Update SSE tools when status changes
        if status == "running" and tools:
            asyncio.create_task(update_sse_tools())
            logger.info(f"Server {server_name} is running with {len(tools)} tools")

def run_server():
    """Run the main FastAPI server"""
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8765,
            log_level="info",
            access_log=False
        )
    except Exception as e:
        logger.error(f"Server error: {e}")

def main():
    """Main entry point for desktop application"""
    print("Starting MCP Bridge Desktop Application...")
    print(f"Management UI will be available at: http://127.0.0.1:8765")
    print(f"SSE MCP Server will be available at: http://{app_settings.host}:{app_settings.port}{app_settings.sse_path}")
    print("=" * 60)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(3)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--electron":
        # Running from Electron
        print("Running in Electron mode...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")
    else:
        # Running standalone
        import webbrowser
        webbrowser.open("http://127.0.0.1:8765")
        print("Opened management UI in browser")
        print("Add MCP servers through the web interface")
        print("Your application can connect to the SSE endpoint")
        print("\nPress Ctrl+C to stop...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")

if __name__ == "__main__":
    main()