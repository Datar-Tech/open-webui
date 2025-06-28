from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from open_webui.models.agents import Agent, AgentForm, AgentModel, AgentResponse, AgentUserResponse
from open_webui.models.users import Users
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.misc import has_access
import logging

log = logging.getLogger(__name__)

router = APIRouter()

@router.get("", response_model=List[AgentUserResponse])
async def get_agents(request: Request, user=Depends(get_verified_user)):
    agents = []
    for agent_obj in Agent.get_all():
        user_obj = Users.get_user_by_id(agent_obj.user_id)
        if agent_obj.user_id == user.id or has_access(
            user.id, "read", agent_obj.access_control
        ):
            agents.append(
                AgentUserResponse(
                    **AgentModel.model_validate(agent_obj.__data__).model_dump(),
                    user=user_obj.model_dump() if user_obj else None,
                )
            )
    return agents

@router.post("/create", response_model=AgentResponse)
async def create_agent(request: Request, form_data: AgentForm, user=Depends(get_admin_user)):
    if Agent.get_by_id(form_data.id):
        raise HTTPException(status_code=400, detail="Agent with this ID already exists")

    agent_obj = Agent(
        id=form_data.id,
        user_id=user.id,
        agent_type=form_data.agent_type,
        definition=form_data.definition,
        valves=form_data.valves,
        name=form_data.name,
        meta=form_data.meta.model_dump() if form_data.meta else None,
        access_control=form_data.access_control,
    )
    agent_obj.save()
    return AgentResponse.model_validate(agent_obj.__data__)

@router.get("/id/{agent_id}", response_model=AgentModel)
async def get_agent_by_id(request: Request, agent_id: str, user=Depends(get_verified_user)):
    agent_obj = Agent.get_by_id(agent_id)
    if not agent_obj:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if agent_obj.user_id != user.id and not has_access(
        user.id, "read", agent_obj.access_control
    ):
        raise HTTPException(status_code=403, detail="Not authorized to access this agent")

    return AgentModel.model_validate(agent_obj.__data__)

@router.post("/id/{agent_id}/update", response_model=AgentResponse)
async def update_agent(request: Request, agent_id: str, form_data: AgentForm, user=Depends(get_admin_user)):
    agent_obj = Agent.get_by_id(agent_id)
    if not agent_obj:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent_obj.user_id != user.id and not has_access(user.id, "write", agent_obj.access_control):
        raise HTTPException(status_code=403, detail="Not authorized to update this agent")

    agent_obj.agent_type = form_data.agent_type
    agent_obj.definition = form_data.definition
    agent_obj.valves = form_data.valves
    agent_obj.name = form_data.name
    agent_obj.meta = form_data.meta.model_dump() if form_data.meta else None
    agent_obj.access_control = form_data.access_control
    agent_obj.save()
    return AgentResponse.model_validate(agent_obj.__data__)

@router.delete("/id/{agent_id}/delete")
async def delete_agent(request: Request, agent_id: str, user=Depends(get_admin_user)):
    agent_obj = Agent.get_by_id(agent_id)
    if not agent_obj:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent_obj.user_id != user.id and not has_access(user.id, "write", agent_obj.access_control):
        raise HTTPException(status_code=403, detail="Not authorized to delete this agent")

    agent_obj.delete()
    return {"message": "Agent deleted successfully"}
