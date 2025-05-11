import { WEBUI_API_BASE_URL } from '$lib/constants';
import { getAuthHeader } from '$lib/utils/auth';
import { executeLocalClientTool } from '$lib/utils/localClientToolExecutor';

/**
 * Executes a tool with the given parameters.
 * If the tool is a local client tool, it will be executed directly from the frontend.
 * Otherwise, it will be executed through the backend.
 * 
 * @param chatId - The ID of the chat
 * @param toolId - The ID of the tool to execute
 * @param params - The parameters to pass to the tool
 * @param messageId - The ID of the message
 * @param modelId - The ID of the model
 * @param isLocalClientCall - Whether the tool is a local client tool
 * @param localMcpServerUrl - The URL of the local MCP server (required for local client tools)
 * @param capability - The capability details (required for local client tools)
 * @returns A promise that resolves to the result of the tool execution
 */
export async function executeTool(
	chatId: string,
	toolId: string,
	params: Record<string, any>,
	messageId: string,
	modelId: string,
	isLocalClientCall: boolean = false,
	localMcpServerUrl?: string,
	capability?: any
) {
	// If this is a local client call, execute it directly from the frontend
	if (isLocalClientCall && localMcpServerUrl && capability) {
		try {
			// Extract the capability ID from the tool ID (format: mcpEndpointUrl#capabilityId)
			const capabilityId = toolId.split('#')[1];
			
			// Find the specific capability invocation details
			const invocation = capability.invocation;
			
			if (!invocation || invocation.type !== 'http') {
				throw new Error('Invalid capability invocation details');
			}
			
			// Execute the local client tool
			const result = await executeLocalClientTool(params, invocation, localMcpServerUrl);
			
			// Return the result in a format similar to the backend response
			return {
				result: result,
				status: 'success'
			};
		} catch (error) {
			console.error('Error executing local client tool:', error);
			
			// Provide more specific error messages based on the error type
			let errorMessage = 'Failed to execute local client tool';
			
			if (error instanceof Error) {
				const errorText = error.message || '';
				
				// Check for specific error types
				if (errorText.includes('NetworkError') || errorText.includes('Failed to fetch')) {
					errorMessage = 'Cannot connect to local server. Please ensure your local MCP server is running.';
				} else if (errorText.includes('CORS')) {
					errorMessage = 'Local server CORS issue: Please check your local server CORS settings to allow requests from this origin.';
				} else if (errorText.includes('MCP Initialize failed') || errorText.includes('Invalid MCP')) {
					errorMessage = 'MCP initialization failed or invalid capability list. Please check your local MCP server implementation.';
				} else if (errorText.includes('Timeout')) {
					errorMessage = 'Connection to local server timed out. Please check if your local MCP server is responsive.';
				} else if (error.message) {
					// Use the original error message if available
					errorMessage = error.message;
				}
			}
			
			throw new Error(errorMessage);
		}
	} else {
		// Use the existing backend-mediated tool call mechanism
		try {
			const response = await fetch(`${WEBUI_API_BASE_URL}/chats/${chatId}/tools/${toolId}/execute`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					...getAuthHeader()
				},
				body: JSON.stringify({
					params,
					message_id: messageId,
					model_id: modelId
				})
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to execute tool');
			}

			return await response.json();
		} catch (error) {
			console.error('Error executing backend tool:', error);
			throw error;
		}
	}
}
