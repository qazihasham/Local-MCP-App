# mcp_bridge.py - Windows-compatible version
import asyncio
import subprocess
import json
import logging
import os
import sys
import threading
import queue
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class MCPServerProcess:
    name: str
    process: subprocess.Popen
    tools: List[Dict[str, Any]]
    initialized: bool = False
    stdin_queue: queue.Queue = None
    stdout_queue: queue.Queue = None
    stderr_queue: queue.Queue = None

class MCPBridge:
    """Windows-compatible bridge between stdio MCP servers and SSE-compatible interface"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServerProcess] = {}
        self.request_id_counter = 0
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.status_callback: Optional[Callable] = None
        
    async def initialize(self):
        """Initialize the bridge system"""
        logger.info("MCP Bridge initialized")
        
    def set_status_callback(self, callback: Callable):
        """Set callback for status updates"""
        self.status_callback = callback
        
    def _notify_status(self, server_name: str, status: str, **kwargs):
        """Notify status change"""
        if self.status_callback:
            self.status_callback(server_name, status, **kwargs)
    
    def _find_executable(self, command: str) -> str:
        """Find the full path to an executable"""
        if os.path.isabs(command) and os.path.exists(command):
            return command
            
        found = shutil.which(command)
        if found:
            return found
            
        if sys.platform == "win32":
            for ext in ['.cmd', '.exe', '.bat']:
                cmd_with_ext = command + ext
                found = shutil.which(cmd_with_ext)
                if found:
                    return found
                    
        return command

    def _stdin_writer_thread(self, process, stdin_queue):
        """Thread to handle stdin writing"""
        try:
            while True:
                try:
                    data = stdin_queue.get(timeout=1.0)
                    if data is None:  # Shutdown signal
                        break
                    process.stdin.write(data)
                    process.stdin.flush()
                    stdin_queue.task_done()
                except queue.Empty:
                    if process.poll() is not None:
                        break
                except Exception as e:
                    logger.error(f"Stdin writer error: {e}")
                    break
        except Exception as e:
            logger.error(f"Stdin thread error: {e}")

    def _stdout_reader_thread(self, process, stdout_queue):
        """Thread to handle stdout reading"""
        try:
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                stdout_queue.put(line.strip())
        except Exception as e:
            logger.error(f"Stdout reader error: {e}")

    def _stderr_reader_thread(self, process, stderr_queue):
        """Thread to handle stderr reading"""
        try:
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                stderr_queue.put(line.strip())
        except Exception as e:
            logger.error(f"Stderr reader error: {e}")
    
    async def start_server(self, server_name: str, config):
        """Start an MCP server process with Windows-compatible threading"""
        if server_name in self.servers:
            logger.warning(f"Server {server_name} already running")
            return
            
        try:
            command = self._find_executable(config.command)
            logger.info(f"Using command: {command}")
            
            # Prepare environment
            env = os.environ.copy()
            if config.env:
                env.update(config.env)
            
            # Windows PATH handling
            if sys.platform == "win32":
                node_paths = [
                    r"C:\Program Files\nodejs",
                    r"C:\Program Files (x86)\nodejs",
                    os.path.expanduser(r"~\AppData\Roaming\npm"),
                ]
                current_path = env.get('PATH', '')
                for node_path in node_paths:
                    if os.path.exists(node_path) and node_path not in current_path:
                        env['PATH'] = f"{node_path};{current_path}"
            
            cmd_args = [command] + config.args
            logger.info(f"Starting process: {' '.join(cmd_args)}")
            
            # Start process with threading approach
            process = subprocess.Popen(
                cmd_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=config.cwd,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Wait to see if process starts
            await asyncio.sleep(0.5)
            
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                error_msg = f"Process failed to start. Return code: {process.returncode}\nStdout: {stdout}\nStderr: {stderr}"
                logger.error(error_msg)
                self._notify_status(server_name, "error", error=error_msg)
                return
            
            # Create queues for communication
            stdin_queue = queue.Queue()
            stdout_queue = queue.Queue()
            stderr_queue = queue.Queue()
            
            # Start communication threads
            stdin_thread = threading.Thread(
                target=self._stdin_writer_thread, 
                args=(process, stdin_queue),
                daemon=True
            )
            stdout_thread = threading.Thread(
                target=self._stdout_reader_thread, 
                args=(process, stdout_queue),
                daemon=True
            )
            stderr_thread = threading.Thread(
                target=self._stderr_reader_thread, 
                args=(process, stderr_queue),
                daemon=True
            )
            
            stdin_thread.start()
            stdout_thread.start()
            stderr_thread.start()
            
            server_process = MCPServerProcess(
                name=server_name,
                process=process,
                tools=[],
                stdin_queue=stdin_queue,
                stdout_queue=stdout_queue,
                stderr_queue=stderr_queue
            )
            
            self.servers[server_name] = server_process
            
            # Start background tasks
            asyncio.create_task(self._handle_server_output(server_name))
            asyncio.create_task(self._handle_server_errors(server_name))
            
            # Initialize MCP connection
            await self._initialize_mcp_server(server_name)
            
            self._notify_status(server_name, "running", pid=process.pid)
            logger.info(f"Started MCP server: {server_name}")
            
        except Exception as e:
            error_msg = f"Failed to start server {server_name}: {e}"
            logger.error(error_msg)
            self._notify_status(server_name, "error", error=error_msg)
            if server_name in self.servers:
                del self.servers[server_name]
            raise Exception(error_msg)
    
    async def _initialize_mcp_server(self, server_name: str):
        """Initialize MCP protocol with server"""
        server = self.servers[server_name]
        
        try:
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": self._get_request_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "0.1.0",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "MCP-Bridge", "version": "1.0.0"}
                }
            }
            
            response = await self._send_request(server_name, init_request)
            if response.get("error"):
                raise Exception(f"MCP initialization failed: {response['error']}")
            
            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            await self._send_notification(server_name, initialized_notification)
            
            # List available tools
            await self._list_tools(server_name)
            
            server.initialized = True
            logger.info(f"MCP server {server_name} initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize MCP server {server_name}: {e}"
            logger.error(error_msg)
            self._notify_status(server_name, "error", error=error_msg)
    
    async def _list_tools(self, server_name: str):
        """List tools available from MCP server"""
        try:
            list_tools_request = {
                "jsonrpc": "2.0",
                "id": self._get_request_id(),
                "method": "tools/list"
            }
            
            response = await self._send_request(server_name, list_tools_request)
            if response.get("result") and "tools" in response["result"]:
                self.servers[server_name].tools = response["result"]["tools"]
                self._notify_status(
                    server_name, 
                    "running", 
                    tools=response["result"]["tools"]
                )
                logger.info(f"Found {len(response['result']['tools'])} tools for {server_name}")
            else:
                logger.warning(f"No tools found for {server_name}")
                
        except Exception as e:
            logger.error(f"Failed to list tools for {server_name}: {e}")
    
    async def _send_request(self, server_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and wait for response"""
        if server_name not in self.servers:
            raise Exception(f"Server {server_name} not found")
        
        server = self.servers[server_name]
        request_id = str(request["id"])
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            # Send request via queue
            request_json = json.dumps(request) + "\n"
            server.stdin_queue.put(request_json)
            
            # Wait for response
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
            
        except asyncio.TimeoutError:
            raise Exception(f"Request timeout for {server_name}")
        except Exception as e:
            raise Exception(f"Failed to send request to {server_name}: {e}")
        finally:
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
    
    async def _send_notification(self, server_name: str, notification: Dict[str, Any]):
        """Send a JSON-RPC notification"""
        if server_name not in self.servers:
            raise Exception(f"Server {server_name} not found")
        
        server = self.servers[server_name]
        try:
            notification_json = json.dumps(notification) + "\n"
            server.stdin_queue.put(notification_json)
        except Exception as e:
            logger.error(f"Failed to send notification to {server_name}: {e}")
    
    async def _handle_server_output(self, server_name: str):
        """Handle stdout from MCP server"""
        server = self.servers[server_name]
        
        try:
            while True:
                try:
                    # Check for stdout messages
                    line = server.stdout_queue.get_nowait()
                    if line:
                        try:
                            message = json.loads(line)
                            await self._handle_server_message(server_name, message)
                        except json.JSONDecodeError:
                            logger.debug(f"Non-JSON output from {server_name}: {line}")
                except queue.Empty:
                    # No messages, check if process is still running
                    if server.process.poll() is not None:
                        break
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error handling output from {server_name}: {e}")
            self._notify_status(server_name, "error", error=str(e))
    
    async def _handle_server_errors(self, server_name: str):
        """Handle stderr from MCP server"""
        server = self.servers[server_name]
        
        try:
            while True:
                try:
                    line = server.stderr_queue.get_nowait()
                    if line:
                        logger.warning(f"MCP server {server_name} stderr: {line}")
                except queue.Empty:
                    if server.process.poll() is not None:
                        break
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error handling stderr from {server_name}: {e}")
    
    async def _handle_server_message(self, server_name: str, message: Dict[str, Any]):
        """Handle a message from MCP server"""
        if "id" in message and str(message["id"]) in self.pending_requests:
            request_id = str(message["id"])
            future = self.pending_requests[request_id]
            if not future.done():
                future.set_result(message)
        else:
            logger.debug(f"Received message from {server_name}: {message}")
    
    def _get_request_id(self) -> int:
        """Get next request ID"""
        self.request_id_counter += 1
        return self.request_id_counter
    
    async def stop_server(self, server_name: str):
        """Stop an MCP server"""
        if server_name not in self.servers:
            return
        
        server = self.servers[server_name]
        
        try:
            # Signal shutdown to stdin thread
            server.stdin_queue.put(None)
            
            # Terminate process
            server.process.terminate()
            
            # Wait for termination
            try:
                await asyncio.wait_for(
                    self._wait_for_process(server.process), 
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                server.process.kill()
                await self._wait_for_process(server.process)
            
        except Exception as e:
            logger.error(f"Error stopping server {server_name}: {e}")
        finally:
            del self.servers[server_name]
            self._notify_status(server_name, "stopped")
        
        logger.info(f"Stopped MCP server: {server_name}")
    
    async def _wait_for_process(self, process):
        """Wait for process to terminate"""
        while process.poll() is None:
            await asyncio.sleep(0.1)
    
    async def get_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Get tools from a specific server"""
        if server_name not in self.servers:
            return []
        return self.servers[server_name].tools
    
    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all tools from all running servers"""
        all_tools = []
        for server_name, server in self.servers.items():
            if server.initialized:
                for tool in server.tools:
                    tool_with_server = tool.copy()
                    tool_with_server["server"] = server_name
                    all_tools.append(tool_with_server)
        return all_tools
    
    async def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on a specific server"""
        if server_name not in self.servers:
            raise Exception(f"Server {server_name} not found")
        
        server = self.servers[server_name]
        if not server.initialized:
            raise Exception(f"Server {server_name} not initialized")
        
        tool_exists = any(tool["name"] == tool_name for tool in server.tools)
        if not tool_exists:
            raise Exception(f"Tool {tool_name} not found on server {server_name}")
        
        execute_request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }
        
        response = await self._send_request(server_name, execute_request)
        
        if response.get("error"):
            raise Exception(f"Tool execution failed: {response['error']}")
        
        return response.get("result")
    
    async def cleanup(self):
        """Cleanup all servers on shutdown"""
        for server_name in list(self.servers.keys()):
            await self.stop_server(server_name)