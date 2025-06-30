# Agent Framework Documentation

This document provides a comprehensive guide for developers on how to create, manage, and use agents within the Open WebUI ecosystem.

## 1. Introduction

The Agent Framework is a powerful feature that allows developers to create sophisticated, tool-using agents that can be integrated directly into the Open WebUI chat interface. The framework is designed to be flexible, supporting both custom Python agents and agents built with external frameworks like LlamaIndex.

## 2. Agent Types

There are two primary types of agents you can create:

*   **`custom_python`**: This agent type allows you to write your own Python code to define the agent's behavior. It offers maximum flexibility and control.
*   **`llamaindex_workflow`**: This agent type allows you to define an agent using a LlamaIndex workflow in JSON format. This is ideal for creating agents that leverage the power of LlamaIndex's structured execution and tool-using capabilities.

## 3. Creating a `custom_python` Agent

To create a `custom_python` agent, you need to define a Python script that contains a class named `Pipe`. This class must have an asynchronous method named `pipe`.

### 3.1. The `Pipe` Class and `pipe` Method

The `pipe` method is the entry point for your agent. It receives two arguments:

*   `body` (dict): The full request body, identical to the one received by `functions.py`'s pipes. This contains `messages`, `model`, `stream`, `metadata`, etc.
*   `**kwargs` (dict): A dictionary containing extra parameters, including:
    *   `__user__` (dict): Information about the current user.
    *   `__request__` (Request): The FastAPI request object.
    *   `__tools__` (dict): A dictionary of available tools in the Open WebUI format.
    *   `__event_emitter__` and `__event_call__`: For emitting events.

### 3.2. Example `custom_python` Agent

```python
# file: example_custom_python_agent.py

class Pipe:
    """
    This is an example of a custom Python agent.
    It demonstrates how to define a pipe class with a pipe method
    that can access tools and other context information.
    """

    def __init__(self):
        # You can define Valves for your agent here
        # class Valves:
        #     my_valve: str = "default_value"
        pass

    async def pipe(self, body: dict, **kwargs):
        """
        This is the entry point for the agent.
        It receives the full request body and any extra parameters.
        """
        print("Custom Python agent started!")

        # Access user message from the body
        messages = body.get("messages", [])
        user_message = ""
        if messages and messages[-1]["role"] == "user":
            user_message = messages[-1]["content"]

        print(f"User message: {user_message}")

        # Access tools from kwargs
        tools = kwargs.get("__tools__", {})
        print(f"Available tools: {list(tools.keys())}")

        # Example of using a tool
        if "search" in tools:
            print("Calling the 'search' tool...")
            try:
                search_tool = tools["search"]["callable"]
                search_result = await search_tool(query=f"information about {user_message}")
                print(f"Search result: {search_result}")
                yield f"I found this information using the search tool: {search_result}"
            except Exception as e:
                print(f"Error calling search tool: {e}")
                yield f"Sorry, I couldn't use the search tool. Error: {e}"
        else:
            yield f"I received your message: '{user_message}', but I don't have a 'search' tool to help you."

        print("Custom Python agent finished.")
```

## 4. Creating a `llamaindex_workflow` Agent

To create a `llamaindex_workflow` agent, you need to provide a JSON definition of a LlamaIndex workflow.

### 4.1. Workflow Structure

The JSON definition should contain a `workflow` object with `nodes` and `edges`.

*   **Nodes**: Define the steps in your workflow (e.g., `start`, `tool`, `llm`, `end`).
*   **Edges**: Define the connections between the nodes.

### 4.2. Tool Usage

The `llamaindex_workflow` agent will receive a list of LlamaIndex `FunctionTool` objects, which are converted from the Open WebUI tools specified in `form_data.metadata.tool_ids`.

### 4.3. Example `llamaindex_workflow` Agent

```json
// file: example_llamaindex_workflow_agent.json
{
  "name": "LlamaIndex Search Agent",
  "description": "An example agent that uses LlamaIndex to search for information and answer questions.",
  "workflow": {
    "nodes": [
      {
        "id": "start",
        "type": "start",
        "config": {
          "input_schema": {
            "type": "object",
            "properties": {
              "query": {
                "type": "string",
                "description": "The user's query."
              }
            },
            "required": ["query"]
          }
        }
      },
      {
        "id": "search_tool",
        "type": "tool",
        "config": {
          "tool_name": "search",
          "input_map": {
            "query": "start.query"
          }
        }
      },
      {
        "id": "llm_step",
        "type": "llm",
        "config": {
          "prompt_template": "Based on the following search result, please answer the user's query.\n\nSearch Result:\n{search_tool.output}\n\nUser Query: {start.query}\n\nAnswer:",
          "model": "ollama/llama2"
        }
      },
      {
        "id": "end",
        "type": "end",
        "config": {
          "output_map": {
            "answer": "llm_step.output"
          }
        }
      }
    ],
    "edges": [
      {
        "from": "start",
        "to": "search_tool"
      },
      {
        "from": "search_tool",
        "to": "llm_step"
      },
      {
        "from": "llm_step",
        "to": "end"
      }
    ]
  }
}
```

## 5. Valves and UserValves

Both agent types support `valves` (agent-specific configurations) and `UserValves` (user-specific configurations).

*   **`valves`**: Defined in the agent's `valves` field in the database.
*   **`UserValves`**: Stored in the `Users.settings` field, under `settings["agents"]["valves"][agent_id]`.

To use them, define a `Valves` and/or `UserValves` Pydantic model class within your `Pipe` class:

```python
class Pipe:
    class Valves:
        my_valve: str = "default_value"

    class UserValves:
        user_specific_valve: str = "default_user_value"

    async def pipe(self, body: dict, **kwargs):
        # Access valves
        print(f"My valve: {self.valves.my_valve}")

        # Access user valves
        user = kwargs.get("__user__", {})
        if "valves" in user:
            print(f"User specific valve: {user['valves'].user_specific_valve}")
```

## 6. Agent Execution Flow

1.  A user selects an agent from the model dropdown and sends a message.
2.  The request is routed to `handle_agent_chat_completion`.
3.  `AgentExecutor` is instantiated.
4.  Based on `agent_type`, the corresponding execution method is called (`_execute_custom_python_agent` or `_execute_llamaindex_workflow_agent`).
5.  The agent's code/workflow is loaded and executed with the appropriate context and tools.
6.  The result is streamed back to the user.
