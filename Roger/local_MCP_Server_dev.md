# Local MCP Server Feature Development Progress

**Date:** 2025-05-11

## Completed Tasks (Verified against codebase):

1.  **Type Definitions (`src/lib/types/tools.ts`, `src/lib/types/index.ts`):**
    *   **Accuracy Note:** The specific MCP message structures (`McpMessage`, `McpResponse`, `McpErrorResponse`, `McpInitializeRequest`, `McpInitializeResponse`, `McpExecuteRequest`, `McpExecuteResponse`) listed in the original dev log were **not found** in `src/lib/types/tools.ts`. The file primarily defines interfaces like `McpCapability`, `McpHttpInvocation`, `LocalClientToolServerConfig`, and `DiscoveredServer`.
    *   Added `LocalClientToolServerConfig` interface to manage configurations for local MCP servers. (Verified)
    *   Extended the `Tool` type: (Verified)
        *   `isLocalClientCall?: boolean`: Flag to indicate if the tool call should be handled by the local client.
        *   `localMcpServerUrl?: string`: URL of the local MCP server if `isLocalClientCall` is true.
        *   `capabilities?: McpCapability[]`: Stores the specific capability details for local tools.
    *   Ensured relevant types (like `LocalClientToolServerConfig`, extended `Tool`) are exported via `src/lib/types/index.ts` (using `export * from './tools';`). (Verified)

2.  **Local Client Tool Utilities (`src/lib/utils/localClientToolExecutor.ts`):** (Largely Verified)
    *   Implemented as exported functions: `initializeAndGetCapabilities`, `executeLocalClientTool`, and `discoverLocalMcpServers`. (Verified)
    *   `initializeAndGetCapabilities(mcpSseEndpointUrl: string): Promise<McpSseInitializeResult>`: (Verified as of 2025-05-11, post-SSE refactor)
        *   Connects to the specified MCP SSE endpoint using `EventSource` (HTTP GET).
        *   Listens for an SSE message containing `capabilities`, `serverInfo`, and `messagePath`.
        *   Includes a timeout mechanism (`MCP_SSE_INIT_TIMEOUT_MS`, 5 seconds).
        *   Returns a `Promise<McpSseInitializeResult>`.
        *   Error handling: Throws `Error` for connection timeout, SSE connection errors, or if the received SSE message parsing fails or lacks expected fields.
    *   `executeLocalClientTool(params: any, capabilityInvocationDetails: McpHttpInvocation, mcpBaseUrl: string, messagePath: string): Promise<any>`: (Verified as of 2025-05-11)
        *   Signature updated to include `messagePath: string`.
        *   Constructs the POST URL using `mcpBaseUrl` and `messagePath` (e.g., `http://localhost:8000/messages/`).
        *   Constructs and sends an HTTP request (typically POST) based on `capabilityInvocationDetails` (method, parameter mapping to body).
        *   The `capabilityInvocationDetails.urlTemplate` and `parameterMapping.path` are not used to modify the POST URL itself, assuming `messagePath` is the definitive execution endpoint.
        *   Handles parameter mapping to the request body. Query parameters are less likely for this model but logic is retained.
        *   **Note:** The `capabilityId` parameter is not explicitly passed; server is expected to infer capability from payload or a specific field within `params` if `messagePath` is generic. This might require further refinement based on FastMCP server implementation.
        *   **Note:** Does not have a dedicated timeout mechanism for the `fetch` call itself. (Verified)
        *   Error handling: Throws `Error` for non-successful HTTP responses (`!response.ok`), including status text and attempts to include the response body. Also re-throws errors from `fetch`.
    *   `discoverLocalMcpServers(ports: number[], mcpSsePath: string = '/sse'): Promise<DiscoveredServer[]>`: (Verified as of 2025-05-11, post-SSE refactor)
        *   Iterates through specified `ports`, constructing SSE endpoint URLs (e.g., `http://localhost:{port}/sse`).
        *   Calls the new SSE-based `initializeAndGetCapabilities` for each endpoint.
        *   Timeout for each discovery attempt is handled within `initializeAndGetCapabilities`.
        *   Returns an array of `DiscoveredServer` objects for successfully initialized servers, including their `url` (the SSE endpoint), `serverInfo`, and `capabilities`.
        *   Error handling: Catches errors from individual `initializeAndGetCapabilities` calls (including timeouts, connection errors), logs them, and allows other discoveries to proceed.
    *   **General Error Handling Notes (Post-SSE Refactor):**
        *   No explicit parsing of a structured `McpErrorResponse` type from server error bodies is evident in `executeLocalClientTool`'s primary error path; it includes raw text.
        *   `initializeAndGetCapabilities` has specific error messages for SSE timeout, connection, and parsing issues.

