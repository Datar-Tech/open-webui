<script>
	import { page } from '$app/stores';
	import { ADMIN_PATH } from '$lib/constants';

	import Fa from 'svelte-fa';
	import { faPlus } from '@fortawesome/free-solid-svg-icons';

	import Agents from '$lib/components/admin/Agents.svelte';
</script>

<div class="flex justify-between items-center">
	<div class="text-2xl font-bold">Agents</div>
	<a href="{ADMIN_PATH}/agents/create" class="btn btn-primary">
		<Fa icon={faPlus} class="mr-2" />
		Create Agent
	</a>
</div>

<Agents />