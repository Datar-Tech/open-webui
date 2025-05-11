import type {
  McpCapability,
  McpHttpInvocation,
  DiscoveredServer,
  McpServerInfo,
  McpSseInitializeResult
} from '$lib/types/tools';

const MCP_DEFAULT_PATH = '/sse';
const DISCOVERY_TIMEOUT_MS = 10000; // 10 seconds scan timeout
const MCP_SSE_INIT_TIMEOUT_MS = 5000; // 5 seconds for SSE handshake to complete

/**
 * Initializes with a local MCP server using SSE and retrieves its capabilities,
 * server info, and the message path for subsequent POST requests.
 * @param mcpSseEndpointUrl The full URL to the MCP server's SSE endpoint (e.g., http://localhost:8000/sse).
 * @returns A promise that resolves to an McpSseInitializeResult object.
 * @throws Will throw an error if the connection fails, times out, or the expected message is not received.
 */
export function initializeAndGetCapabilities(
  mcpSseEndpointUrl: string
): Promise<McpSseInitializeResult> {
  console.log(`Initializing MCP server via SSE at: ${mcpSseEndpointUrl}`);

  return new Promise((resolve, reject) => {
    const eventSource = new EventSource(mcpSseEndpointUrl);
    let timeoutId: NodeJS.Timeout | null = null;

    const cleanup = () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      eventSource.close();
      eventSource.onmessage = null;
      eventSource.onerror = null;
      eventSource.onopen = null;
    };

    timeoutId = setTimeout(() => {
      cleanup();
      reject(
        new Error(`MCP SSE initialization timed out after ${MCP_SSE_INIT_TIMEOUT_MS / 1000}s for ${mcpSseEndpointUrl}`)
      );
    }, MCP_SSE_INIT_TIMEOUT_MS);

    eventSource.onopen = () => {
      console.log(`SSE connection opened to ${mcpSseEndpointUrl}`);
    };

    eventSource.onmessage = (event) => {
      console.log(`SSE message received from ${mcpSseEndpointUrl}:`, event.data);
      try {
        const data = JSON.parse(event.data as string);
        if (data.capabilities && data.messagePath) {
          cleanup();
          resolve({
            capabilities: data.capabilities as McpCapability[],
            serverInfo: data.serverInfo as McpServerInfo | undefined,
            messagePath: data.messagePath as string
          });
        } else {
          console.warn('Received SSE message without expected fields (capabilities, messagePath)', data);
        }
      } catch (parseError) {
        cleanup();
        reject(
          new Error(
            `Failed to parse MCP SSE initialization data from ${mcpSseEndpointUrl}: ${parseError} (Data: ${event.data})`
          )
        );
      }
    };

    eventSource.onerror = (errorEvent) => {
      cleanup();
      console.error(`SSE error from ${mcpSseEndpointUrl}:`, errorEvent);
      reject(new Error(`MCP SSE connection error with ${mcpSseEndpointUrl}. Check server and CORS.`));
    };
  });
}

/**
 * Executes a specific capability of a local client tool server.
 * @param params - The parameters required by the capability.
 * @param capabilityInvocationDetails - The McpHttpInvocation object describing how to call the capability.
 * @param mcpBaseUrl - The base URL of the MCP server (e.g., http://localhost:8000).
 * @param messagePath - The specific path for POSTing execution messages (obtained from SSE handshake, e.g., /messages/).
 * @returns A promise that resolves to the result of the tool execution.
 * @throws Error if execution fails.
 */
