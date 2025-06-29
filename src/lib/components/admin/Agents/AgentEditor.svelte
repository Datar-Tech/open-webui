<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ADMIN_PATH } from '$lib/constants';
	import { createAgent, getAgent, updateAgent } from '$lib/apis/agents';

	export let agentId: string | null = null;

	let agent = {
		id: '',
		name: '',
		agent_type: 'custom_python',
		definition: '',
		meta: {},
		valves: {},
		access_control: {}
	};

	onMount(async () => {
		if (agentId) {
			agent = await getAgent(localStorage.token, agentId);
		}
	});

	const handleSubmit = async () => {
		if (agentId) {
			await updateAgent(localStorage.token, agentId, agent);
		} else {
			await createAgent(localStorage.token, agent);
		}
		goto(`${ADMIN_PATH}/agents`);
	};
</script>

<form on:submit|preventDefault={handleSubmit}>
	<div class="mb-4">
		<label for="name" class="block text-sm font-medium">Name</label>
		<input type="text" id="name" bind:value={agent.name} class="input input-bordered w-full" />
	</div>

	<div class="mb-4">
		<label for="id" class="block text-sm font-medium">ID</label>
		<input type="text" id="id" bind:value={agent.id} class="input input-bordered w-full" disabled={agentId !== null} />
	</div>

	<div class="mb-4">
		<label for="agent_type" class="block text-sm font-medium">Agent Type</label>
		<select id="agent_type" bind:value={agent.agent_type} class="select select-bordered w-full">
			<option value="custom_python">Custom Python</option>
			<option value="llamaindex_workflow">LlamaIndex Workflow</option>
		</select>
	</div>

	<div class="mb-4">
		<label for="definition" class="block text-sm font-medium">Definition</label>
		{#if agent.agent_type === 'custom_python'}
			<textarea id="definition" bind:value={agent.definition} class="textarea textarea-bordered w-full" rows="10"></textarea>
		{:else if agent.agent_type === 'llamaindex_workflow'}
			<textarea id="definition" bind:value={agent.definition} class="textarea textarea-bordered w-full" rows="10"></textarea>
		{/if}
	</div>

	<button type="submit" class="btn btn-primary">Save</button>
</form>
