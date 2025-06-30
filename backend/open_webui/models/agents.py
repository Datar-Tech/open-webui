from typing import Optional, Any
from pydantic import BaseModel, Field
import time

from open_webui.internal.db import db
from open_webui.models.users import Users
from open_webui.utils.misc import has_access


# Agents DB Schema
from peewee import Model, CharField, TextField, IntegerField, SqliteDatabase, PostgresqlDatabase, MySQLDatabase
from playhouse.sqlite_ext import JSONField as SQLiteJSONField # For SQLite
from playhouse.postgres_ext import JSONField as PostgresJSONField # For PostgreSQL
from playhouse.mysql_ext import JSONField as MySQLJSONField # For MySQL
import time

from open_webui.internal.db import db
from open_webui.models.users import Users
from open_webui.utils.misc import has_access

# Determine which JSONField to use based on the database type
if isinstance(db, SqliteDatabase):
    JSONField = SQLiteJSONField
elif isinstance(db, PostgresqlDatabase):
    JSONField = PostgresJSONField
elif isinstance(db, MySQLDatabase):
    JSONField = MySQLJSONField
else:
    # Fallback for other databases, or raise an error if JSONField is critical
    JSONField = TextField # Or raise NotImplementedError

# Agents DB Schema
class Agent(Model):
    id = CharField(primary_key=True)
    user_id = CharField()
    agent_type = CharField()  # e.g., "custom_python", "llamaindex_workflow"
    definition = JSONField(null=True)  # Python code or workflow definition
    valves = JSONField(null=True)  # Agent-specific configurations
    name = CharField(null=True)
    meta = JSONField(null=True)  # General metadata (description, icon, etc.)
    access_control = JSONField(null=True)  # Permissions for this agent
    created_at = IntegerField(default=lambda: int(time.time()))
    updated_at = IntegerField(default=lambda: int(time.time()))

    class Meta:
        database = db

    @classmethod
    def get_by_id(cls, id: str):
        return cls.get_or_none(cls.id == id)

    def to_dict(self):
        return self.__data__

    @classmethod
    def get_all(cls):
        return list(cls.select())

    @classmethod
    def get_user_valves_by_id_and_user_id(cls, agent_id: str, user_id: str) -> Optional[dict]:
        """
        Retrieves user-specific valves for a given agent from user settings.
        Mimics FunctionsTable.get_user_valves_by_id_and_user_id.
        """
        try:
            user = Users.get_user_by_id(user_id)
            user_settings = user.settings.model_dump() if user.settings else {}

            # Check if user has "agents" and "valves" settings
            if "agents" not in user_settings:
                user_settings["agents"] = {}
            if "valves" not in user_settings["agents"]:
                user_settings["agents"]["valves"] = {}

            return user_settings["agents"]["valves"].get(agent_id, {})
        except Exception as e:
            # log.exception( # 這裡不應該有 log.exception，因為 FunctionsTable 中也沒有
            #     f"Error getting user agent valves by id {agent_id} and user id {user_id}: {e}"
            # )
            return None # 返回 None 或空字典，根據 Functions 的行為

    @classmethod
    def update_user_valves_by_id_and_user_id(cls, agent_id: str, user_id: str, valves: dict) -> Optional[dict]:
        """
        Updates user-specific valves for a given agent in user settings.
        Mimics FunctionsTable.update_user_valves_by_id_and_user_id.
        """
        try:
            user = Users.get_user_by_id(user_id)
            user_settings = user.settings.model_dump() if user.settings else {}

            if "agents" not in user_settings:
                user_settings["agents"] = {}
            if "valves" not in user_settings["agents"]:
                user_settings["agents"]["valves"] = {}

            user_settings["agents"]["valves"][agent_id] = valves

            Users.update_user_by_id(user_id, {"settings": user_settings})

            return user_settings["agents"]["valves"][agent_id]
        except Exception as e:
            # log.exception( # 這裡不應該有 log.exception，因為 FunctionsTable 中也沒有
            #     f"Error updating user agent valves by id {agent_id} and user_id {user_id}: {e}"
            # )
            return None


# Pydantic Models for API
class AgentMeta(BaseModel):
    description: Optional[str] = None
    icon_url: Optional[str] = None
    manifest: Optional[dict] = None  # For future compatibility with external manifests


class AgentModel(BaseModel):
    id: str
    user_id: str
    agent_type: str
    definition: Optional[Any] = None
    valves: Optional[dict] = None
    name: Optional[str] = None
    meta: Optional[AgentMeta] = None
    access_control: Optional[dict] = None
    created_at: int
    updated_at: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "my-first-agent",
                    "user_id": "user-123",
                    "agent_type": "custom_python",
                    "definition": "print('Hello from agent!')",
                    "valves": {"default_llm": "ollama/llama2"},
                    "name": "My First Agent",
                    "meta": {"description": "A simple test agent."},
                    "access_control": {"public": True},
                    "created_at": 1678886400,
                    "updated_at": 1678886400,
                }
            ]
        }
    }


class AgentUserModel(AgentModel):
    user: Optional[dict] = None  # User details for display


class AgentResponse(BaseModel):
    id: str
    agent_type: str
    name: Optional[str] = None
    meta: Optional[AgentMeta] = None
    created_at: int
    updated_at: int


class AgentUserResponse(AgentResponse):
    user: Optional[dict] = None


class AgentForm(BaseModel):
    id: str
    agent_type: str
    definition: Optional[Any] = None
    valves: Optional[dict] = None
    name: Optional[str] = None
    meta: Optional[AgentMeta] = None
    access_control: Optional[dict] = None