export async function executeLocalClientTool(
  params: any,
  capabilityInvocationDetails: McpHttpInvocation,
  mcpBaseUrl: string, 
  messagePath: string 
): Promise<any> {
  if (capabilityInvocationDetails.type !== 'http') {
    throw new Error('Unsupported capability invocation type. Only "http" is supported.');
  }

  let postUrl = mcpBaseUrl.endsWith('/') ? mcpBaseUrl.slice(0, -1) : mcpBaseUrl;
  postUrl += messagePath.startsWith('/') ? messagePath : `/${messagePath}`;
  
  // Note: The original capabilityInvocationDetails.urlTemplate and parameterMapping.path
  // are not used here to modify postUrl, assuming messagePath is the definitive endpoint for POST.
  // If urlTemplate or path parameters were meant to be part of the POST body or further
  // qualify the action on the server side, that logic is encapsulated within how 'params'
  // and 'capabilityInvocationDetails.parameterMapping.body' are structured and interpreted by the server.

  const requestOptions: RequestInit = {
    method: capabilityInvocationDetails.method, // Should typically be POST for this model
    headers: {
      'Content-Type': 'application/json'
      // Add other headers if specified in invocationDetails
    }
  };

  // Construct the body based on parameterMapping
  // This logic remains largely the same as before, as it defines the payload.
  if (capabilityInvocationDetails.method !== 'GET' && capabilityInvocationDetails.method !== 'DELETE') {
    let bodyData: any = {};
    if (capabilityInvocationDetails.parameterMapping?.body) {
      if (typeof capabilityInvocationDetails.parameterMapping.body === 'string') {
        bodyData = params[capabilityInvocationDetails.parameterMapping.body as keyof typeof params];
      } else {
        for (const [paramName, bodyKey] of Object.entries(
          capabilityInvocationDetails.parameterMapping.body
        )) {
          if (params.hasOwnProperty(paramName)) {
            bodyData[bodyKey] = params[paramName];
          }
        }
      }
    } else {
      bodyData = params; // Default: send all params in body
    }
    // It's crucial that the body also includes information about *which* capability to execute,
    // if the messagePath is generic (e.g., /messages/). This might be `capabilityInvocationDetails.id`
    // or the original `capabilityInvocationDetails.urlTemplate` if it serves as an action identifier.
    // For example: bodyData = { capabilityId: capabilityInvocationDetails.originalIdOrPath, parameters: bodyData };
    // This detail depends on the FastMCP server's expectation for the /messages/ endpoint.
    // Assuming for now the server infers capability from the overall structure or a specific field within params.
    requestOptions.body = JSON.stringify(bodyData);
  }
  // Query parameters are less likely for a POST to a generic /messages/ path,
  // but the logic is kept if capabilityInvocationDetails still uses GET/DELETE for some reason.
  else {
    const queryParams = new URLSearchParams();
    if (capabilityInvocationDetails.parameterMapping?.query) {
      for (const [paramName, queryKey] of Object.entries(
        capabilityInvocationDetails.parameterMapping.query
      )) {
        if (params.hasOwnProperty(paramName)) {
          queryParams.append(queryKey, params[paramName]);
        }
      }
    }
    for (const key in params) {
      if (!queryParams.has(key) && 
          (!capabilityInvocationDetails.parameterMapping?.path || !Object.keys(capabilityInvocationDetails.parameterMapping.path).includes(key)) &&
          (!capabilityInvocationDetails.parameterMapping?.body) // Ensure not already handled by body
         ) {
           if (typeof params[key] === 'string' || typeof params[key] === 'number' || typeof params[key] === 'boolean') {
              queryParams.append(key, params[key].toString());
          }
      }
    }
    if (queryParams.toString()) {
      postUrl += `?${queryParams.toString()}`;
    }
  }

  try {
    const response = await fetch(postUrl, requestOptions);
    if (!response.ok) {
      let errorBody = '';
      try {
        errorBody = await response.text();
      } catch (e) { /* ignore */ }
      throw new Error(
        `Tool execution failed: ${response.status} ${response.statusText}. ${errorBody}`
      );
    }
    return await response.json();
  } catch (error) {
    console.error(`Error executing local client tool at ${postUrl}:`, error);
    throw error;
  }
}

/**
 * Discovers local MCP servers by attempting an initialize handshake on a list of ports.
 * @param ports - An array of port numbers to scan.
 * @param mcpSsePath - The path for the MCP SSE endpoint (default: '/sse').
 * @returns A promise that resolves to an array of DiscoveredServer objects.
 */
export async function discoverLocalMcpServers(
  ports: number[],
  mcpSsePath: string = MCP_DEFAULT_PATH 
): Promise<DiscoveredServer[]> {
  const discoveredServers: DiscoveredServer[] = [];

  const discoveryPromises = ports.map(async (port) => {
    const mcpSseEndpointUrl = `http://localhost:${port}${mcpSsePath.startsWith('/') ? mcpSsePath : '/' + mcpSsePath}`;
    try {
      const result: McpSseInitializeResult = await initializeAndGetCapabilities(mcpSseEndpointUrl);

      if (result.error) {
        console.warn(`MCP SSE Initialization for ${mcpSseEndpointUrl} reported an error: ${result.error}`);
        return null;
      }
      
      discoveredServers.push({
        url: mcpSseEndpointUrl, 
        serverInfo: result.serverInfo,
        capabilities: result.capabilities,
      });
      return mcpSseEndpointUrl; 
    } catch (error) {
      if (error instanceof Error) {
        console.log(
          `Discovery/Initialization via SSE failed for ${mcpSseEndpointUrl}: ${error.message}`
        );
      } else {
        console.log(
          `Discovery/Initialization via SSE failed for ${mcpSseEndpointUrl} with an unknown error.`
        );
      }
      return null; 
    }
  });

  await Promise.allSettled(discoveryPromises);
  
  return discoveredServers;
}
