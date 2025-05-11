import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { SSEClientTransport } from '@modelcontextprotocol/sdk/client/sse.js';
import { z } from 'zod';
import { ToolSchema } from '@modelcontextprotocol/sdk/types.js';
import type {
	McpCapability,
	DiscoveredServer,
	McpServerInfo,
	McpSseInitializeResult
} from '$lib/types/tools';

type SdkTool = z.infer<typeof ToolSchema>;

const MCP_DEFAULT_PATH = '/sse'; // Default path for SSE endpoint on a server
const MCP_SSE_INIT_TIMEOUT_MS = 60000; // 60 seconds for SSE handshake and capability fetching

/**
 * Initializes with a local MCP server using SSE and retrieves its capabilities,
 * server info, and the message path for subsequent POST requests.
 * @param mcpSseEndpointUrl The full URL to the MCP server's SSE endpoint (e.g., http://localhost:8000/sse).
 * @returns A promise that resolves to an McpSseInitializeResult object.
 * @throws Will throw an error if the connection fails, times out, or the expected message is not received.
 */
export async function initializeAndGetCapabilities(
	mcpSseEndpointUrl: string
): Promise<McpSseInitializeResult> {
	console.log(`Initializing MCP server via SDK at: ${mcpSseEndpointUrl}`);

	const transport = new SSEClientTransport(new URL(mcpSseEndpointUrl));
	// Added name and version to Client constructor
	const client = new Client({ name: 'OpenWebUI-LocalClient', version: '0.0.1' });

	try {
		await client.connect(transport); // Establishes connection and performs handshake

		const sdkCapabilities = await client.listTools();
		const serverInfo = client.getServerVersion() as McpServerInfo | undefined; // Use getServerInfo()

		// The messagePath for POST requests. The SDK client's transport should store the endpoint.
		// For SSETransport in the JS SDK, `client.transport.endpoint` seems to hold the path like '/messages/'.
		// We need to ensure this property exists and is accessible.
		// If `client.transport` is an instance of `SSETransport`, it might have an `endpoint` property.
		let messagePath = '';
		if (client.transport && typeof (client.transport as any).endpoint === 'string') {
			messagePath = (client.transport as any).endpoint;
		} else {
			// Fallback or error if messagePath cannot be determined, though callTool should handle it.
			// For compatibility with existing McpSseInitializeResult, we need something.
			// Defaulting to /mcp if not found, but this might be an issue.
			console.warn(
				`Message path (endpoint) not explicitly found on transport for ${mcpSseEndpointUrl}. Tool execution might rely on client.callTool's internal logic.`
			);
			// Removed problematic serverInfo?.baseUrl access as it's not on the local McpServerInfo type
		}

		// Map SDK Tool[] to Open WebUI McpCapability[]
		const mcpBaseUrl = mcpSseEndpointUrl.substring(0, mcpSseEndpointUrl.lastIndexOf(MCP_DEFAULT_PATH));
		const capabilities: McpCapability[] = (sdkCapabilities?.tools || []).map((sdkTool: SdkTool) => {
			// Assuming SdkTool has id, name, description, inputSchema, outputSchema
			// OpenWebUI's McpCapability also has `type` and `invocation`
			// For now, we'll assume 'http' type and let executeLocalClientTool handle invocation if needed,
			// or rely on client.callTool which abstracts invocation.
			const capability: McpCapability = {
				id: sdkTool.name, // Changed from sdkTool.id as ToolSchema uses name
				name: sdkTool.name,
				description: sdkTool.description,
				parameters: sdkTool.inputSchema, // Changed to 'parameters' to match McpCapability
				// outputSchema: undefined, // outputSchema is not in McpCapability interface
				// type: 'http', // type is not in McpCapability interface
				// isLocalClientCall: true, // isLocalClientCall is not in McpCapability interface
				// localMcpServerUrl: mcpBaseUrl, // localMcpServerUrl is not in McpCapability interface
				invocation: {
					// Placeholder or default invocation as McpCapability requires it.
					// The actual invocation is handled by the SDK's client.callTool.
					type: 'sdk_handled_internally'
				} as any // Cast to any to satisfy McpHttpInvocation | any union
			};
			return capability;
		});

		await client.close(); // Use close() instead of disconnect()

		return {
			capabilities,
			serverInfo,
			messagePath // This path is relative to the server's base URL
		};
	} catch (error: any) {
		console.error(
			`MCP SDK initialization failed for ${mcpSseEndpointUrl}: ${error.message}`,
			error
		);
		await client.close(); // Ensure client is disconnected on error
		throw new Error(
			`MCP SDK initialization failed for ${mcpSseEndpointUrl}: ${error.message}`
		);
	}
}

