import os
from openai import OpenAI

GENERATE_TITLE_PROMPT = """
    你是一个标题生成助手
    根据用户的问题生成一个简短的会话标题。
    要求:
    1. 不超过15个字
    2. 不要加引号
    3. 直接返回标题
"""

SUMMARY_PROMPT = """
你是一个门店经营管理智能助手的对话记忆整理模块。

你的任务是：根据已有的历史摘要和需要压缩的历史对话，生成一份新的对话摘要。
这份摘要会作为后续对话的长期记忆，因此应该保留对未来回答有价值的信息，而不是简单复述聊天内容。

请遵循以下规则：

1. 保留重要的业务事实
   - 门店信息
   - 商品信息
   - 库存信息
   - 销售数据
   - 订单信息
   - 用户提出的业务需求
   - 已经执行或确认的业务操作
   - 工具调用得到的重要结果

2. 保留对后续对话有帮助的上下文
   - 用户正在解决的问题
   - 已经讨论过的方案
   - 已经确定的结论
   - 用户提出但尚未解决的问题
   - 后续可能需要继续处理的事项

3. 对重复信息进行合并，不要机械重复相同内容。

4. 删除没有长期价值的信息
   - 普通寒暄
   - 无意义的闲聊
   - 重复的确认信息
   - 与门店经营无关的内容

5. 不要编造任何信息。
   摘要中的所有事实都必须能够从已有摘要或历史对话中找到依据。

6. 如果已有摘要存在，请在已有摘要的基础上吸收新的历史对话。
   不要只总结新的历史对话而丢失已有摘要中的重要信息。

7. 摘要应该简洁、结构清晰，方便另一个 AI 在后续对话中快速理解上下文。

8. 不要输出分析过程，不要解释你是如何总结的，只输出最终摘要。

已有摘要：
{existing_summary}

需要压缩的历史对话：
{conversation}

请输出新的对话摘要。
"""

class LLMClient:

    def __init__(self,model: str = None,api_key: str = None,base_url: str = None,timeout:int = 60):
        self.model = model or "deepseek-chat"
        api_key = api_key or os.environ.get("deepseek_key")
        base_url = base_url or "https://api.deepseek.com"
        self.client = OpenAI(api_key=api_key,base_url=base_url,timeout=timeout)

    def think(self,messages: list[dict[str,str]],tools: list[dict],temperature: float = 0) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                tools=tools,
                stream=True,
            )
            print(f"✅{self.model}响应成功")
            tool_calls = {}
            for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield {
                        "type": "content",
                        "content": delta.content
                    }
                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        index = tool_call.index
                        if index not in tool_calls:
                            tool_calls[index] = {
                                "id": "",
                                "type": "function",
                                "name": "",
                                "arguments": ""
                            }
                        if tool_call.id:
                            tool_calls[index]["id"] = tool_call.id
                        if tool_call.type:
                            tool_calls[index]["type"] = tool_call.type
                        if tool_call.function:
                            if tool_call.function.name:
                                tool_calls[index]["name"] = tool_call.function.name
                            if tool_call.function.arguments:
                                tool_calls[index]["arguments"] += tool_call.function.arguments
            if tool_calls:
                yield {
                    "type": "tool_call",
                    "tool_calls": list(tool_calls.values()),
                }
        except Exception as e:
            print(f"调用{self.model}时发生错误:{e}")
            yield {
                "type": "error",
                "message": str(e)
            }

    def generate_summary(self,existing_summary: str,conversation: list[dict[str,str]]):
        conversation_text = [
            f"{message['role']}: {message['content']}"
            for message in conversation
        ]
        messages = [
            {"role": "system", "content": SUMMARY_PROMPT.format(
                    existing_summary=existing_summary if existing_summary else "",
                    conversation=conversation_text
                )
            },
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content


    def generate_title(self,question: str):
        messages = [
            {"role": "system", "content": GENERATE_TITLE_PROMPT},
            {"role": "user", "content": question},
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content