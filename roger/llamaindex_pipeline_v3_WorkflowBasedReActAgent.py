"""
title: Llama Index Pipeline
author: open-webui
date: 2024-05-30
version: 1.0
license: MIT
description: A pipeline for retrieving relevant information from a knowledge base using the Llama Index library, now with Workflow-based ReAct Agent.
requirements: llama-index==0.12.34, llama-index-llms-openai==0.3.38, langfuse, llama-index-embeddings-azure-openai==0.3.2, llama-index-llms-azure-openai==0.3.2
"""
from typing import List, Union, Generator, Iterator, Optional, Any, AsyncIterator # Added AsyncIterator back
from pydantic import BaseModel, Field
from llama_index.core import Response
from tenacity import retry, stop_after_attempt, wait_exponential
from llama_index.core.storage import StorageContext
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
# Old ReActAgent import, will be replaced by workflow
# from llama_index.core.agent import ReActAgent 
from llama_index.core.tools import FunctionTool, ToolSelection, ToolOutput, BaseTool
from llama_index.core.llms import ChatMessage, MessageRole, LLM
import json

# Azure Search imports
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient

# Langfuse integration
from langfuse.llama_index import LlamaIndexInstrumentor

# Import dotenv for loading environment variables from .env file
from dotenv import load_dotenv

import os
import logging
import sys
import asyncio # Added for async main
import time # Added for execution time tracking

# LlamaIndex Workflow imports
from llama_index.core.agent.react import ReActChatFormatter, ReActOutputParser
from llama_index.core.agent.react.types import (
    ActionReasoningStep,
    ObservationReasoningStep,
)
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.workflow import (
    Context,
    Workflow,
    StartEvent,
    StopEvent,
    Event,
    step,
)

import queue # Standard library queue for thread-safe communication

# Helper function to iterate an async generator in a sync context
async def _agen_wrapper(agen: AsyncIterator[Any], thread_queue: queue.Queue, loop: asyncio.AbstractEventLoop):
    """Wraps an async generator to put its items into a thread-safe queue.Queue."""
    try:
        async for item in agen:
            # Use call_soon_threadsafe to put items from the event loop thread to the main thread's queue
            loop.call_soon_threadsafe(thread_queue.put, item)
    except Exception as e:
        loop.call_soon_threadsafe(thread_queue.put, e)  # Put exception in queue
    finally:
        loop.call_soon_threadsafe(thread_queue.put, None) # Sentinel to indicate completion

def _iterate_async_gen_in_sync(agen: AsyncIterator[Any]) -> Iterator[Any]:
    """
    Synchronously iterates over an asynchronous generator using a separate thread for the event loop.
    """
    thread_queue = queue.Queue() # Use standard library queue for thread-safety
    
    # The following commented block containing an erroneous 'await' call is removed.
    # # This async def is not strictly needed here anymore as main_coro is not used with asyncio.run directly
    # # async def main_coro():
    #     # Ensure there's a running loop for the agen_wrapper if called from a context
    #     # where asyncio.run() is not already managing one for this specific task.
    #     # However, since we are calling asyncio.run(main_coro()) below,
    #     # this main_coro itself will run in a new loop.
    #     await _agen_wrapper(agen, queue) # This 'queue' was also a typo, should be thread_queue

    # Run the wrapper in a new event loop.
    # This is suitable if _iterate_async_gen_in_sync is called from a synchronous context.
    # If it's called from an already running asyncio loop (like in the test harness),
    # asyncio.run() will raise a RuntimeError.
    # The test harness itself needs to be careful not to create this conflict.
    # For OpenWebUI's synchronous pipe, this approach should be fine.
    
    # We need a thread to run the asyncio.run() if the main thread is already sync
    # and we don't want to block it entirely if the generator is long-running.
    # However, for a simple synchronous iteration, we can consume it directly.
    # The challenge is that `pipe` itself is synchronous.
    
    # Let's try a simpler approach for the bridge, assuming `pipe` is truly sync.
    # We'll run the async generator to completion and collect results if it's not too complex.
    # For true streaming, a thread-based approach is more robust.

    # Simpler approach for now: run the async generator using asyncio.run()
    # This will block until the async generator is fully consumed.
    # This is not ideal for true streaming from a sync method but is a common bridge.
    
    # To make it truly iterable synchronously while the async gen runs in background:
    import threading

    # loop = None # loop will be created and managed within the thread
    # thread = None # thread variable is local to this function

    def start_loop_in_thread():
        # nonlocal loop # loop is local to this thread function
        local_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(local_loop)
        try:
            # Pass the local_loop to _agen_wrapper so it can use call_soon_threadsafe
            local_loop.run_until_complete(_agen_wrapper(agen, thread_queue, local_loop))
        finally:
            local_loop.close()

    thread = threading.Thread(target=start_loop_in_thread)
    thread.daemon = True # So it doesn't block program exit
    thread.start()

    while True:
        # Get items from the thread_queue. This blocks until an item is available.
        item = thread_queue.get() # This is a blocking call to a standard queue.Queue
        if item is None: # Sentinel for completion
            break
        if isinstance(item, Exception):
            logger.error(f"Error from async generator: {item}", exc_info=item)
            yield f"Pipeline error during async processing: {str(item)}"
            break
        yield item
        thread_queue.task_done() # Notify queue that item processing is complete

    thread.join(timeout=10) # Wait for the thread to finish, increased timeout slightly

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

