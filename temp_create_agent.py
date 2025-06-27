from open_webui.internal.db import db
from open_webui.models.agents import Agent

with db:
    Agent.create(
        id='custom_python_example',
        user_id='admin',
        agent_type='custom_python',
        name='Custom Python Example',
        definition='print("Hello from a custom Python agent!")'
    )