3.  **Stores (`src/lib/stores/index.ts`):** (Verified as of 2025-05-11)
    *   Created a writable store `localMcpTools`: (Verified)
        *   Stores an array of `LocalClientToolServerConfig`.
        *   Persists its state to `localStorage` under the key `open-webui_local-mcp-tools`.
        *   Initializes as an empty array if no data is found in `localStorage` or if parsing fails.
    *   Corrected type annotations for existing `tools` (as `Tool[] | null`) and `toolServers` (as `ToolServer[]`) stores. (Verified)
    *   Added a placeholder `availableTools` store (`writable<Tool[]>([])`) with a TODO comment about merging logic for backend and local tools. (Verified) (Note: The dev log's point about this being "partially addressed by a derived store in `ToolServersModal.svelte`" is accurate.)

4.  **Automatic Discovery of Default Local MCP Server (`src/routes/(app)/+layout.svelte`):** (Verified)
    *   On application load (client-side `onMount`), the system automatically attempts to connect to a default local MCP SSE endpoint: `http://localhost:8000/sse` (using constant `DEFAULT_LOCAL_MCP_SSE_ENDPOINT`). (Verified as of 2025-05-11)
    *   Utilizes the SSE-based `initializeAndGetCapabilities` from `localClientToolExecutor`. (Verified as of 2025-05-11)
    *   If the connection and SSE handshake are successful (yielding `McpSseInitializeResult`): (Verified as of 2025-05-11)
        *   A `LocalClientToolServerConfig` object is created/updated.
        *   This configuration (including `mcpEndpointUrl` (the SSE endpoint), `name` (from `serverInfo` or host), `enabled: true` (or preserved), `discoveredCapabilities`, `serverInfo`, and `messagePath`) is added/updated in the `localMcpTools` store.
        *   A success toast (`Local SSE tools updated from localhost:8000`) is displayed.
    *   If the connection/initialization fails, a warning is logged to the console. Previously discovered information for this server (if any) remains in `localStorage`. (Verified as of 2025-05-11)

5.  **Tool Display and Selection Modal (`src/lib/components/chat/ToolServersModal.svelte`):** (Verified & Stable as of 2025-05-11, no changes from previous verification)
    *   **Current Status:** (Verified)
    *   The modal imports the `localMcpTools` store. (Verified)
    *   A Svelte derived store (`allAvailableTools`) has been implemented to create a unified list of tools: (Verified)
        *   It combines tools from the backend (`$tools` store), marking them with `isLocalClientCall: false`.
        *   It derives individual tools from each enabled `LocalClientToolServerConfig` in `$localMcpTools` by iterating through their `discoveredCapabilities`. These local tools are marked with `isLocalClientCall: true`, their IDs are constructed using `mcpEndpointUrl#capabilityId`, and they store `localMcpServerUrl` and the specific capability.
    *   The modal's template iterates over this `$allAvailableTools` list. (Verified)
    *   Each tool in the list is rendered with: (Verified)
        *   A checkbox to enable/disable the tool. The checked state is synchronized with the `selectedToolIds` prop.
        *   The tool's name.
        *   A visual indicator ("(Local)" badge using `i18n.t('Local')`) for tools where `isLocalClientCall` is true.
        *   A collapsible section showing the tool's description and, for local tools, details like the server URL and capability ID.
    *   **Note:** The i18n syntax in the current version of `ToolServersModal.svelte` appears to be correct (using `{i18n.t(...)}`). (Verified)
    *   **Note:** No outstanding TypeScript errors were observed in the code. Component considered stable for now. (Verified 2025-05-11)

## In Progress:


## Next Steps (Revised based on current progress):

