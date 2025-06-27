import requests
import json
import time

# Assuming the server is running on localhost:8080
BASE_URL = "http://localhost:8080"

admin_user = {
    "name": "Admin User",
    "email": "admin@example.com",
    "password": "password"
}

# Retry mechanism for server connection
max_retries = 10
retry_delay = 5 # seconds

for i in range(max_retries):
    try:
        # Try to sign up the admin user (it might already exist from previous runs)
        # We ignore the status code as it might return 400 if user already exists
        response = requests.post(f"{BASE_URL}/api/v1/auths/signup", json=admin_user, timeout=5)
        if response.status_code == 400 and "User already exists" in response.text:
            print("User already exists, proceeding with login.")
        elif response.status_code != 200:
            print(f"Signup failed with status code {response.status_code}: {response.text}")
            time.sleep(retry_delay)
            continue
        
        # Log in to get the token
        response = requests.post(f"{BASE_URL}/api/v1/auths/signin", json={
            "email": admin_user["email"],
            "password": admin_user["password"]
        }, timeout=5)

        if response.status_code == 200:
            token = response.json()["token"]
            print(f"Successfully obtained token: {token[:10]}...")

            # Create the custom_python agent
            agent_data = {
                "id": "custom_python_example",
                "user_id": "admin", # This will be overwritten by the backend based on the token
                "agent_type": "custom_python",
                "name": "Custom Python Example",
                "definition": "print('Hello from a custom Python agent!')",
                "meta": {"description": "A simple test agent."}, 
                "valves": {}, 
                "access_control": {"public": True}
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            create_agent_response = requests.post(f"{BASE_URL}/api/v1/agents/create", headers=headers, data=json.dumps(agent_data), timeout=5)

            if create_agent_response.status_code == 200:
                print("Custom Python agent created successfully!")
                exit() # Exit on success
            else:
                print(f"Failed to create agent: {create_agent_response.status_code} - {create_agent_response.text}")
                time.sleep(retry_delay)
                continue
        else:
            print(f"Failed to sign in: {response.status_code} - {response.text}")
            time.sleep(retry_delay)
            continue

    except requests.exceptions.ConnectionError as e:
        print(f"Attempt {i+1}/{max_retries}: Server not reachable ({e}). Retrying in {retry_delay} seconds...")
        time.sleep(retry_delay)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        time.sleep(retry_delay)

print("Failed to connect to the server after multiple retries. Please check if Open WebUI is running correctly.")