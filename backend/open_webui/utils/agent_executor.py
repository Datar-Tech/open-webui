import sys
import io
import inspect
import json
import asyncio
import logging
import types
import textwrap
import tempfile
import os

from typing import AsyncIterator, Dict, Any, Generator, Iterator
from fastapi import Request, HTTPException, StreamingResponse
from pydantic import BaseModel

from open_webui.models.agents import Agent as AgentModel, Agent # 確保引入 Agent 類本身
from open_webui.utils.openwebui_tool_adapter import OpenWebUIToolAdapter
from open_webui.utils.agent_tools import AgentTools
from open_webui.utils.tools import get_tools # 直接引入 get_tools
from open_webui.utils.misc import openai_chat_chunk_message_template, openai_chat_completion_message_template # 引入兩個模板函數
from open_webui.socket.main import get_event_call, get_event_emitter # 引入 socket 相關函數
from open_webui.utils.plugin import load_agent_module_by_id # 引入新的載入函數

log = logging.getLogger(__name__)

# 確保 LlamaIndex FunctionTool 可用
try:
    from llama_index.core.tools import FunctionTool, BaseTool, ToolOutput
    from llama_index.core.llms import ChatMessage, MessageRole, LLM
    from llama_index.core.response import Response as LlamaIndexResponse
except ImportError:
    log.warning("LlamaIndex not found. LlamaIndex workflow agent will not be able to create LlamaIndex tools.")
    FunctionTool = None
    BaseTool = None
    ToolOutput = None
    LlamaIndexResponse = None

