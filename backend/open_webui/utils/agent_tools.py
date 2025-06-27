from typing import Any, Dict
from open_webui.utils.log import log
from open_webui.models.agents import Agent
from open_webui.utils.agent_executor import handle_agent_chat_completion
from fastapi import Request

class AgentTools:
    def __init__(self, request: Request):
        self.request = request

    async def call_agent(self, agent_id: str, message: str) -> Any:
        """Calls another agent with a given message and returns its response."""
        log.info(f"Agent calling another agent: {agent_id} with message: {message}")
        
        agent_obj = Agent.get_by_id(agent_id)
        if not agent_obj:
            log.error(f"Agent {agent_id} not found for nested call.")
            return f"Error: Agent {agent_id} not found."

        # Simulate a chat completion request to the nested agent
        # This will trigger the agent_executor for the nested agent
        # We need to capture the streamed response and return it as a single string
        
        # Construct a dummy form_data for the nested call
        # This needs to mimic what chat_completion expects
        form_data = {
            "model": agent_id, # The agent's ID acts as the model ID
            "model_item": {"id": agent_id, "agent": True, "name": agent_obj.name, "agent_type": agent_obj.agent_type},
            "messages": [{"role": "user", "content": message}],
            "stream": False, # We want the full response back for the calling agent
        }

        full_response = []
        async for chunk in handle_agent_chat_completion(
            self.request, agent_obj, form_data, message, [] # Pass empty chat history for nested call
        ):
            full_response.append(chunk)
        
        return "".join(full_response)

