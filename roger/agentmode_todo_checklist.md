# Agent Mode - To-Do Checklist

This checklist breaks down the high-level plan for the Advanced Agent Mode into actionable tasks.

### Phase 1: Backend Foundation (Flexible Data Model & APIs)

- [x] Create database migration for the new `agent` table.
- [x] Define the `Agent` SQLAlchemy model in `backend/open_webui/models/agents.py`.
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
- [x] Implement the `LlamaIndexWorkflowHandler` for running LlamaIndex-based agents.
- [x] Develop the `OpenWebUIToolAdapter` to discover, convert, and proxy tool calls.
- [x] Implement the `call_agent` built-in tool to allow for hierarchical agent execution.

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