/**
 * Executes a specific capability of a local client tool server using the MCP SDK.
 * @param params - The parameters required by the capability.
 * @param capabilityId - The ID of the capability/tool to execute.
 * @param mcpBaseUrl - The base URL of the MCP server (e.g., http://localhost:8000).
 *                     The SSE endpoint would be mcpBaseUrl + /sse (or MCP_DEFAULT_PATH)
 * @returns A promise that resolves to the result of the tool execution.
 * @throws Error if execution fails.
 */
export async function executeLocalClientTool(
	params: any,
	capabilityId: string, // Changed from capabilityInvocationDetails
	mcpBaseUrl: string
	// messagePath is no longer needed if client.callTool handles it
): Promise<any> {
	const mcpSseEndpointUrl = `${mcpBaseUrl}${MCP_DEFAULT_PATH}`;
	console.log(
		`Executing tool '${capabilityId}' via SDK on server ${mcpSseEndpointUrl} with params:`,
		params
	);

	const transport = new SSEClientTransport(new URL(mcpSseEndpointUrl));
	// Added name and version to Client constructor
	const client = new Client({ name: 'OpenWebUI-LocalClient', version: '0.0.1' });

	try {
		await client.connect(transport);
		// The capabilityId should be the tool.id from the SDK's perspective
		const result = await client.callTool({ name: capabilityId, arguments: params });
		await client.close(); // Use close() instead of disconnect()
		return result;
	} catch (error: any) {
		console.error(
			`Error executing MCP tool '${capabilityId}' on ${mcpSseEndpointUrl} with SDK: ${error.message}`,
			error
		);
		await client.close(); // Use close() instead of disconnect()
		// Ensure the error is re-thrown to be caught by the caller
		throw new Error(
			`MCP SDK tool execution failed for '${capabilityId}': ${error.message}`
		);
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
		const mcpSseEndpointUrl = `http://localhost:${port}${
			mcpSsePath.startsWith('/') ? mcpSsePath : '/' + mcpSsePath
		}`;
		try {
			// initializeAndGetCapabilities now uses the SDK
			const result: McpSseInitializeResult = await initializeAndGetCapabilities(mcpSseEndpointUrl);

			// The McpSseInitializeResult structure should remain compatible
			// if error field is part of it for non-SDK errors, handle SDK errors by catching
			// No 'result.error' field from SDK-based init, errors are thrown.

			discoveredServers.push({
				url: mcpSseEndpointUrl, // This is the SSE endpoint URL
				serverInfo: result.serverInfo,
				capabilities: result.capabilities
				// messagePath is part of McpSseInitializeResult but not directly DiscoveredServer
			});
			return mcpSseEndpointUrl;
		} catch (error) {
			if (error instanceof Error) {
				console.log(
					`SDK Discovery/Initialization via SSE failed for ${mcpSseEndpointUrl}: ${error.message}`
				);
			} else {
				console.log(
					`SDK Discovery/Initialization via SSE failed for ${mcpSseEndpointUrl} with an unknown error.`
				);
			}
			return null;
		}
	});

	// Wait for all discovery attempts to settle
	await Promise.allSettled(discoveryPromises);

	return discoveredServers;
}
