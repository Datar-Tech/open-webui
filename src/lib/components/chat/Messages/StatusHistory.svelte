<script lang="ts">
    import { getContext } from 'svelte';
    import type { Writable } from 'svelte/store';
    import type { i18n as i18nType } from 'i18next';

    import Spinner from '$lib/components/common/Spinner.svelte';
    import WebSearchResults from './ResponseMessage/WebSearchResults.svelte';
    import Collapsible from '$lib/components/common/Collapsible.svelte';

    const i18n = getContext<Writable<i18nType>>('i18n');

    export let statusHistory: {
        done: boolean;
        action: string;
        description: string;
        urls?: string[];
        query?: string;
        hidden?: boolean;
    }[];

    export let messageId: string;

    let open: boolean = false;
</script>

{#if statusHistory.length > 0}
    <Collapsible id={`status-collapsible-${messageId}`} bind:open class="w-full">
        <div slot="header" class="flex items-center gap-2 py-0.5">
            {#if statusHistory.at(-1)?.done === false}
                <Spinner className="size-4" />
            {/if}
            <div class="text-gray-500 dark:text-gray-500 text-base line-clamp-1 text-wrap">
                {$i18n.t(statusHistory.at(-1)?.description ?? '')}
            </div>
        </div>
        <div slot="content" class="pl-6">
            {#each statusHistory as status, idx}
                {#if !status.hidden}
                    <div class="status-description flex items-center gap-2 py-0.5">
                        {#if status.done === false}
                            <Spinner className="size-4" />
                        {/if}

                        {#if status.action === 'web_search' && status.urls}
                            <WebSearchResults {status}>
                                <div class="flex flex-col justify-center -space-y-0.5">
                                    <div
                                        class="{status.done === false
                                            ? 'shimmer'
                                            : ''} text-base line-clamp-1 text-wrap"
                                    >
                                        {#if status.description.includes('{{count}}')}
                                            {$i18n.t(status.description, {
                                                count: status.urls.length
                                            })}
                                        {:else if status.description === 'No search query generated'}
                                            {$i18n.t('No search query generated')}
                                        {:else if status.description === 'Generating search query'}
                                            {$i18n.t('Generating search query')}
                                        {:else}
                                            {status.description}
                                        {/if}
                                    </div>
                                </div>
                            </WebSearchResults>
                        {:else if status.action === 'knowledge_search'}
                            <div class="flex flex-col justify-center -space-y-0.5">
                                <div
                                    class="{status.done === false
                                        ? 'shimmer'
                                        : ''} text-gray-500 dark:text-gray-500 text-base line-clamp-1 text-wrap"
                                >
                                    {$i18n.t(`Searching Knowledge for "{{searchQuery}}"`, {
                                        searchQuery: status.query
                                    })}
                                </div>
                            </div>
                        {:else}
                            <div class="flex flex-col justify-center -space-y-0.5">
                                <div
                                    class="{status.done === false
                                        ? 'shimmer'
                                        : ''} text-gray-500 dark:text-gray-500 text-base line-clamp-1 text-wrap"
                                >
                                    {#if status.description.includes('{{searchQuery}}')}
                                        {$i18n.t(status.description, {
                                            searchQuery: status.query
                                        })}
                                    {:else if status.description === 'No search query generated'}
                                        {$i18n.t('No search query generated')}
                                    {:else if status.description === 'Generating search query'}
                                        {$i18n.t('Generating search query')}
                                    {:else}
                                        {status.description}
                                    {/if}
                                </div>
                            </div>
                        {/if}
                    </div>
                {/if}
            {/each}
        </div>
    </Collapsible>
{/if}
