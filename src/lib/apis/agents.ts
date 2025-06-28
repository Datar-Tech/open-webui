import { writable } from 'svelte/store';
import { WEBUI_API_BASE_URL } from '$lib/constants';
import type { Agent } from '$lib/types/agents';

export const agents = writable<Agent[]>([]);

export const getAgents = async (token: string = '') => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/agents`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (response.ok) {
		const data = await response.json();
		agents.set(data);
		return data;
	} else {
		agents.set([]);
		return [];
	}
};

export const getAgent = async (id: string) => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/agents/id/${id}`);
	return await response.json();
};

export const createAgent = async (token: string, agent: any) => {
	await fetch(`${WEBUI_API_BASE_URL}/agents/create`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify(agent)
	});
	await getAgents(token);
};

export const updateAgent = async (token: string, id: string, agent: any) => {
	await fetch(`${WEBUI_API_BASE_URL}/agents/id/${id}/update`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify(agent)
	});
	await getAgents(token);
};

export const deleteAgent = async (token: string, id: string) => {
	await fetch(`${WEBUI_API_BASE_URL}/agents/id/${id}/delete`, {
		method: 'DELETE',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});
	await getAgents(token);
};
