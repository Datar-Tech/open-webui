<script lang="ts">
  import { getContext } from 'svelte';
  import ToolCall from '../../ToolCall.svelte';
  
  const i18n = getContext('i18n');
  
  export let chatId: string;
  export let messageId: string;
  export let modelId: string;
  export let toolCalls: any[] = [];
  
  let toolCallResults: any[] = [];
  let toolCallErrors: any[] = [];
</script>

{#if toolCalls && toolCalls.length > 0}
  <div class="mt-2 space-y-2">
    {#each toolCalls as toolCall, i}
      <ToolCall
        {chatId}
        {messageId}
        {modelId}
        {toolCall}
        onExecute={(result) => {
          toolCallResults[i] = result;
          toolCallResults = toolCallResults;
        }}
        onError={(error) => {
          toolCallErrors[i] = error;
          toolCallErrors = toolCallErrors;
        }}
      />
    {/each}
  </div>
{/if}

{#if toolCallResults.length > 0}
  <div class="mt-2 space-y-2">
    {#each toolCallResults as result, i}
      <div class="border rounded-md p-4 bg-muted/30">
        <div class="font-medium">
          Tool Result
          {#if toolCalls && toolCalls[i] && toolCalls[i].id && toolCalls[i].id.includes('#')}
            <span class="ml-2 bg-primary/10 text-primary px-1 py-0.5 rounded text-xs">
              Local
            </span>
          {/if}
        </div>
        <div class="mt-2 text-sm">
          {#if typeof result.result === 'object'}
            <pre class="whitespace-pre-wrap">{JSON.stringify(result.result, null, 2)}</pre>
          {:else}
            <pre class="whitespace-pre-wrap">{result.result}</pre>
          {/if}
        </div>
      </div>
    {/each}
  </div>
{/if}

{#if toolCallErrors.length > 0}
  <div class="mt-2 space-y-2">
    {#each toolCallErrors as error, i}
      <div class="border border-destructive rounded-md p-4 bg-destructive/10">
        <div class="font-medium text-destructive">
          Tool Error
          {#if toolCalls && toolCalls[i] && toolCalls[i].id && toolCalls[i].id.includes('#')}
            <span class="ml-2 bg-destructive/20 text-destructive px-1 py-0.5 rounded text-xs">
              Local
            </span>
          {/if}
        </div>
        <div class="mt-2 text-sm text-destructive">
          {error.message}
        </div>
        {#if toolCalls && toolCalls[i] && toolCalls[i].id && toolCalls[i].id.includes('#')}
          <div class="mt-2 text-xs text-destructive/80">
            If this is a CORS issue, ensure your local MCP server has the correct CORS headers configured.
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
