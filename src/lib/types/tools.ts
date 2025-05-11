// Existing tool structure (inferred from ToolServersModal.svelte and stores)
export interface Tool {
  id: string;
  name: string;
  meta?: {
    description?: string;
  };
  // Extensions for local client-side tools
  isLocalClientCall?: boolean;
  localMcpServerUrl?: string; // Full MCP endpoint URL for the local tool
  capabilities?: McpCapability[]; // Cached capabilities from MCP initialize
}

// For tool servers (inferred from ToolServersModal.svelte and stores)
export interface ToolServer {
  id?: string; // Assuming an ID might be useful
  url: string;
  openapi?: {
    info?: {
      title?: string;
      version?: string;
      description?: string;
    };
  };
  specs?: Array<{
    name?: string;
    description?: string;
    // Potentially more details from OpenAPI spec
  }>;
  // Flag to indicate if this is a local MCP server config
  // This might be redundant if local tools are managed separately or within the Tool type
  isLocalMcpServer?: boolean;
}

// MCP (Model Context Protocol) related types as per PRD 4.6

export interface McpServerInfo {
  name: string;
  description?: string;
  version?: string;
  // Other metadata from MCP initialize response
}

export interface McpCapability {
  id: string; // Unique identifier for the capability
  name: string; // Human-readable name
  description?: string;
  parameters: any; // JSON Schema for parameters
  invocation: McpHttpInvocation | any; // Invocation details, focusing on HTTP
  // Potentially other fields like 'type' if capabilities can be other than 'tool'
}

export interface McpHttpInvocation {
  type: 'http';
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'; // Common HTTP methods
  urlTemplate: string; // URL template, e.g., "/tools/{toolId}/execute"
  // Parameter mapping details (how tool params map to query, path, body)
  // This might be a more complex object based on MCP spec for HTTP invocation
  parameterMapping?: {
    query?: { [paramName: string]: string }; // maps tool param to query param name
    path?: { [paramName: string]: string };  // maps tool param to path variable name
    body?: { [paramName: string]: string } | string; // maps tool params to body structure or a single param to body
  };
  // Potentially headers, auth, etc.
}

// Configuration for a local client tool server (as per PRD 4.6 - LocalClientToolServerConfig)
// This might be represented by a Tool object where isLocalClientCall = true
// and localMcpServerUrl is set.
// If a separate config object is needed for storage or management:
export interface LocalClientToolServerConfig {
  id: string; // Unique ID for this local server config
  mcpEndpointUrl: string; // e.g., http://localhost:8000/mcp
  name?: string; // User-defined name for this server
  enabled?: boolean; // If this server's tools are globally enabled by user
  messagePath?: string; // Path for POSTing execution requests, obtained from SSE handshake
  serverInfo?: McpServerInfo; // Information obtained from the server during handshake
  // Discovered capabilities could be stored here too, or within individual Tool objects
  discoveredCapabilities?: McpCapability[];
}

// For discovered local MCP servers (PRD 4.4 - discoverLocalMcpServers)
export interface DiscoveredServer {
  url: string; // The full MCP endpoint URL, e.g., http://localhost:8000/mcp
  serverInfo?: McpServerInfo; // Info from MCP initialize
  capabilities: McpCapability[]; // Capabilities discovered
  error?: string; // If there was an error during discovery for this specific server
}

export interface McpSseInitializeResult {
  capabilities: McpCapability[];
  serverInfo?: McpServerInfo;
  messagePath: string; // The path for subsequent POST requests for tool execution
  error?: string; // Optional error message if initialization failed
}
