/**
 * Returns the authentication header for API requests.
 * This function retrieves the authentication token from localStorage and returns it in the format expected by the API.
 * @returns An object containing the authentication header, or an empty object if no token is found.
 */
export function getAuthHeader() {
    if (typeof window !== 'undefined') {
        const token = localStorage.getItem('open-webui_auth_token');
        if (token) {
            return { Authorization: `Bearer ${token}` };
        }
    }
    return {};
}
