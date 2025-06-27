from typing import AsyncIterator, Dict, Any
from fastapi import Request
from open_webui.models.agents import Agent as AgentModel
from open_webui.utils.log import log
from open_webui.utils.openwebui_tool_adapter import OpenWebUIToolAdapter
from open_webui.utils.agent_tools import AgentTools
import inspect
import json
import asyncio

class AgentExecutor:
    def __init__(self, request: Request, agent_obj: AgentModel):
        self.request = request
        self.agent_obj = agent_obj
        self.openwebui_tool_adapter = OpenWebUIToolAdapter(request, request.state.user) # Assuming user is in request.state
        self.agent_tools = AgentTools(request)

    async def execute(self, user_message: str, chat_history: list) -> AsyncIterator[str]:
        log.info(f"Executing agent: {self.agent_obj.name} (Type: {self.agent_obj.agent_type})")

        try:
            yield json.dumps({"type": "status", "content": "Agent started..."}) + "\n"

            if self.agent_obj.agent_type == "custom_python":
                async for chunk in self._execute_custom_python_agent(user_message, chat_history):
                    yield chunk
            elif self.agent_obj.agent_type == "llamaindex_workflow":
                async for chunk in self._execute_llamaindex_workflow_agent(user_message, chat_history):
                    yield chunk
            else:
                yield json.dumps({"type": "error", "content": f"Unsupported agent type: {self.agent_obj.agent_type}"}) + "\n"

            yield json.dumps({"type": "status", "content": "Agent finished."}) + "\n"

        except asyncio.CancelledError:
            log.info(f"Agent {self.agent_obj.name} execution cancelled.")
            yield json.dumps({"type": "status", "content": "Agent execution cancelled."})
        except Exception as e:
            log.error(f"Error during agent execution: {e}", exc_info=True)
            yield json.dumps({"type": "error", "content": f"Agent execution failed: {str(e)}"}) + "\n"

    async def _execute_custom_python_agent(self, user_message: str, chat_history: list) -> AsyncIterator[str]:
        yield json.dumps({"type": "status", "content": "Running custom Python agent..."}) + "\n"
        # Placeholder for custom Python agent execution logic
        # In a real scenario, you would execute the agent_obj.definition (Python code)
        # and provide it with self.openwebui_tool_adapter and self.agent_tools
        
        # For now, just demonstrating the availability of these objects
        yield json.dumps({"type": "text", "content": f"Custom Python agent received message: {user_message}\n"}) + "\n"
        yield json.dumps({"type": "text", "content": f"Chat history: {chat_history}\n"}) + "\n"
        
        # Simulate tool call
        yield json.dumps({"type": "status", "content": "Custom Python agent calling a tool..."}) + "\n"
        try:
            tool_result = await self.openwebui_tool_adapter._execute_openwebui_tool_proxy("dummy_tool_id", "dummy_tool_name", param1="value1")
            yield json.dumps({"type": "text", "content": f"Tool result: {tool_result}\n"}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "content": f"Tool call failed: {str(e)}"}) + "\n"

        yield json.dumps({"type": "text", "content": "(Custom Python agent execution not yet implemented)"}) + "\n"

    async def _execute_llamaindex_workflow_agent(self, user_message: str, chat_history: list) -> AsyncIterator[str]:
        yield json.dumps({"type": "status", "content": "Running LlamaIndex workflow agent..."}) + "\n"
        # Placeholder for LlamaIndex workflow agent execution logic
        # In a real scenario, you would load the agent_obj.definition (LlamaIndex workflow JSON)
        # and execute it, providing it with self.openwebui_tool_adapter and self.agent_tools
        
        # For now, just demonstrating the availability of these objects
        yield json.dumps({"type": "text", "content": f"LlamaIndex workflow agent received message: {user_message}\n"}) + "\n"
        yield json.dumps({"type": "text", "content": f"Chat history: {chat_history}\n"}) + "\n"

        # Simulate tool call
        yield json.dumps({"type": "status", "content": "LlamaIndex workflow agent calling a tool..."}) + "\n"
        try:
            tool_result = await self.openwebui_tool_adapter._execute_openwebui_tool_proxy("dummy_tool_id", "dummy_tool_name", param1="value1")
            yield json.dumps({"type": "text", "content": f"Tool result: {tool_result}\n"}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "content": f"Tool call failed: {str(e)}"}) + "\n"

        yield json.dumps({"type": "text", "content": "(LlamaIndex workflow agent execution not yet implemented)"}) + "\n"


async def handle_agent_chat_completion(
    request: Request,
    agent_obj: AgentModel,
    form_data: Dict[str, Any],
    user_message: str,
    chat_history: list,
) -> AsyncIterator[str]:
    executor = AgentExecutor(request, agent_obj)
    async for chunk in executor.execute(user_message, chat_history):
        yield chunk