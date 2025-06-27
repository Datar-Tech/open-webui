from typing import List, Dict, Any, Callable, AsyncIterator
from fastapi import Request, HTTPException
from open_webui.models.users import UserModel
from open_webui.utils.log import log
import httpx
import json

# Assuming llama_index is installed in the agent's environment
try:
    from llama_index.core.tools import FunctionTool, BaseTool
    from llama_index.core.llms import ChatMessage, MessageRole, LLM
    from llama_index.core.response import Response as LlamaIndexResponse
except ImportError:
    log.warning("LlamaIndex not found. OpenWebUIToolAdapter will not be able to create LlamaIndex tools.")
    FunctionTool = None
    BaseTool = None
    LlamaIndexResponse = None

# Import the new execute_tool_by_id function
from open_webui.utils.tools import execute_tool_by_id

class OpenWebUIToolAdapter:
    def __init__(self, request: Request, user: UserModel):
        self.request = request
        self.user = user
        self.tools_cache: Dict[str, Any] = {}

    async def _fetch_openwebui_tools(self) -> List[Dict[str, Any]]:
        """Fetches tools from Open WebUI's backend API using an internal HTTP call."""
        # Construct the URL for the internal tools API endpoint
        # Assuming the API is running on the same host/port as the current request
        base_url = str(self.request.base_url).rstrip('/')
        tools_api_url = f"{base_url}/api/v1/tools/"

        headers = {
            "Authorization": f"Bearer {self.request.state.token.credentials}" # Use the current user's token
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(tools_api_url, headers=headers)
                response.raise_for_status() # Raise an exception for 4xx/5xx responses
                tools_data = response.json()
                log.info(f"Successfully fetched {len(tools_data)} tools from Open WebUI API.")
                return tools_data
            except httpx.HTTPStatusError as e:
                log.error(f"HTTP error fetching tools from {tools_api_url}: {e.response.status_code} - {e.response.text}")
                return []
            except httpx.RequestError as e:
                log.error(f"Network error fetching tools from {tools_api_url}: {e}")
                return []

    async def _execute_openwebui_tool_proxy(self, tool_id: str, tool_name: str, **kwargs) -> Any:
        """Proxy function to execute an Open WebUI tool via execute_tool_by_id."""
        log.info(f"Proxying execution for Open WebUI tool: {tool_name} (ID: {tool_id}) with args: {kwargs}")
        try:
            result = await execute_tool_by_id(self.request, tool_id, tool_name, **kwargs)
            log.info(f"Tool {tool_name} execution proxied successfully. Result type: {type(result)}")
            
            # LlamaIndex tools expect a string output for observation
            # If the tool returns a complex object, convert it to string/JSON
            if isinstance(result, (dict, list)):
                return json.dumps(result, indent=2)
            return str(result)
        except HTTPException as e:
            log.error(f"HTTPException during tool proxy execution: {e.detail}")
            return f"Error executing tool {tool_name}: {e.detail}"
        except Exception as e:
            log.error(f"Unexpected error during tool proxy execution: {e}", exc_info=True)
            return f"Error executing tool {tool_name}: {str(e)}"

    async def get_llamaindex_tools(self) -> List[BaseTool]:
        """Converts Open WebUI tools into LlamaIndex FunctionTool objects."""
        if FunctionTool is None:
            log.error("LlamaIndex FunctionTool is not available. Cannot create LlamaIndex tools.")
            return []

        openwebui_tools = await self._fetch_openwebui_tools()
        llamaindex_tools: List[BaseTool] = []

        for tool_data in openwebui_tools:
            tool_id = tool_data.get("id")
            tool_name = tool_data.get("name")
            tool_description = tool_data.get("meta", {}).get("description", "No description provided.")
            tool_specs = tool_data.get("specs", [])

            if not tool_specs:
                log.warning(f"Tool {tool_name} (ID: {tool_id}) has no specs. Skipping.")
                continue

            # Assuming the first spec is the primary one for simplicity
            # In a real scenario, you might iterate through all specs or choose based on type
            primary_spec = tool_specs[0]
            
            # Create a partial function that includes tool_id and tool_name
            # This allows the proxy to know which specific tool to execute
            proxy_callable = lambda **kwargs: self._execute_openwebui_tool_proxy(tool_id, tool_name, **kwargs)

            # LlamaIndex FunctionTool can take a pydantic BaseModel as fn_schema
            # We need to convert OpenAPI spec to Pydantic BaseModel dynamically.
            # This is a complex task and might require a separate utility.
            # For now, we'll omit fn_schema and rely on description.
            
            # A proper implementation would involve: 
            # from open_webui.utils.tools import convert_openapi_to_pydantic_model
            # tool_schema = convert_openapi_to_pydantic_model(primary_spec)

            llamaindex_tool = FunctionTool.from_defaults(
                fn=proxy_callable,
                name=tool_name,
                description=tool_description,
                # fn_schema=tool_schema # Add this once dynamic schema conversion is ready
            )
            llamaindex_tools.append(llamaindex_tool)

        return llamaindex_tools