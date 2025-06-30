# Agent Mode - To-Do Checklist

This checklist breaks down the high-level plan for the Advanced Agent Mode into actionable tasks.

### Phase 1: Backend Foundation (Flexible Data Model & APIs)

- [x] Create database migration for the new `agent` table.
- [x] Define the `Agent` SQLAlchemy model in `backend/open_webui/models/agents.py`.
    - [ ] Implement `get_user_valves_by_id_and_user_id` class method in `Agent` model to retrieve user-specific agent valves from `Users.settings`.
    - [ ] Implement `update_user_valves_by_id_and_user_id` class method in `Agent` model to update user-specific agent valves in `Users.settings`.
    - [ ] Ensure `Agent` model's `valves` field is correctly defined for agent-specific configurations.
- [x] Implement full CRUD API endpoints under `/api/v1/agents/`.
- [x] Implement endpoints for managing agent valves (global and user-specific).

### Phase 2: Admin UI for Agent Management

- [x] Add a new "Agents" link to the Admin navigation sidebar.
- [x] Create the main "Agents" management page to list and manage created agents.
- [x] Develop the Agent Editor component.
- [x] Implement framework-aware logic in the editor (e.g., a dropdown for `agent_type`).
- [x] Build the Valve configuration UI within the Agent Editor.

### Phase 3: Core Execution Engine & Chat Integration

- [x] Modify the backend model-fetching logic to include agents in the list sent to the frontend.
- [x] Add a visual "Agent" tag to the model selection dropdown in the chat UI.
- [x] Implement the core Agent Execution Engine using a strategy pattern to handle different `agent_type`s.
- [x] Implement the `CustomPythonAgentHandler` for running bespoke Python agents.
    - [ ] Modify `AgentExecutor.execute` to accept `form_data` parameter.
    - [ ] Implement module loading for `custom_python` agents using a new `load_agent_module_by_id` function in `plugin.py`, mirroring `load_function_module_by_id`.
    - [ ] Ensure the agent's Python code defines a `Pipe`, `Filter`, or `Action` class with an `async def pipe(...)` entry point.
    - [ ] Prepare execution parameters for the agent's `pipe` function, mirroring `functions.py`'s `extra_params` structure (including `body`, `__user__`, `__request__`, `__event_emitter__`, `__event_call__`, etc.).
    - [ ] Populate `__tools__` parameter using `open_webui.utils.tools.get_tools` to provide access to Open WebUI tools.
    - [ ] Handle agent-specific `valves` (from `agent_obj.valves`) and user-specific `UserValves` (retrieved via `Agent.get_user_valves_by_id_and_user_id`), instantiating and passing them to the `pipe_instance`.
    - [ ] Implement error handling and output formatting (streaming/non-streaming) identically to `functions.py`, using `_process_line`, `openai_chat_chunk_message_template`, and `openai_chat_completion_message_template`.
- [ ] Implement the `LlamaIndexWorkflowHandler` for running LlamaIndex-based agents.
    - [ ] Modify `AgentExecutor.execute` to accept `form_data` parameter.
    - [ ] Dynamically select tools based on `form_data.metadata.tool_ids`.
    - [ ] Convert selected tools into LlamaIndex `FunctionTool` objects using `OpenWebUIToolAdapter`'s logic.
    - [ ] Ensure `call_agent` built-in tool is also converted to LlamaIndex `FunctionTool` and available.
- [ ] Develop the `OpenWebUIToolAdapter` to discover, convert, and proxy tool calls.
- [ ] Implement the `call_agent` built-in tool to allow for hierarchical agent execution.
- [ ] **New Task:** Add `load_agent_module_by_id` function to `backend/open_webui/utils/plugin.py`.

### Phase 4: Advanced Interaction & User Experience

- [x] Implement status streaming from the backend agent handlers (e.g., "Thinking...", "Calling tool X...").
- [x] Enhance the chat UI to display these real-time agent status updates.
- [x] Implement the backend logic for user interruption (stop signal).
- [x] Implement the UI button for user interruption.
- [x] Implement structured error reporting from agents to the backend.
- [x] Display structured errors in the UI.

### Phase 5: Documentation & Onboarding

- [ ] Write comprehensive developer documentation for the new Agent Framework.
- [ ] Create a working example of a `custom_python` agent.
- [ ] Create a working example of a `llamaindex_workflow` agent that utilizes the `OpenWebUIToolAdapter`.
