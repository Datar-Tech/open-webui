# Example Custom Python Agent

class Pipe:
    """
    This is an example of a custom Python agent.
    It demonstrates how to define a pipe class with a pipe method
    that can access tools and other context information.
    """

    def __init__(self):
        pass

    async def pipe(self, body: dict, **kwargs):
        """
        This is the entry point for the agent.
        It receives the full request body and any extra parameters.
        """
        print("Custom Python agent started!")

        # Access user message and chat history from the body
        messages = body.get("messages", [])
        user_message = ""
        if messages and messages[-1]["role"] == "user":
            user_message = messages[-1]["content"]

        print(f"User message: {user_message}")

        # Access tools from kwargs
        tools = kwargs.get("__tools__", {})
        print(f"Available tools: {list(tools.keys())}")

        # Example of using a tool
        # This assumes a tool named 'search' is available
        if "search" in tools:
            print("Calling the 'search' tool...")
            try:
                search_tool = tools["search"]["callable"]
                search_result = await search_tool(query=f"information about {user_message}")
                print(f"Search result: {search_result}")
                yield f"I found this information using the search tool: {search_result}"
            except Exception as e:
                print(f"Error calling search tool: {e}")
                yield f"Sorry, I couldn't use the search tool. Error: {e}"
        else:
            yield f"I received your message: '{user_message}', but I don't have a 'search' tool to help you."

        print("Custom Python agent finished.")
