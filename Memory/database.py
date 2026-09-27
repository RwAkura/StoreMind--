import asyncpg
class Database:
    def __init__(self,
                 host: str = "localhost",
                 port: int = 5432,
                 user: str = "root",
                 password: str = "123456",
                 database: str = "storemind"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            min_size=1,
            max_size=10
        )

    async def close(self):
        if self.pool is not None:
            await self.pool.close()