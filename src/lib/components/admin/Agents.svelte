<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ADMIN_PATH } from '$lib/constants';
	import { agents, getAgents, deleteAgent } from '$lib/apis/agents';

	import Fa from 'svelte-fa';
	import { faTrash, faEdit } from '@fortawesome/free-solid-svg-icons';

	onMount(async () => {
		await getAgents(localStorage.token);
	});

	const handleDelete = async (agentId: string) => {
		if (confirm('Are you sure you want to delete this agent?')) {
			await deleteAgent(localStorage.token, agentId);
		}
	};
</script>

<div class="container mx-auto p-4">
	<table class="table w-full">
		<thead>
			<tr>
				<th>Name</th>
				<th>ID</th>
				<th>Type</th>
				<th>Created By</th>
				<th>Actions</th>
			</tr>
		</thead>
		<tbody>
			{#each $agents as agent}
				<tr>
					<td>{agent.name}</td>
					<td>{agent.id}</td>
					<td>{agent.agent_type}</td>
					<td>{agent.user?.name ?? 'N/A'}</td>
					<td>
						<a href="{ADMIN_PATH}/agents/edit/{agent.id}" class="btn btn-ghost">
							<Fa icon={faEdit} />
						</a>
						<button class="btn btn-ghost" on:click={() => handleDelete(agent.id)}>
							<Fa icon={faTrash} />
						</button>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
