<script lang="ts">
	// Import the correct utilities
	import i18n from '$lib/i18n';
	import { localMcpTools } from '$lib/stores';
	import { executeTool } from '$lib/apis/tools';

	export let chatId: string;
	export let messageId: string;
	export let modelId: string;
	export let toolCall: any;
	export let onExecute: (result: any) => void;
	export let onError: (error: any) => void;

	let executing = false;
	let isLocalTool = false;

	// Subscribe to the localMcpTools store to access local MCP server configurations
	$: localMcpToolsMap = $localMcpTools.reduce((acc: Record<string, any>, server) => {
		if (server.enabled && server.discoveredCapabilities) {
			server.discoveredCapabilities.forEach(capability => {
				const toolId = `${server.mcpEndpointUrl}#${capability.id}`;
				acc[toolId] = {
					serverUrl: server.mcpEndpointUrl,
					capability
				};
			});
		}
		return acc;
	}, {} as Record<string, any>);

	// Check if this is a local tool
	$: isLocalTool = toolCall.id && toolCall.id.includes('#');
	$: localToolInfo = isLocalTool ? localMcpToolsMap[toolCall.id] : null;

	async function execute() {
		try {
			executing = true;
			
			const result = await executeTool(
				chatId,
				toolCall.id,
				toolCall.function.arguments ? JSON.parse(toolCall.function.arguments) : {},
				messageId,
				modelId,
				isLocalTool,
				localToolInfo?.serverUrl,
				localToolInfo?.capability
			);
			onExecute(result);
		} catch (error) {
			console.error('Tool execution error:', error);
			onError(error);
		} finally {
			executing = false;
		}
	}
</script>

<div class="border rounded-md p-4 bg-muted/30">
	<div class="flex items-center justify-between">
		<div class="font-medium">
			{toolCall.function.name}
			{#if isLocalTool}
				<span class="ml-2 bg-primary/10 text-primary px-1 py-0.5 rounded text-xs">
					Local
				</span>
			{/if}
		</div>
		<button
			class="px-3 py-1 text-sm border rounded bg-background hover:bg-accent flex items-center gap-2"
			on:click={execute}
			disabled={executing}
		>
			{#if executing}
				<span class="inline-block animate-spin">⟳</span>
				<span>Executing</span>
			{:else}
				<span>Execute</span>
			{/if}
		</button>
	</div>
	<div class="mt-2 text-sm text-muted-foreground">
		<pre class="whitespace-pre-wrap">{toolCall.function.arguments}</pre>
	</div>
	{#if isLocalTool && localToolInfo}
		<div class="mt-2 text-xs text-muted-foreground">
			<div>Server: {localToolInfo.serverUrl}</div>
			<div>Capability: {localToolInfo.capability.id}</div>
		</div>
	{/if}
</div>
