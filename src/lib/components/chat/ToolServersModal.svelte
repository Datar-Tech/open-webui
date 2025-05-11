<script lang="ts">
import { getContext, onMount } from 'svelte';
import { derived, type Writable } from 'svelte/store'; // Correct import for derived, added Writable
import type { i18n as I18nInstanceType } from 'i18next'; // For typing the store's content
import { models, config, toolServers, tools, localMcpTools } from '$lib/stores';
import type { Tool, LocalClientToolServerConfig, McpCapability } from '$lib/types';

import { toast } from 'svelte-sonner';
import { deleteSharedChatById, getChatById, shareChatById } from '$lib/apis/chats';
	import { copyToClipboard } from '$lib/utils';

	import Modal from '../common/Modal.svelte';
	import Link from '../icons/Link.svelte';
	import Collapsible from '../common/Collapsible.svelte';

export let show = false;
export let selectedToolIds: string[] = []; // Explicitly typed

const i18nStore = getContext<Writable<I18nInstanceType>>('i18n'); // Explicitly type the store

$: if (show) {
  console.log('All Available Tools in Modal (when shown):', $allAvailableTools);
}

// Combine backend tools and local MCP tools into a single list
const allAvailableTools = derived<
  [typeof tools, typeof localMcpTools], // Specify store types
  Tool[] // Specify return type of the derived store
>(
  [tools, localMcpTools],
  ([$tools_val, $localMcpTools_val]) => { // Typed parameters
    const backendTools: Tool[] = ($tools_val ?? []).map((tool: Tool) => ({ ...tool, isLocalClientCall: false })); // Typed map parameter

    const localTools: Tool[] = [];
    ($localMcpTools_val ?? []).forEach((serverConfig: LocalClientToolServerConfig) => {
      if (serverConfig.enabled && serverConfig.discoveredCapabilities) {
        serverConfig.discoveredCapabilities.forEach((cap: McpCapability) => {
          localTools.push({
            id: `${serverConfig.mcpEndpointUrl}#${cap.id}`, // Unique ID for local capability
            name: cap.name || cap.id,
            meta: { description: cap.description },
            isLocalClientCall: true,
            localMcpServerUrl: serverConfig.mcpEndpointUrl,
            capabilities: [cap] // Store the specific capability
          });
        });
      }
    });
    return [...backendTools, ...localTools];
  }
);

function toggleToolSelection(toolId: string) {
  const index = selectedToolIds.indexOf(toolId);
  if (index === -1) {
    selectedToolIds = [...selectedToolIds, toolId];
  } else {
    selectedToolIds = selectedToolIds.filter((id) => id !== toolId);
  }
  console.log('[Debug ToolServersModal] toggleToolSelection - selectedToolIds now:', JSON.parse(JSON.stringify(selectedToolIds)));
  // Consider dispatching an event if parent needs to know about selection change immediately
  // dispatch('selectionChange', { selectedToolIds });
}

</script>

<Modal bind:show size="md">
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-0.5">
<div class=" text-lg font-medium self-center">{$i18nStore.t('Available Tools')}</div>
			<button
				class="self-center"
				on:click={() => {
					show = false;
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
</button>
</div>

<!-- Unified Tools List -->
<div class=" flex justify-between dark:text-gray-300 px-5 pt-2 pb-1">
  <div class=" text-base font-medium self-center">{$i18nStore.t('Select Tools')}</div>
</div>

<div class="px-5 pb-3 w-full flex flex-col justify-center max-h-96 overflow-y-auto">
  {#if $allAvailableTools.length > 0}
    <div class=" text-sm dark:text-gray-300 mb-1">
      {#each $allAvailableTools as tool (tool.id)}
        <div class="flex items-center mb-1 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
          <input
            type="checkbox"
            id={`tool-checkbox-${tool.id}`}
            class="mr-3 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            checked={selectedToolIds.includes(tool.id)}
            on:change={() => toggleToolSelection(tool.id)}
          />
          <label for={`tool-checkbox-${tool.id}`} class="flex-1 cursor-pointer">
            <Collapsible buttonClassName="w-full -ml-2" chevron={false}>
              <div class="flex items-center">
                <div class="text-sm font-medium dark:text-gray-100 text-gray-800">
                  {tool.name}
                </div>
                {#if tool.isLocalClientCall}
                  <span class="ml-2 px-1.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full">{$i18nStore.t('Local')}</span>
                {/if}
              </div>
              {#if tool.meta?.description}
                <div class="text-xs text-gray-500 mt-0.5">
                  {tool.meta.description}
                </div>
              {/if}
              <div slot="content" class="mt-1 text-xs p-2 bg-gray-50 dark:bg-gray-750 rounded">
                <strong>ID:</strong> {tool.id}<br/>
                {#if tool.isLocalClientCall}
                  <strong>Server:</strong> {tool.localMcpServerUrl}<br/>
                  <strong>Capability ID:</strong> {tool.capabilities && tool.capabilities[0] ? tool.capabilities[0].id : 'N/A'}
                {/if}
                <!-- Raw tool data for debugging if needed -->
                <!-- <pre>{JSON.stringify(tool, null, 2)}</pre> -->
              </div>
            </Collapsible>
          </label>
        </div>
      {/each}
    </div>
  {:else}
    <p class="text-sm text-gray-500 dark:text-gray-400 py-3 text-center">{$i18nStore.t('No tools available.')}</p>
  {/if}
</div>


<!-- Existing Tool Servers (OpenAPI) informational display -->
{#if $toolServers.length > 0}
<div class=" flex justify-between dark:text-gray-300 px-5 pt-3 pb-0.5 border-t dark:border-gray-700">
<div class=" text-base font-medium self-center">{$i18nStore.t('Tool Servers')}</div>
</div>

<div class="px-5 pb-5 w-full flex flex-col justify-center">
<div class=" text-xs text-gray-600 dark:text-gray-300 mb-2">
{$i18nStore.t('Open WebUI can use tools provided by any OpenAPI server.')} <br /><a
class="underline"
href="https://github.com/open-webui/openapi-servers"
target="_blank">{$i18nStore.t('Learn more about OpenAPI tool servers.')}</a
>
</div>
				<div class=" text-sm dark:text-gray-300 mb-1">
					{#each $toolServers as toolServer}
						<Collapsible buttonClassName="w-full" chevron>
							<div>
								<div class="text-sm font-medium dark:text-gray-100 text-gray-800">
									{toolServer?.openapi?.info?.title} - v{toolServer?.openapi?.info?.version}
								</div>

								<div class="text-xs text-gray-500">
									{toolServer?.openapi?.info?.description}
								</div>

								<div class="text-xs text-gray-500">
									{toolServer?.url}
								</div>
							</div>

							<div slot="content">
								{#each toolServer?.specs ?? [] as tool_spec}
									<div class="my-1">
										<div class="font-medium text-gray-800 dark:text-gray-100">
											{tool_spec?.name}
										</div>

										<div>
											{tool_spec?.description}
										</div>
									</div>
								{/each}
							</div>
						</Collapsible>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</Modal>
