from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import Response

def create_sse_server(mcp: FastMCP):
    """Create a Starlette app that handles SSE connections and message handling"""
    transport = SseServerTransport("/messages/")

    # Define handler functions
    async def handle_sse(request):
        try:
            async with transport.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await mcp._mcp_server.run(
                    streams[0], streams[1], mcp._mcp_server.create_initialization_options()
                )
        except Exception as e:
            print(f"SSE Error: {e}")
            return Response("SSE connection error", status_code=500)
        
        return Response("SSE connection closed", status_code=200)

    # Define messages handler
    async def handle_messages(request):
        """Handle POST messages to the MCP server"""
        try:
            return await transport.handle_post_message(request)
        except Exception as e:
            print(f"Message handling error: {e}")
            return Response("Message handling error", status_code=500)

    # Create Starlette routes for SSE and message handling
    routes = [
        Route("/sse/", endpoint=handle_sse),
        Mount("/messages/", app=transport.handle_post_message),
    ]

    # Create a Starlette app
    return Starlette(routes=routes)