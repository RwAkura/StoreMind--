from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

class MCPClient:
    def __init__(self, host:str ,port:str):
        transport = StreamableHttpTransport(
            url=f"http://{host}:{port}/mcp",
        )
        self.client = Client(transport=transport)

    async def tool_list(self):
        async with self.client:
            tool_list = await self.client.list_tools()
            #返回openai的tool_calling 格式
            return [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                }
                for tool in tool_list
            ]

    async def call_tool(self,tool_name:str ,params:dict, authorization: str = None):
        async with self.client:
            meta = {}
            if authorization:
                meta = {
                    "authorization": authorization
                }
            result = await self.client.call_tool(tool_name,params,meta=meta)
            return " ".join(
                item.text
                for item in result.content
            )

