from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn
from fastapi import FastAPI

# Create your FastMCP server
mcp = FastMCP("MyServer")

@mcp.tool()
def hello(name: str) -> str:
    return f"Hello, {name}!"

# Define custom middleware
custom_middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"]),
]

# Create ASGI app with custom middleware
sse_app = mcp.http_app(middleware=custom_middleware, transport="sse", path="/sse")


# Get a Starlette app instance for Streamable HTTP transport (recommended)
#http_app = mcp.http_app(middleware=custom_middleware, transport="http")

# Create a FastAPI app and mount the MCP server
#app = FastAPI(lifespan=sse_app.router.lifespan_context)
#app.mount("/mcp", sse_app)


if __name__ == "__main__":
    # To use a different transport, e.g., SSE:
    # mcp.run(transport="sse", host="localhost", port=8000)

    uvicorn.run(sse_app, host="localhost", port=8000)