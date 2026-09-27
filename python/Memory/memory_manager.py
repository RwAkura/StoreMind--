import uuid
from agent.database import Database
class MemoryManager:
    def __init__(self,database:Database):
        self.database = database

    #创建新会话
    async def create_conversation(self,title: str,user_id: int):
        conversation_id = str(uuid.uuid4())
        sql = "insert into conversation(conversation_id,title,user_id) values($1,$2,$3)"
        async with self.database.pool.acquire() as conn:
            await conn.execute(sql,conversation_id,title,user_id)
        return conversation_id

    #获取会话记忆
    async def get_conversation_memory(self,conversation_id: str,limit: int = 20):
        sql = "select * from conversation_message where conversation_id = $1 order by create_time desc limit $2"
        async with self.database.pool.acquire() as conn:
            rows = await conn.fetch(sql,conversation_id,limit)
        rows = list(reversed(rows))
        return [
            {
                "role": row['role'],
                "content": row['content']
            }
            for row in rows
        ]

    #向数据库添加新记忆
    async def add_conversation_message(self,conversation_id: str,role: str,content: str):
        message_sql = "insert into conversation_message(conversation_id,role,content) values($1,$2,$3)"
        conversation_sql = "update conversation set update_time = CURRENT_TIMESTAMP where conversation_id = $1"
        async with self.database.pool.acquire() as conn:
            await conn.execute(message_sql,conversation_id,role,content)
            await conn.execute(conversation_sql,conversation_id)

    #校验指定会话是否属于当前用户，防止越权访问
    async def conversation_authorization(self,conversation_id: str,user_id: int):
        sql = "select 1 from conversation where conversation_id = $1 and user_id = $2"
        async with self.database.pool.acquire() as conn:
            row = await conn.fetchrow(sql,conversation_id,user_id)
        return True if row else False

    #获取用户的会话列表
    async def get_conversation_list(self,user_id: int):
        sql = "select * from conversation where user_id = $1 order by create_time desc"
        async with self.database.pool.acquire() as conn:
            rows = await conn.fetch(sql,user_id)
        return [
            {
                "conversation_id": row["conversation_id"],
                "title": row["title"],
                "create_time": row["create_time"],
                "update_time": row["update_time"],
            }
            for row in rows
        ]

    #获取会话摘要
    async def get_conversation_summary(self,conversation_id: str):
        sql = "select summary from conversation where conversation_id = $1"
        async with self.database.pool.acquire() as conn:
            row = await conn.fetchrow(sql,conversation_id)
        if row is None:
            return None
        return row["summary"]

    #更新会话摘要
    async def update_conversation_summary(self,conversation_id: str,summary: str):
        sql = "update conversation set summary = $1 where conversation_id = $2"
        async with self.database.pool.acquire() as conn:
            await conn.execute(sql,conversation_id,summary)

    #获取当前会话还未进行摘要的消息
    async def get_unsummarized_message_count(self, conversation_id: str):
        sql = "select count(*) from conversation_message where conversation_id = $1 and is_summarized = false"
        async with self.database.pool.acquire() as conn:
            count = await conn.fetchval(sql, conversation_id)
        return count

    #获取本次进行摘要的消息
    async def get_unsummarized_messages(self,conversation_id: str,count: int = 20):
        sql = "select * from conversation_message where conversation_id = $1 and is_summarized = false order by create_time desc limit $2"
        async with self.database.pool.acquire() as conn:
            rows = await conn.fetch(sql,conversation_id,count)
        return [
            {
                "role": row["role"],
                "content": row["content"]
            }
            for row in rows
        ]
