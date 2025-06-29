<script lang="ts">
	import { page } from '$app/stores';
	import AgentEditor from '$lib/components/admin/Agents/AgentEditor.svelte';

	const agentId: string = $page.params.id;
</script>

<div class="text-2xl font-bold">Edit Agent: {agentId}</div>

<AgentEditor {agentId} />
