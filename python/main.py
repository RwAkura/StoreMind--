import json
from contextlib import asynccontextmanager

from pydantic import BaseModel
from starlette.responses import StreamingResponse

from fastapi import FastAPI,Header
from fastapi.middleware.cors import CORSMiddleware
from agent.agent import ReactAgent,LLMClient,MCPClient,MemoryManager
from agent.database import Database
from JwtUtil import get_user_id_from_token

database = Database()

llm_client = LLMClient()
mcp_client = MCPClient("localhost",8000)
memory_manager = MemoryManager(database)
agent = ReactAgent(llm_client,mcp_client,memory_manager)

class ConfirmationRequest(BaseModel):
    run_id: str
    approved: bool

class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None

#异步函数作为fastapi的生命周期启动来初始化数据库连接池
@asynccontextmanager
async def database_lifespan(app: FastAPI):
    await database.connect()
    yield
    await database.close()

app = FastAPI(lifespan=database_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(request: ChatRequest,authorization: str = Header(...)):
    #内部函数将agent的返回信息包装为SSE格式
    async def event_stream():
        async for event in agent.run_stream(request.question,authorization,request.conversation_id):
            yield f"data: {json.dumps(event,ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(),media_type="text/event-stream")

@app.post("/confirm")
async def confirm(request: ConfirmationRequest,authorization: str = Header(...)):
    async def event_stream():
        async for event in agent.confirm_run(request.run_id,request.approved,authorization):
            yield f"data: {json.dumps(event,ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(),media_type="text/event-stream")

@app.get("/conversation/list")
async def get_conversation_list(authorization: str = Header(...)):
    try:
        return {
            "type": "success",
            "data": await memory_manager.get_conversation_list(get_user_id_from_token(authorization))
        }
    except ValueError as e:
        return {
            "type": "error",
            "message": str(e),
        }

@app.get("/conversation/{conversation_id}")
async def get_conversation_content(conversation_id: str,authorization: str = Header(...)):
    try:
        user_id = get_user_id_from_token(authorization)
        if await memory_manager.conversation_authorization(conversation_id,user_id):
            return {
                "type": "success",
                "data": await memory_manager.get_conversation_memory(conversation_id)
            }
        else:
            return {
                "type": "error",
                "message": "身份凭证无效",
            }
    except ValueError as e:
        return {
            "type": "error",
            "message": str(e),
        }