# Workflow Event Classes
class PrepEvent(Event):
    pass

class InputEvent(Event):
    input: List[ChatMessage]

class StreamEvent(Event):
    delta: str

class ToolCallEvent(Event):
    tool_calls: List[ToolSelection]

class FunctionOutputEvent(Event): # Defined as per markdown, though not directly used in this ReAct example's steps
    output: ToolOutput

# Workflow-based ReAct Agent Class
class ReActAgentWorkflow(Workflow):
    def __init__(
        self,
        *args: Any,
        llm: LLM | None = None,
        tools: list[BaseTool] | None = None,
        extra_context: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools or []
        self.llm = llm or AzureOpenAI() # Defaulting to AzureOpenAI if not provided
        self.formatter = ReActChatFormatter.from_defaults(
            context=extra_context or ""
        )
        self.output_parser = ReActOutputParser()
        self.logger = logging.getLogger(__name__) # Add logger

    @step
    async def new_user_msg(self, ctx: Context, ev: StartEvent) -> PrepEvent:
        self.logger.info("Workflow step: new_user_msg")
        await ctx.set("sources", []) # clear sources

        # init memory if needed (or get from context if passed in)
        memory = await ctx.get("memory", default=None)
        if not memory:
            self.logger.info("No existing memory in context, creating new ChatMemoryBuffer.")
            memory = ChatMemoryBuffer.from_defaults(llm=self.llm)
        else:
            self.logger.info("Using existing memory from context.")

        user_input = ev.input # This is the current user_message string
        user_msg = ChatMessage(role=MessageRole.USER, content=user_input)
        memory.put(user_msg)
        self.logger.debug(f"Added user message to memory: {user_input}")

        await ctx.set("current_reasoning", []) # clear current reasoning
        await ctx.set("memory", memory) # set memory back to context

        return PrepEvent()

    @step
    async def prepare_chat_history(
        self, ctx: Context, ev: PrepEvent
    ) -> InputEvent:
        self.logger.info("Workflow step: prepare_chat_history")
        memory = await ctx.get("memory")
        chat_history = memory.get()
        current_reasoning = await ctx.get("current_reasoning", default=[])
        
        self.logger.debug(f"Preparing chat history. History length: {len(chat_history)}, Reasoning steps: {len(current_reasoning)}")

        llm_input = self.formatter.format(
            self.tools, chat_history, current_reasoning=current_reasoning
        )
        return InputEvent(input=llm_input)

    @step
    async def handle_llm_input(
        self, ctx: Context, ev: InputEvent
    ) -> Union[ToolCallEvent, StopEvent, PrepEvent]: # Added PrepEvent for loop
        self.logger.info("Workflow step: handle_llm_input")
        chat_history_for_llm = ev.input # Renamed to avoid confusion with broader chat_history
        current_reasoning = await ctx.get("current_reasoning", default=[])
        memory = await ctx.get("memory")

        self.logger.debug("Getting LLM response...")
        llm_response_message = await self.llm.achat(chat_history_for_llm)
        full_response_content = llm_response_message.message.content

        self.logger.debug(f"LLM raw response content: {full_response_content}")

        # Ensure llm_response_message is not None before proceeding
        if llm_response_message is None:
            # This case should ideally not happen if the LLM streamed anything.
            # If it does, it might indicate an empty response or an issue.
            self.logger.warning("LLM response message is None after streaming. Looping for retry.")
            # Add an observation about the empty/failed LLM response
            current_reasoning.append(
                ObservationReasoningStep(observation="LLM did not provide a response.")
            )
            await ctx.set("current_reasoning", current_reasoning)
            return PrepEvent() # Loop again

        try:
            reasoning_step = self.output_parser.parse(llm_response_message.message.content)
            current_reasoning.append(reasoning_step)
            self.logger.info(f"Parsed reasoning step: {type(reasoning_step)}")

            if reasoning_step.is_done:
                self.logger.info("Reasoning step is done. Preparing StopEvent.")
                memory.put(
                    ChatMessage(
                        role=MessageRole.ASSISTANT, content=reasoning_step.response
                    )
                )
                await ctx.set("memory", memory)
                await ctx.set("current_reasoning", current_reasoning)

                sources = await ctx.get("sources", default=[])
                return StopEvent(
                    result={
                        "response": reasoning_step.response,
                        "sources": sources, # Markdown example had [sources], check if it should be flat
                        "reasoning": current_reasoning,
                    }
                )
            elif isinstance(reasoning_step, ActionReasoningStep):
                self.logger.info(f"ActionReasoningStep: {reasoning_step.action}, Args: {reasoning_step.action_input}")
                tool_name = reasoning_step.action
                tool_args = reasoning_step.action_input
                return ToolCallEvent(
                    tool_calls=[
                        ToolSelection(
                            tool_id="fake_id", # Tool ID is not strictly used by FunctionTool lookup by name
                            tool_name=tool_name,
                            tool_kwargs=tool_args,
                        )
                    ]
                )
        except Exception as e:
            self.logger.error(f"Error parsing LLM output or processing reasoning step: {e}", exc_info=True)
            current_reasoning.append(
                ObservationReasoningStep(
                    observation=f"There was an error in parsing my reasoning: {e}"
                )
            )
            await ctx.set("current_reasoning", current_reasoning)

        # if no tool calls or final response (e.g. error or unexpected output), iterate again
        self.logger.info("No tool call or final response, preparing for another iteration.")
        return PrepEvent()

    @step
    async def handle_tool_calls(
        self, ctx: Context, ev: ToolCallEvent
    ) -> PrepEvent:
        self.logger.info("Workflow step: handle_tool_calls")
        tool_calls = ev.tool_calls
        tools_by_name = {tool.metadata.get_name(): tool for tool in self.tools}
        current_reasoning = await ctx.get("current_reasoning", default=[])
        sources = await ctx.get("sources", default=[])

        for tool_call in tool_calls:
            self.logger.info(f"Handling tool call: {tool_call.tool_name} with args {tool_call.tool_kwargs}")
            tool = tools_by_name.get(tool_call.tool_name)
            if not tool:
                self.logger.warning(f"Tool {tool_call.tool_name} not found.")
                current_reasoning.append(
                    ObservationReasoningStep(
                        observation=f"Tool {tool_call.tool_name} does not exist."
                    )
                )
                continue

            try:
                # Assuming tools are synchronous. If async, need await tool(**...)
                # The run_azure_search is synchronous.
                tool_output_obj: ToolOutput = tool(**tool_call.tool_kwargs) # tool_output_obj is ToolOutput
                # The raw_output field of ToolOutput should contain the original Response object
                original_response_object = tool_output_obj.raw_output
                self.logger.info(f"Type of tool_output_obj.raw_output: {type(original_response_object)}")
                self.logger.debug(f"Value of tool_output_obj.raw_output: {original_response_object}")

                if isinstance(original_response_object, Response):
                    # This is the expected path: raw_output is the LlamaIndex Response object
                    sources.append(original_response_object) 
                    # The .response attribute of our LlamaIndex Response object is the JSON string of search results
                    current_reasoning.append(
                        ObservationReasoningStep(observation=str(original_response_object.response)) 
                    )
                elif original_response_object is None and tool_output_obj.content and isinstance(tool_output_obj.content, str):
                    # Fallback: if raw_output is None, but content (string) exists (as confirmed by previous logs)
                    self.logger.warning(
                        "Tool raw_output was None, but tool_output_obj.content (string) exists. "
                        "Using tool_output_obj.content for observation. This might indicate an issue "
                        "in how the tool result is packaged if raw_output is unexpectedly None."
                    )
                    # Use the string content directly for observation
                    observation_str = tool_output_obj.content
                    sources.append(Response(response=observation_str)) # Create a basic Response for sources
                    current_reasoning.append(
                        ObservationReasoningStep(observation=observation_str)
                    )
                else:
                    # Handle other unexpected cases
                    error_msg = (
                        f"Unexpected tool output format. "
                        f"tool_output_obj.raw_output type: {type(original_response_object)}, "
                        f"tool_output_obj.content: {tool_output_obj.content}"
                    )
                    self.logger.error(error_msg)
                    current_reasoning.append(
                        ObservationReasoningStep(observation=f"Tool execution resulted in unexpected output: {error_msg}")
                    )
                    sources.append(Response(response=f"Error processing tool output: {error_msg}"))
                
                self.logger.info(f"Tool {tool_call.tool_name} executed successfully.")
            except Exception as e:
                self.logger.error(f"Error calling tool {tool.metadata.get_name()}: {e}", exc_info=True)
                current_reasoning.append(
                    ObservationReasoningStep(
                        observation=f"Error calling tool {tool.metadata.get_name()}: {e}"
                    )
                )

        await ctx.set("sources", sources)
        await ctx.set("current_reasoning", current_reasoning)
        return PrepEvent()


class SearchPayload(BaseModel):
    """Schema for Azure AI Search API."""
    index_name: str = Field(..., description="The name of the Azure Search index to query.")
    search_text: str = Field(..., description="The main search query text.")
    select: str = Field(..., description="Comma-separated list of fields to retrieve. Do NOT include field extracted_vector. Always include fields which indicate the source of the document.")
    filter: Optional[str] = Field(default=None, description="""Use OData filter expressions to narrow results by specific criteria.
            WHEN TO USE FILTERS:
                - For date ranges: "filter": "date ge '2023-01-01' and date le '2023-12-31'"
                - For numeric values: "filter": "price lt 100"
                - For categories: "filter": "category eq 'Technology'"
                - For boolean fields: "filter": "isAvailable eq true"
                - For combining criteria: "filter": "category eq 'Books' and price lt 20""")
    top: Optional[int] = Field(default=5, description="Number of results to return. Note that the API response will include an '@odata.count' field indicating the total number of matching documents available, which might be higher than this 'top' value.")
    query_type: Optional[str] = Field(default=None, description="Type of search query. When set to 'semantic', the semantic configuration must be specified in 'semantic_configuration_name'.")
    semantic_configuration_name: Optional[str] = Field(default=None, description="Name of the semantic configuration to use when queryType is 'semantic'.")
    order_by: Optional[str] = Field(default=None, description="Comma-separated list of fields to sort the results by.")
    vector_filter_mode: Optional[str] = Field(default=None, description="Filters can be applied before query execution to reduce the query surface, or after query execution to trim results.")
    vector_field: Optional[str] = Field(..., description="The name of the field in the index that contains the vector representation of the document. Usually, the data type is Collection(Edm.Single).")
    k: Optional[int] = Field(default=None, description="k determines how many nearest neighbor matches are returned from the vector query and provided to the RRF ranker.")

class Pipeline:
    class Valves(BaseModel):
        AZURE_API_KEY: str 
        AZURE_ENDPOINT: str
        AZURE_API_VERSION: str
        AZURE_SUBSCRIPTION_KEY: str
        LLAMAINDEX_MODEL_NAME: str
        LLAMAINDEX_EMBEDDING_MODEL_NAME: str
        AZURE_SEARCH_API_KEY: str
        AZURE_SEARCH_ENDPOINT: str
        AZURE_SEARCH_ADMIN_KEY: str
        LANGFUSE_PUBLIC_KEY: Optional[str] = None
        LANGFUSE_SECRET_KEY: Optional[str] = None
        LANGFUSE_HOST: Optional[str] = None

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.storage_context = StorageContext.from_defaults()
        load_dotenv(override=True)
        self.logger.info("Loaded environment variables from .env file.")
        
        self.valves = self.Valves(
            **{
                "AZURE_API_KEY": os.getenv("AZURE_API_KEY", "default"),
                "AZURE_ENDPOINT": os.getenv("AZURE_ENDPOINT", "https://llm-api.amd.com"),
                "AZURE_API_VERSION": os.getenv("AZURE_API_VERSION", "default"),
                "AZURE_SUBSCRIPTION_KEY": os.getenv("AZURE_SUBSCRIPTION_KEY", "7cce1ac73d98442c844bb040b983114c"),
                "AZURE_SEARCH_API_KEY": os.getenv("AZURE_SEARCH_API_KEY", "SbEBqR8O01YJ7WwhFJo32DGEhG4pRqk9YZ7rjGEfrhAzSeAnryoB"),
                "AZURE_SEARCH_ENDPOINT": os.getenv("AZURE_SEARCH_ENDPOINT", "https://pdase-cepm-search.search.windows.net"),
                "AZURE_SEARCH_ADMIN_KEY": os.getenv("AZURE_SEARCH_ADMIN_KEY", "cNK2ZylNjszCu7HnNhFYQYPLyHOGkP4nJh6cZxa0rGAzSeDa9nt7"),
                "LLAMAINDEX_MODEL_NAME": os.getenv("LLAMAINDEX_MODEL_NAME", "gpt-4.1"),
                "LLAMAINDEX_EMBEDDING_MODEL_NAME": "text-embedding-ada-002",
                "LANGFUSE_PUBLIC_KEY": os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-dc0f9f5d-7f02-472c-9032-8b5112a92d0c"),
                "LANGFUSE_SECRET_KEY": os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-15e0fb26-b64f-4cc7-bab9-5b073daad037"),
                "LANGFUSE_HOST": os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com"),
            }
        )
        azure_headers = {
            'Ocp-Apim-Subscription-Key': self.valves.AZURE_SUBSCRIPTION_KEY,
        }
        
        self.instrumentor = LlamaIndexInstrumentor(
            public_key=self.valves.LANGFUSE_PUBLIC_KEY,
            secret_key=self.valves.LANGFUSE_SECRET_KEY,
            host=self.valves.LANGFUSE_HOST
        )
        self.instrumentor.start()
        self.logger.info("Langfuse instrumentation initialized and started")

        @retry(
            wait=wait_exponential(multiplier=1, min=4, max=60),
            stop=stop_after_attempt(5)
        )
        def create_llm():
            return AzureOpenAI(
                model=self.valves.LLAMAINDEX_MODEL_NAME,
                deployment_name=self.valves.LLAMAINDEX_MODEL_NAME,
                api_key=self.valves.AZURE_API_KEY,
                azure_endpoint=self.valves.AZURE_ENDPOINT,
                api_version=self.valves.AZURE_API_VERSION,
                default_headers=azure_headers,
                max_retries=3,
                timeout=60,
                temperature=0,
                # reasoning_Effort="medium", # This might not be a standard AzureOpenAI param
            )
        self.logger.warning(f"Using model from valves: {self.valves.LLAMAINDEX_MODEL_NAME}")
        self.llm = create_llm()

        def create_AzureSearchClient():
            return SearchIndexClient(
                endpoint=self.valves.AZURE_SEARCH_ENDPOINT,
                credential=AzureKeyCredential(self.valves.AZURE_SEARCH_ADMIN_KEY),
            )
        self.index_client = create_AzureSearchClient()
            
    def get_azure_search_index_list(self) -> str:
        """
        This function retrieves the list of Azure Search indexes.
        """
        temp_list = ["azureblob-index-jiratest"]  # This is a temporary hardcoded list for testing purposes.
        return temp_list
        
        # try:
        #     # Get the list of indexes
        #     index_list = self.index_client.list_indexes()
        #     index_names = [index.name for index in index_list]
        #     logger.info(f"Successfully retrieved {len(index_names)} indexes.")

        #     # To see the full raw schema structure:
        #     return json.dumps(index_names, indent=2)

        # except Exception as e:
        #     logger.error(f"Azure Search API call failed: {e}", exc_info=True)
        #     return f"Error during Azure Search get index list: {str(e)}"
    
    def get_azure_search_index_schema(self, input) -> str:
        """
        This function retrieves the schema of a specific Azure Search index.
        """
        try:
            # Get the index schema
            index_definition = self.index_client.get_index(name=input)
            logger.info(f"Successfully retrieved schema for index '{index_definition.name}'")

            # To see the full raw schema structure:
            return json.dumps(index_definition.serialize(), indent=2)

        except Exception as e:
            logger.error(f"Azure Search API call failed: {e}", exc_info=True)
            return f"Error during Azure Search get index schema: {str(e)}"

    def run_azure_search(self,
        index_name: str,
        search_text: str,
        select: str,
        vector_field: Optional[str] = None,
        filter: Optional[str] = None,
        top: Optional[int] = 5,
        query_type: Optional[str] = None,
        semantic_configuration_name: Optional[str] = None,
        vector_filter_mode: Optional[str] = None,
        k: Optional[int] = None,
        ) -> Response: # Return type is LlamaIndex Response
        azure_search_endpoint = self.valves.AZURE_SEARCH_ENDPOINT
        azure_search_index = index_name
        azure_search_key = self.valves.AZURE_SEARCH_API_KEY

        Azuresearchclient = SearchClient(
                endpoint=azure_search_endpoint,
                index_name=azure_search_index,
                credential=AzureKeyCredential(azure_search_key),
                api_version="2024-11-01-preview" # Check if this version is appropriate
            )
        try:
            if vector_field and vector_field != "":
                results = Azuresearchclient.search(
                    search_text=search_text,
                    select=select,
                    filter=filter,
                    top=top,
                    query_type=query_type,
                    semantic_configuration_name=semantic_configuration_name,
                    include_total_count=True,
                    vector_filter_mode=vector_filter_mode,
                    vector_queries=[
                        {
                            "kind": "text",
                            "text": search_text,
                            "fields": vector_field,
                            "k": k
                        }
                    ],
                )
            else:
                results = Azuresearchclient.search(
                    search_text=search_text,
                    select=select,
                    filter=filter,
                    top=top,
                    query_type=query_type,
                    semantic_configuration_name=semantic_configuration_name,
                    include_total_count=True
                )

            documents = list(results)
            self.logger.info(f"Azure Search returned {len(documents)} documents.")
            result_str = json.dumps([doc for doc in documents], default=str, indent=2)
            
            from llama_index.core.schema import TextNode, NodeWithScore
            source_node = NodeWithScore(
                node=TextNode(text=str(result_str)), # Content for the node
                score=1.0 # Placeholder score
            )
            
            response = Response(response=str(result_str)) # Main response content
            response.source_nodes = [source_node]
            response.metadata = {"search_results_count": len(documents)}
            # setattr(response, "raw_output", str(result_str)) # raw_output is usually set by LLM
            return response

        except Exception as e:
            self.logger.error(f"Azure Search API call failed: {e}", exc_info=True)
            # Return an error response object or raise
            error_response = Response(response=f"Error during Azure Search: {str(e)}")
            error_response.source_nodes = []
            return error_response
    
    async def on_startup(self):
        self.logger.info("Starting pipeline initialization...")
        try:
            self.logger.info(f"Using Azure endpoint: {self.valves.AZURE_ENDPOINT}")
            self.logger.warning(f"Using model: {self.valves.LLAMAINDEX_MODEL_NAME}")
            self.logger.info(f"Using embedding model: {self.valves.LLAMAINDEX_EMBEDDING_MODEL_NAME}")
        except Exception as e:
            self.logger.error(f"Critical error during pipeline startup: {str(e)}", exc_info=True)
            raise RuntimeError(f"Pipeline startup failed: {str(e)}")

    async def on_shutdown(self):
        self.logger.info("Starting pipeline shutdown...")
        try:
            self.logger.debug("Flushing Langfuse events")
            self.instrumentor.flush()
            self.logger.info("Pipeline shutdown completed successfully")
        except Exception as e:
            self.logger.error(f"Error during pipeline shutdown: {str(e)}", exc_info=True)
            raise RuntimeError(f"Pipeline shutdown failed: {str(e)}")

    # This is the new async logic, renamed from the original pipe method
    async def _async_pipe_logic(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> AsyncIterator[str]:
        try:
            if not user_message:
                self.logger.error("Empty user message received")
                raise ValueError("User message cannot be empty")
            if not model_id:
                self.logger.error("No model ID provided")
                raise ValueError("Model ID cannot be empty")

            self.logger.info(f"Processing query with model {model_id} using Workflow ReAct Agent")
            self.logger.debug(f"User message: {user_message}")
            self.logger.debug(f"Context messages: {messages}")
            self.logger.debug(f"Additional body parameters: {body}")

            # Access the user object sent by open_webui
            user_info = body.get("user", {})
            
            # Prioritize user_email for Langfuse user_id, then user_id from user_info, then anonymous
            user_id_to_use = "anonymous"
            if user_info.get("email"):
                user_id_to_use = user_info.get("email")
            elif user_info.get("id"):
                user_id_to_use = user_info.get("id")

            metadata = {
                "model_id": model_id,
                "query_length": len(user_message),
                "history_length": len(messages),
                "query_type": "workflow_react_agent",
                "user_id": user_id_to_use
            }

            with self.instrumentor.observe() as trace:
                try:
                    trace.update(metadata=metadata, user_id=user_id_to_use)
                except Exception as e:
                    self.logger.warning(f"Failed to update Langfuse trace metadata: {str(e)}")

                get_AzureCognitiveSearch_index_list = FunctionTool.from_defaults(
                    fn=self.get_azure_search_index_list, 
                    name="get_AzureCognitiveSearch_index_list", 
                    description="Get the list of Azure Search indexes."
                )

                get_AzureCognitiveSearch_index_schema = FunctionTool.from_defaults(
                    fn=self.get_azure_search_index_schema, 
                    name="get_AzureCognitiveSearch_index_schema", 
                    description="Get the schema of the Azure Search index."
                )
                search_AzureCognitiveSearch_index = FunctionTool.from_defaults(
                    fn=self.run_azure_search, 
                    name="search_AzureCognitiveSearch_index",
                    description="Search the Azure Search index with the given parameters. The JSON output will contain a 'value' array with the search results. It will ALSO include an '@odata.count' field, which indicates the TOTAL number of documents in the index that matched the search criteria, irrespective of the 'top' parameter. Use this to understand if more relevant documents exist beyond what was returned.",
                    fn_schema=SearchPayload
                )
                tools_list = [
                    get_AzureCognitiveSearch_index_list, 
                    get_AzureCognitiveSearch_index_schema, 
                    search_AzureCognitiveSearch_index
                ]
                
                system_prompt = """
                When executing search tasks, follow these SEARCH STRATEGIES in strict order:
                1. Index Discovery
                 - Use get_AzureCognitiveSearch_index_list to retrieve the list of available indexes.
                 - Identify the index(es) most relevant to the user's topic.

                2. Schema Inspection
                   For each chosen index, use get_AzureCognitiveSearch_index_schema to retrieve its field definitions and data types.
                   If vectorSearch and semantic configuration are available in the schema, always use vector_field and semantic_configuration_name to construct queries in the next step.

                3. Query Planning & Execution
                  a. Based on the schema, plan your query strategy:
                     - Based on the schema and your understanding of Azure Cognitive Search query syntax (https://learn.microsoft.com/en-us/azure/search/search-query-overview), construct effective queries.
                     - search_text should be in English.
                  b. If the user's request covers multiple distinct items or subtopics:
                     - Break the request into separate sub-queries.
                     - Execute each in turn via search_AzureCognitiveSearch_index
                     - Only proceed to step 4 once every sub-query has returned results.

                4. Results Synthesis & Response
                 - Collate findings from all queries.
                 - Structure your answer in clear Markdown, using headings, bullet lists, or tables for readability.
                 - Always include the reminder in the final output. Note: The following answer is based on the top {n} documents retrieved from the knowledge base. For a more comprehensive answer, consider refining your search criteria or increasing the number of results.
                 - At the end, ALWAYS include a Source section listing each document you used. If no link is available, note the source as "No link available" or similar. Example:
                    ### Source
                    - [filename](doclink)
                    - [source](source_link)
                    - ...

                5. Handling Uncertainty or Gaps
                   If the results seem incomplete or inconclusive (e.g., not enough sources, no clear answer), 
                     - Do not produce a partial answer.
                     - Recommend alternative query strategies (e.g., broaden search_text=, add/remove filters, use semantic or vector search if available) and run additional queries with adjusted parameters, then synthesize the expanded results.

                Important: You may never skip a phase—or return final output—until all sub-queries are executed and synthesized.
                """

                workflow_agent = ReActAgentWorkflow(
                    llm=self.llm,
                    tools=tools_list,
                    extra_context=system_prompt,
                    verbose=True, # Workflow verbose
                    timeout=300 # Workflow timeout in seconds
                )
                
                workflow_ctx = Context(workflow_agent) # Create a new context for this run
                # Initialize memory in the context with historical messages
                chat_memory = ChatMemoryBuffer.from_defaults(llm=self.llm)
                for msg_data in messages:
                    role = MessageRole.USER if msg_data["role"] == "user" else MessageRole.ASSISTANT
                    chat_memory.put(ChatMessage(role=role, content=msg_data["content"]))
                await workflow_ctx.set("memory", chat_memory)
                self.logger.info(f"Initialized workflow context with {len(messages)} historical messages.")
                
                start_time = time.time()
                self.logger.info("Executing query with ReActAgentWorkflow...")
                
                # The run method is non-blocking if you iterate stream_events,
                # but becomes blocking if you await it directly.
                handler = workflow_agent.run(input=user_message, ctx=workflow_ctx)

                # Collect the full thought/action stream first
                full_thought_stream_content = ""
                async for event in handler.stream_events():
                    if isinstance(event, StreamEvent):
                        full_thought_stream_content += (event.delta or "")


                # Execute workflow and get results
                final_result_obj = await handler
                
                # Format reasoning steps for display
                yield "<details type=\"reasoning\">\n<summary>Thought</summary>\n"
                
                # Get reasoning steps from the final result
                reasoning_steps = final_result_obj.get('reasoning', []) if final_result_obj else []
                for step in reasoning_steps:
                    if hasattr(step, 'thought') and step.thought:
                        yield f">Thought: {step.thought}\n"
                    elif hasattr(step, 'action') and step.action:
                        action_str = f">Action: {step.action}"
                        if hasattr(step, 'action_input') and step.action_input:
                            action_str += f"\n>Action Input: {step.action_input}"
                        yield f"{action_str}\n"
                
                yield "</details>\n" 
                execution_time = time.time() - start_time
                self.logger.info(f"Workflow execution completed in {execution_time:.2f} seconds.")

                if final_result_obj:
                    final_answer_content = final_result_obj.get('response', '')
                    
                    # Yield the final answer
                    if final_answer_content:
                        yield "Answer:\n" 
                    
                    if final_answer_content:
                        yield final_answer_content

                    self.logger.info(f"Final response from workflow: {final_answer_content}")
                    trace.score(name="success", value=1.0)
                    trace.update(
                        metadata={
                            "execution_time_seconds": execution_time,
                            "response_length": len(str(final_answer_content)),
                            "tools_used": [tool.metadata.name for tool in tools_list],
                            "reasoning_steps_count": len(final_result_obj.get('reasoning', [])),
                            "sources_count": len(final_result_obj.get('sources', []))
                        }
                    )
                else:
                    self.logger.error("Workflow returned no final result object.")
                    trace.score(name="failure_no_result", value=0.0)
                    # No final result available
                    yield "No response generated from workflow."
                    raise RuntimeError("Workflow did not produce a final result.")

        except Exception as e:
            self.logger.error(f"Error in pipeline: {str(e)}", exc_info=True)
            if 'trace' in locals() and trace: # Check if trace is defined
                trace.update(metadata={"error": str(e)})
                trace.score(name="error", value=0.0)
            # Yield an error message if streaming, or raise
            yield f"Pipeline execution failed: {str(e)}" # Or raise, depending on desired error propagation

    # The main pipe method, now synchronous, using the helper to consume the async generator
    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]: # Signature changed to sync
        
        # Get the async generator from our internal async logic method
        async_gen = self._async_pipe_logic(user_message, model_id, messages, body)
        
        # Use the helper to iterate over the async generator synchronously
        return _iterate_async_gen_in_sync(async_gen)

if __name__ == "__main__":
    async def main_async_test(): # Renamed main to avoid conflict if 'main' is a module
        pipeline_instance = None # Define outside try for finally block
        try:
            # Configure logging for main execution (if not already configured globally)
            # logging.basicConfig(level=logging.INFO) # Already configured globally
            logger.info("Starting pipeline example...")

            pipeline_instance = Pipeline()
            await pipeline_instance.on_startup()
            
            user_message = "How many OPNs will we offer for Granite Ridge and Strix Halo? Help me to create a table to list all the OPN, spec./frequency/clock ...etc. for comparison."
            model_id = os.getenv("LLAMAINDEX_MODEL_NAME", "gpt-4.1") 
            messages_history = [{"role": "user", "content": user_message}] 
            body_params = {} 

            logger.info("Running example query...")
            # pipe() is now synchronous and returns a synchronous generator
            response_generator = pipeline_instance.pipe(user_message, model_id, messages_history, body_params)
            
            print("\nAgent Response (Streaming):")
            full_response_text = ""
            # Iterate over the synchronous generator
            for chunk in response_generator: 
                print(chunk, end="", flush=True)
                full_response_text += chunk
            print("\n--- End of Streamed Response ---")
            logger.info(f"Full streamed response received: {full_response_text}")
            
            logger.info("Pipeline example completed successfully")

        except Exception as e:
            logger.error(f"Error in main execution: {str(e)}", exc_info=True)
            # sys.exit(1) # Avoid sys.exit in library code examples if possible
        finally:
            if pipeline_instance:
                logger.info("Shutting down pipeline...")
                await pipeline_instance.on_shutdown()
                logger.info("Pipeline shutdown complete.")
            else:
                logger.info("Pipeline was not initialized, skipping shutdown.")
            logger.info("--- Pipeline Example Finished ---")

    # Run the async main_async_test function
    asyncio.run(main_async_test())
