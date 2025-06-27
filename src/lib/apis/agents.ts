import { writable } from 'svelte/store';
import { WEBUI_API_BASE_URL } from '$lib/constants';

export const agents = writable([]);

export const getAgents = async () => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/agents`);
	const data = await response.json();
	agents.set(data);
};

export const getAgent = async (id) => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/agents/id/${id}`);
	return await response.json();
};

export const createAgent = async (agent) => {
	await fetch(`${WEBUI_API_BASE_URL}/agents/create`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(agent)
	});
	await getAgents();
};

export const updateAgent = async (id, agent) => {
	await fetch(`${WEBUI_API_BASE_URL}/agents/id/${id}/update`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(agent)
	});
	await getAgents();
};

export const deleteAgent = async (id) => {
	await fetch(`${WEBUI_API_BASE_URL}/agents/id/${id}/delete`, {
		method: 'DELETE'
	});
	await getAgents();
};
