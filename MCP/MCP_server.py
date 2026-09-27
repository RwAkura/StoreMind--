from fastmcp import FastMCP
from tools import register_tools

mcp = FastMCP("StoreMind")
register_tools(mcp)

if __name__ == '__main__':
    mcp.run(transport="http",port=8000,host="127.0.0.1")