class AgentExecutor:
    def __init__(self, request: Request, agent_obj: AgentModel):
        self.request = request
        self.agent_obj = agent_obj
        self.openwebui_tool_adapter = OpenWebUIToolAdapter(request, request.state.user)
        self.agent_tools = AgentTools(request)

    async def execute(self, user_message: str, chat_history: list, form_data: Dict[str, Any]) -> AsyncIterator[str]: # 添加 form_data
        log.info(f"Executing agent: {self.agent_obj.name} (Type: {self.agent_obj.agent_type})")

        try:
            yield json.dumps({"type": "status", "content": "Agent started..."}) + "\n"

            if self.agent_obj.agent_type == "custom_python":
                async for chunk in self._execute_custom_python_agent(user_message, chat_history):
                    yield chunk
            elif self.agent_obj.agent_type == "llamaindex_workflow":
                async for chunk in self._execute_llamaindex_workflow_agent(user_message, chat_history):
                    yield chunk
            else:
                yield json.dumps({"type": "error", "content": f"Unsupported agent type: {self.agent_obj.agent_type}"}) + "\n"

            yield json.dumps({"type": "status", "content": "Agent finished."}) + "\n"

        except asyncio.CancelledError:
            log.info(f"Agent {self.agent_obj.name} execution cancelled.")
            yield json.dumps({"type": "status", "content": "Agent execution cancelled."}) + "\n"
        except Exception as e:
            log.error(f"Error during agent execution: {e}", exc_info=True)
            yield json.dumps({"type": "error", "content": f"Agent execution failed: {str(e)}"}) + "\n"

    def _process_line(self, form_data: dict, line: Any) -> str:
        if isinstance(line, BaseModel):
            line = line.model_dump_json()
            line = f"data: {line}"
        if isinstance(line, dict):
            line = f"data: {json.dumps(line)}"

        try:
            line = line.decode("utf-8")
        except Exception:
            pass

        if line.startswith("data:"):
            return f"{line}\n\n"
        else:
            line = openai_chat_chunk_message_template(form_data["model"], line)
            return f"data: {json.dumps(line)}\n\n"

    async def _execute_custom_python_agent(self, user_message: str, chat_history: list, form_data: Dict[str, Any]) -> AsyncIterator[str]:
        yield json.dumps({"type": "status", "content": "Running custom Python agent..."}) + "\n"

        agent_code = self.agent_obj.definition
        if not agent_code:
            yield json.dumps({"type": "error", "content": "Agent definition (Python code) is empty."}) + "\n"
            return

        # 1. 模組載入 (使用新的 load_agent_module_by_id)
        try:
            pipe_instance, _, _ = load_agent_module_by_id(self.agent_obj.id, agent_code)
        except Exception as e:
            log.error(f"Error loading custom Python agent module: {e}", exc_info=True)
            yield json.dumps({"type": "error", "content": f"Error loading agent code: {str(e)}"}) + "\n"
            return

        # 2. 準備執行參數 (與 functions.py 相同)
        metadata = form_data.get("metadata", {})
        files = metadata.get("files", [])
        tool_ids = metadata.get("tool_ids", [])
        if tool_ids is None:
            tool_ids = []

        __event_emitter__ = None
        __event_call__ = None
        __task__ = None
        __task_body__ = None

        if metadata:
            if all(k in metadata for k in ("session_id", "chat_id", "message_id")):
                __event_emitter__ = get_event_emitter(metadata)
                __event_call__ = get_event_call(metadata)
            __task__ = metadata.get("task", None)
            __task_body__ = metadata.get("task_body", None)

        extra_params = {
            "__event_emitter__": __event_emitter__,
            "__event_call__": __event_call__,
            "__chat_id__": metadata.get("chat_id", None),
            "__session_id__": metadata.get("session_id", None),
            "__message_id__": metadata.get("message_id", None),
            "__task__": __task__,
            "__task_body__": __task_body__,
            "__files__": files,
            "__user__": {
                "id": self.request.state.user.id,
                "email": self.request.state.user.email,
                "name": self.request.state.user.name,
                "role": self.request.state.user.role,
            },
            "__metadata__": metadata,
            "__request__": self.request,
        }
        extra_params["__tools__"] = get_tools(
            self.request,
            tool_ids,
            self.request.state.user,
            {
                **extra_params,
                "__model__": form_data.get("model_item", {}),
                "__messages__": form_data["messages"],
                "__files__": files,
            },
        )

        pipe_function = getattr(pipe_instance, "pipe", None)
        if not pipe_function:
            yield json.dumps({"type": "error", "content": "Loaded agent module must have an async 'pipe' method."}) + "\n"
            return

        sig = inspect.signature(pipe_function)
        params = {"body": form_data}
        params.update({
            k: v for k, v in extra_params.items() if k in sig.parameters
        })

        # 處理 valves (與 functions.py 相同)
        if hasattr(pipe_instance, "valves") and hasattr(pipe_instance, "Valves"):
            valves_data = self.agent_obj.valves if self.agent_obj.valves else {}
            try:
                pipe_instance.valves = pipe_instance.Valves(**valves_data)
            except Exception as e:
                log.exception(f"Error setting agent valves: {e}")

        # 處理 UserValves (與 functions.py 相同)
        if "__user__" in params and hasattr(pipe_instance, "UserValves"):
            user_valves_data = Agent.get_user_valves_by_id_and_user_id(self.agent_obj.id, params["__user__"]["id"])
            if user_valves_data is None:
                user_valves_data = {}
            try:
                params["__user__"]["valves"] = pipe_instance.UserValves(**user_valves_data)
            except Exception as e:
                log.exception(f"Error setting agent UserValves: {e}")
                params["__user__"]["valves"] = pipe_instance.UserValves()

        # 3. 執行代理的 pipe 函數 (與 functions.py 相同)
        try:
            res = await pipe_function(**params)

            # 4. 錯誤處理和輸出格式 (與 functions.py 相同)
            if form_data.get("stream", False):
                if isinstance(res, StreamingResponse):
                    async for data in res.body_iterator:
                        yield data
                    return
                if isinstance(res, dict):
                    yield f"data: {json.dumps(res)}\n\n"
                    return

                if isinstance(res, str):
                    message = openai_chat_chunk_message_template(form_data["model"], res)
                    yield f"data: {json.dumps(message)}\n\n"

                if isinstance(res, Iterator) or isinstance(res, Generator):
                    for line in res:
                        yield self._process_line(form_data, line)

                if isinstance(res, AsyncGenerator):
                    async for line in res:
                        yield self._process_line(form_data, line)

                if isinstance(res, str) or isinstance(res, Iterator) or isinstance(res, Generator) or isinstance(res, AsyncGenerator):
                    finish_message = openai_chat_chunk_message_template(
                        form_data["model"], ""
                    )
                    finish_message["choices"][0]["finish_reason"] = "stop"
                    yield f"data: {json.dumps(finish_message)}\n\n"
                    yield "data: [DONE]"
            else: # 非流式處理
                if isinstance(res, StreamingResponse):
                    full_content = b""
                    async for chunk in res.body_iterator:
                        full_content += chunk
                    try:
                        yield json.dumps(json.loads(full_content.decode('utf-8'))) + "\n"
                    except json.JSONDecodeError:
                        yield json.dumps({"error": {"detail": "Invalid JSON response from agent pipe."}}) + "\n"
                    return
                elif isinstance(res, dict):
                    yield json.dumps(res) + "\n"
                    return
                elif isinstance(res, BaseModel):
                    yield json.dumps(res.model_dump()) + "\n"
                    return

                if isinstance(res, str):
                    message_content = res
                elif isinstance(res, Generator):
                    message_content = "".join(map(str, res))
                elif isinstance(res, AsyncGenerator):
                    message_content = "".join([str(stream) async for stream in res])
                else:
                    message_content = str(res)

                yield json.dumps(openai_chat_completion_message_template(form_data["model"], message_content)) + "\n"

        except Exception as e:
            log.error(f"Error executing custom Python agent pipe: {e}", exc_info=True)
            yield json.dumps({"type": "error", "content": f"Agent pipe execution failed: {str(e)}"}) + "\n"

    async def _execute_llamaindex_workflow_agent(self, user_message: str, chat_history: list, form_data: Dict[str, Any]) -> AsyncIterator[str]: # 添加 form_data
        yield json.dumps({"type": "status", "content": "Running LlamaIndex workflow agent..."}) + "\n"

        # 獲取 tool_ids
        metadata = form_data.get("metadata", {})
        tool_ids = metadata.get("tool_ids", [])
        if tool_ids is None:
            tool_ids = []

        # 準備 extra_params (類似於 custom_python 代理)
        __event_emitter__ = None
        __event_call__ = None
        __task__ = None
        __task_body__ = None

        if metadata:
            if all(k in metadata for k in ("session_id", "chat_id", "message_id")):
                __event_emitter__ = get_event_emitter(metadata)
                __event_call__ = get_event_call(metadata)
            __task__ = metadata.get("task", None)
            __task_body__ = metadata.get("task_body", None)

        extra_params = {
            "__event_emitter__": __event_emitter__,
            "__event_call__": __event_call__,
            "__chat_id__": metadata.get("chat_id", None),
            "__session_id__": metadata.get("session_id", None),
            "__message_id__": metadata.get("message_id", None),
            "__task__": __task__,
            "__task_body__": __task_body__,
            "__files__": metadata.get("files", []),
            "__user__": {
                "id": self.request.state.user.id,
                "email": self.request.state.user.email,
                "name": self.request.state.user.name,
                "role": self.request.state.user.role,
            },
            "__metadata__": metadata,
            "__request__": self.request,
        }

        # 獲取原始 Open WebUI 工具
        raw_openwebui_tools = get_tools(
            self.request,
            tool_ids,
            self.request.state.user,
            {
                **extra_params,
                "__model__": form_data.get("model_item", {}),
                "__messages__": form_data["messages"],
                "__files__": metadata.get("files", []),
            },
        )

        # 將原始工具轉換為 LlamaIndex FunctionTool
        llamaindex_tools = []
        if FunctionTool is None:
            log.error("LlamaIndex FunctionTool is not available. Cannot create LlamaIndex tools for workflow agent.")
        else:
            for tool_name, tool_data in raw_openwebui_tools.items():
                tool_id = tool_data.get("tool_id")
                tool_callable = tool_data.get("callable")
                tool_spec = tool_data.get("spec", {})
                tool_description = tool_spec.get("description", tool_name)

                proxy_callable = lambda **kwargs: self.openwebui_tool_adapter._execute_openwebui_tool_proxy(
                    tool_id, tool_name, **kwargs
                )

                llamaindex_tool = FunctionTool.from_defaults(
                    fn=proxy_callable,
                    name=tool_name,
                    description=tool_description,
                )
                llamaindex_tools.append(llamaindex_tool)

            call_agent_tool = FunctionTool.from_defaults(
                fn=self.agent_tools.call_agent,
                name="call_another_agent",
                description="Calls another agent with a given message and returns its response. Args: agent_id (str), message (str)"
            )
            llamaindex_tools.append(call_agent_tool)


        # For now, just demonstrating the availability of these objects
        yield json.dumps({"type": "text", "content": f"LlamaIndex workflow agent received message: {user_message}"}) + "\n"
        yield json.dumps({"type": "text", "content": f"Chat history: {chat_history}"}) + "\n"
        yield json.dumps({"type": "text", "content": f"Available LlamaIndex tools: {[t.metadata.name for t in llamaindex_tools]}"}) + "\n"

        # Placeholder for LlamaIndex workflow agent execution logic
        # In a real scenario, you would load the agent_obj.definition (LlamaIndex workflow JSON)
        # and execute it, providing it with llamaindex_tools
        
        # Simulate tool call using one of the converted tools
        if llamaindex_tools:
            yield json.dumps({"type": "status", "content": "LlamaIndex workflow agent simulating tool call..."}) + "\n"
            try:
                yield json.dumps({"type": "text", "content": "(LlamaIndex workflow agent execution not yet implemented)"}) + "\n"
            except Exception as e:
                yield json.dumps({"type": "error", "content": f"Simulated tool call failed: {str(e)}"}) + "\n"
        else:
            yield json.dumps({"type": "text", "content": "No LlamaIndex tools available for simulation."}) + "\n"

        yield json.dumps({"type": "text", "content": "(LlamaIndex workflow agent execution not yet implemented)"}) + "\n"


async def handle_agent_chat_completion(
    request: Request,
    agent_obj: AgentModel,
    form_data: Dict[str, Any],
    user_message: str,
    chat_history: list,
) -> AsyncIterator[str]:
    executor = AgentExecutor(request, agent_obj)
    async for chunk in executor.execute(user_message, chat_history, form_data):
        yield chunk
