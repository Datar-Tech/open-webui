# Project Plan: Advanced Agent Mode (v4)

The goal is to create a flexible, secure, and powerful Agent Mode within Open WebUI, supporting both custom Python code and external agentic frameworks like LlamaIndex.

### Phase 1: Backend Foundation (Data Model & APIs)

1.  **Flexible `Agent` Database Model:** I will create a new `agent` table. This table will store the agent's unique properties: `id`, `agent_type` (e.g., `custom_python`, `llamaindex_workflow`), a flexible JSON `definition` field, and a `valves` field for configurations.
    *   **User-Specific Valves for Agents:** Implement `get_user_valves_by_id_and_user_id` and `update_user_valves_by_id_and_user_id` class methods in the `Agent` model. These methods will manage user-specific agent configurations by storing them within the `Users` model's `settings` JSON field, mirroring the approach used for `Functions` to ensure consistency and avoid new database tables for user-specific settings.
2.  **Build Agent API Endpoints:** I will create the necessary API endpoints under `/api/v1/agents/` for full CRUD (Create, Read, Update, Delete) management of these new agents and their configurations.

### Phase 2: Admin UI for Agent Management

1.  **"Agents" Section in Admin Page:** A new "Agents" section will be added to the Admin UI for centralized management.
2.  **Framework-Aware Agent Editor:** The UI will adapt based on the selected `agent_type`, showing a code editor for custom Python or specific configuration fields for frameworks like LlamaIndex.
3.  **Valve Configuration UI:** A dedicated interface will be created to manage the agent's `valves`.

### Phase 3: Core Execution Engine & Chat Integration

1.  **Unified Model/Agent Selection & Permissions:**
    *   Agents will be integrated directly into the existing "Model" selection dropdown in the chat UI, distinguished by a special "Agent" tag.
    *   **Access control will be handled by the existing model permission system.** When an agent is created, it will be registered in a way that it appears in the model list. Administrators will then assign user groups access to agents just as they do for standard models.
2.  **Agent Execution Engine (Strategy Pattern):** The backend will use a strategy pattern to delegate requests to the correct handler based on the agent's `agent_type`.
    *   **Custom Python Agent Execution Alignment:** For `agent_type: custom_python`, the execution will precisely mirror the `functions.py` module's handling of "Pipes" to ensure consistency and leverage existing robust mechanisms. This includes:
        *   **Module Loading:** The agent's Python code (`agent_obj.definition`) will be dynamically loaded into a new Python module using a dedicated `load_agent_module_by_id` function in `plugin.py`. This function will write the code to a temporary file, execute it in a new module namespace, and expect a `Pipe`, `Filter`, or `Action` class within the agent's definition.
        *   **Parameter Structure:** The agent's entry point function (expected to be an `async def pipe(...)` method within the loaded class) will receive parameters structured identically to `functions.py`'s pipes. This includes `body` (containing the full `form_data`), `__user__`, `__request__`, `__event_emitter__`, `__event_call__`, and other `extra_params`.
        *   **Tool Availability:** The `__tools__` parameter will be populated using `open_webui.utils.tools.get_tools`, ensuring the agent has access to the same set of Open WebUI tools in the same format as functions.
        *   **Valve Handling:** The agent's `valves` (from `agent_obj.valves`) and user-specific `UserValves` (retrieved via `Agent.get_user_valves_by_id_and_user_id`) will be correctly instantiated and passed to the `pipe_instance` if the agent's module defines `Valves` and `UserValves` classes.
        *   **Error Handling & Output Formatting:** The execution will adopt the exact error handling and streaming/non-streaming output formatting logic from `functions.py`, including the use of `_process_line`, `openai_chat_chunk_message_template`, and `openai_chat_completion_message_template` to ensure consistent frontend display.
    *   **LlamaIndex Workflow Agent Tooling:** For `agent_type: llamaindex_workflow`, the agent will receive tools specifically tailored for the LlamaIndex framework. Tools will be dynamically selected based on `form_data.metadata.tool_ids` (similar to `custom_python` agents), then converted into LlamaIndex `FunctionTool` objects by `OpenWebUIToolAdapter` for seamless integration with LlamaIndex workflows. This ensures that LlamaIndex agents only operate with the explicitly requested tools, enhancing control and relevance.
3.  **The `OpenWebUIToolAdapter`:** This component will be provided to the running agent. It will:
    *   Discover all tools **that the current user has permission to access**.
    *   Convert these tools into the format expected by the agent's framework (e.g., `llama_index.core.tools.FunctionTool`).
    *   Proxy tool execution calls from the agent back to the Open WebUI core, ensuring all existing security and logic are reused.
4.  **Agent-to-Agent Communication:** Implemented via a built-in `call_agent` tool, allowing for hierarchical agent designs.

### Phase 4: Advanced Interaction & User Experience

1.  **Advanced Streaming:** The engine will stream both status updates (`"Thinking..."`, `"Calling tool X..."`) and intermediate results to the UI.
2.  **User Interruption:** A "stop" button will be implemented to allow users to gracefully terminate a running agent.
3.  **Robust Error Handling & Reporting:** The engine will catch errors and report a structured summary of the agent's state and failure point to the UI.

### Phase 5: Documentation & Onboarding

1.  **Developer Documentation:** I will create clear documentation for the Agent Framework.
2.  **Example Agents:** I will build and include at least two example agents (one custom, one LlamaIndex) as practical templates.
