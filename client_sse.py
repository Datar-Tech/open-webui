import asyncio
from fastmcp import Client
from fastmcp.client.transports import SSETransport

sse_url = "http://localhost:8000/sse"       # SSE server URL

# Since v2.3.0, HTTP URLs default to StreamableHttpTransport,
# so you must explicitly use SSETransport for SSE connections
transport_explicit = SSETransport(url=sse_url)
client_sse = Client(transport_explicit)

print(client_sse.transport)

async def main():
    # Connection is established here
    async with client_sse as client:
        print(f"Client connected: {client.is_connected()}")

        # Make MCP calls within the context
        tools = await client.list_tools()
        print(f"Available tools: {tools}")

        if any(tool.name == "greet" for tool in tools):
            result = await client.call_tool("greet", {"name": "World"})
            print(f"Greet result: {result}")

    # Connection is closed automatically here
    print(f"Client connected: {client.is_connected()}")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())



