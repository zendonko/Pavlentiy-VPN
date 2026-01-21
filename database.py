import asyncio
import asyncpg
import time

class Database:
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None

    async def setup(self):
        # Создаем пул соединений
        self.pool = await asyncpg.create_pool(self.db_url)
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    uuid TEXT,
                    email TEXT,
                    expiry_date BIGINT,
                    is_active INTEGER DEFAULT 1
                )
            ''')

    async def add_or_update_user(self, user_id, uuid, email, days=30):
        expiry_add = days * 86400
        new_expiry = int(time.time() + expiry_add)
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, uuid, email, expiry_date) 
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(user_id) DO UPDATE SET 
                expiry_date = users.expiry_date + $5, is_active = 1
            ''', user_id, uuid, email, new_expiry, expiry_add)

    async def get_expired_users(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT user_id, email FROM users WHERE expiry_date < $1 AND is_active = 1', 
                int(time.time())
            )
            return rows

    async def set_inactive(self, user_id):
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE users SET is_active = 0 WHERE user_id = $1', user_id)
