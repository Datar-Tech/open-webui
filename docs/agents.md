# Agent Framework Documentation

This document provides a guide for developers on how to create, manage, and use agents within Open WebUI.

## Overview

The Agent Framework is designed to be a flexible and powerful system for extending Open WebUI with autonomous capabilities. It allows for the creation of agents using custom Python code or by leveraging external agentic frameworks like LlamaIndex.

## Key Concepts

- **Agent:** An agent is a special type of model that can perform actions and interact with tools. Agents are managed through the Admin Panel and can be assigned to users and groups just like regular models.
- **Agent Type:** Defines the execution logic for the agent. The two primary types are `custom_python` and `llamaindex_workflow`.
- **Definition:** The core logic of the agent. For a `custom_python` agent, this is the Python code to be executed. For a `llamaindex_workflow` agent, this is the JSON definition of the workflow.
- **Valves:** A set of configuration values that can be used to control the agent's behavior. These are defined on a per-agent basis.
- **OpenWebUIToolAdapter:** A component that is automatically provided to running agents, allowing them to discover and use any tool that the current user has permission to access.
- **Agent-to-Agent Communication:** Agents can call other agents using the built-in `call_agent` tool.

## Creating a Custom Python Agent

To create a custom Python agent, follow these steps:

1.  **Navigate to the Admin Panel:** Go to the "Agents" section in the Admin Panel.
2.  **Create a New Agent:** Click the "Create Agent" button.
3.  **Set Agent Type:** Select `custom_python` as the agent type.
4.  **Write the Definition:** Write your Python code in the "Definition" field. The code must be a single script. You can use the `openwebui_tool_adapter` and `agent_tools` objects to interact with Open WebUI's tools and other agents.

**Example `custom_python` Agent:**

```python
# A simple agent that uses a tool and prints the result
async def main(user_message, chat_history, openwebui_tool_adapter, agent_tools):
    print(f"User message: {user_message}")
    
    # Use a tool
    tool_result = await openwebui_tool_adapter.execute_tool_by_id("some_tool_id", "some_tool_name", arg1="value1")
    print(f"Tool result: {tool_result}")
    
    # Call another agent
    agent_response = await agent_tools.call_agent("another_agent_id", "some message")
    print(f"Agent response: {agent_response}")
    
    return "Task complete!"
```

## Creating a LlamaIndex Workflow Agent

To create a LlamaIndex workflow agent, follow these steps:

1.  **Navigate to the Admin Panel:** Go to the "Agents" section in the Admin Panel.
2.  **Create a New Agent:** Click the "Create Agent" button.
3.  **Set Agent Type:** Select `llamaindex_workflow` as the agent type.
4.  **Provide the Definition:** Paste the JSON definition of your LlamaIndex workflow into the "Definition" field.

**Example `llamaindex_workflow` Agent:**

```json
{
  "workflow": {
    "nodes": [
      {
        "id": "start",
        "type": "start",
        "next": "end"
      },
      {
        "id": "end",
        "type": "end"
      }
    ]
  }
}
```
