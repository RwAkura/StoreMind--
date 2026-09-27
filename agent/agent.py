import json
from uuid import uuid4

from agent.llm import LLMClient
from agent.memory_manager import MemoryManager

from JwtUtil import get_user_id_from_token

from MCP.MCP_client import MCPClient


confirmation_tools_name = [
    "store_inbound"
]

# ReAct 提示词
PROMPT_TEMPLATE = """
你是 StoreMind 门店经营分析助手。

以下是该会话的历史摘要：
{summary}

以下是最近的历史对话：
{history}

请结合历史摘要、最近对话以及当前用户问题进行回答。
"""

pending_run = {}

class ReactAgent:
    def __init__(self,llm_client:LLMClient,mcp_client: MCPClient,memory_manager: MemoryManager,max_step: int = 5):
        self.llm_client = llm_client
        self.mcp_client = mcp_client
        self.memory_manager = memory_manager
        self.max_step = max_step

    async def run_stream(self,question: str,authorization: str,conversation_id: str = None):
        #根据authorization获取user_id
        try:
            user_id = get_user_id_from_token(authorization)
        except ValueError as e:
            yield {
                "type": "error",
                "message": str(e)
            }
            return

        #用户会话鉴权
        if conversation_id is not None and not await self.memory_manager.conversation_authorization(conversation_id,user_id):
            yield {
                "type": "error",
                "message": "不可访问他人会话！！！"
            }
            return
        # 从数据库读取会话摘要和最近历史
        history = []
        summary = None

        if conversation_id is not None:
            summary = await self.memory_manager.get_conversation_summary(
                conversation_id
            )

            history = await self.memory_manager.get_conversation_memory(
                conversation_id
            )

        prompt = PROMPT_TEMPLATE.format(
            summary=summary or "暂无历史摘要",
            history=history
        )

        tools = await self.mcp_client.tool_list()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": question}
        ]
        async for event in self.run_loop(messages,tools,authorization,conversation_id,question,user_id):
            yield event


    #进行agent循环思考和调用
    async def run_loop(self,messages,tools,authorization,conversation_id,question,user_id):
        current_step = 0
        while current_step < self.max_step:
            current_step += 1
            print(f"-----第{current_step}步-----")
            content = ""
            content_chunks = []
            tool_calls = []
            has_tool_call = False
            # 生成器获取大模型的返回信息
            yield {
                "type": "status",
                "content": "思考中..."
            }
            try:
                for response in self.llm_client.think(messages, tools):
                    response_type = response["type"]
                    # 如果是返回的内容先进行存储
                    if response_type == "content":
                        content += response["content"]
                        content_chunks.append(response)

                    # 如果返回的错误类型
                    elif response_type == "error":
                        yield response
                        return

                    # 如果返回的是最后的工具调用(进行对应的tool_calling流程)
                    elif response_type == "tool_call":
                        tool_calls = response["tool_calls"]
                        has_tool_call = True
            except Exception as e:
                yield {
                    "type": "error",
                    "message": f"模型调用失败:{str(e)}"
                }
                return

            # 如果没有调用工具的话,说明已经完成了回答
            if not has_tool_call:
                if conversation_id is None:
                    conversation_id = await self.memory_manager.create_conversation(self.llm_client.generate_title(question), user_id)
                # 得出结论，进行会话记忆 (question为None的时候是在用户确认调用需要确认工具时的)
                if question is not None:
                    await self.memory_manager.add_conversation_message(conversation_id, "user", question)
                await self.memory_manager.add_conversation_message(conversation_id, "assistant", content)
                # 将结果返回给前端
                for chunk in content_chunks:
                    yield chunk
                yield {
                    "type": "done"
                }
                try:
                    # 判断当前会话记忆是否需要进行摘要
                    count = await self.memory_manager.get_unsummarized_message_count(conversation_id)
                    if count >= 20:
                        # 先获取进行摘要的内容
                        existing_summary = await self.memory_manager.get_conversation_summary(conversation_id)
                        conversation = await self.memory_manager.get_unsummarized_messages(conversation_id)
                        # 用内置llm生成摘要
                        summary = self.llm_client.generate_summary(existing_summary,conversation)
                        await self.memory_manager.update_conversation_summary(conversation_id, summary)
                except Exception as e:
                    # 摘要错误，进行日志记录
                    pass
                return
            yield {
                "type": "status",
                "content": "调用工具中..."
            }
            # 否则进行调用工具
            assistant_tool_message = {
                "role": "assistant",
                "content": content or "",
                "tool_calls": []
            }
            # 依照官方api流程，先传入需要调用的工具信息
            for tool in tool_calls:
                assistant_tool_message["tool_calls"].append({
                    "id": tool["id"],
                    "type": tool["type"],
                    "function": {
                        "name": tool["name"],
                        "arguments": tool["arguments"]
                    }
                })
            messages.append(assistant_tool_message)
            # 分批调用工具获取结果
            for tool in tool_calls:
                tool_name = tool["name"]
                arguments = json.loads(tool["arguments"])
                if tool_name in confirmation_tools_name:
                    run_id = str(uuid4())
                    pending_run[run_id] = {
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "messages": messages,
                        "tools": tools,
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "tool_call_id": tool["id"],
                    }
                    yield {
                        "type": "confirmation_information",
                        "content": content
                    }
                    yield {
                        "type": "confirmation_required",
                        "run_id": run_id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "conversation_id": conversation_id,
                        "message": "该操作需要用户确认"
                    }
                    return
                try:
                    result = await self.mcp_client.call_tool(tool_name, arguments, authorization)
                except Exception as e:
                    result = {
                        "message": f"工具调用失败: {str(e)}"
                    }
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool["id"],
                    "content": json.dumps(result, ensure_ascii=False)
                })
        yield {
            "type": "error",
            "message": "超过最大推理次数"
        }

    #判断是否执行确认性工具
    async def confirm_run(self,run_id: str,approved: bool,authorization: str):
        run = pending_run.get(run_id)
        if run is None:
            yield {
                "type": "error",
                "message": "该工具调用不存在或已经失效"
            }
            return
        user_id = run["user_id"]
        authorization_user_id = get_user_id_from_token(authorization)
        if authorization_user_id != user_id:
            yield {
                "type": "error",
                "message": "你无权操作他人的任务决策"
            }
            return
        messages = run["messages"]
        tools = run["tools"]
        conversation_id = run["conversation_id"]
        #用户拒绝
        if not approved:
            pending_run.pop(run_id,None)
            messages.append({
                "role": "user",
                "content": "用户拒绝执行刚才的请求，该工具调用未执行，请根据这个结果继续回答用户"
            })
            async for event in self.run_loop(messages,tools,authorization,conversation_id,None,user_id):
                yield event
            return
        #用户同意
        tool_name = run["tool_name"]
        arguments = run["arguments"]
        try:
            print(arguments)
            result = await self.mcp_client.call_tool(tool_name,arguments,authorization)
            tool_call_id = run["tool_call_id"]
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result
            })
            async for event in self.run_loop(messages,tools,authorization,conversation_id,None,user_id):
                yield event
        #最后无论是否调用成功都弹出这个任务
        finally:
            pending_run.pop(run_id,None)


