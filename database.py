import asyncpg
import time
import ssl

class Database:
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None

    async def setup(self):
        """Инициализация пула соединений и создание таблиц"""
        # Настройка SSL для безопасного подключения к Neon.tech
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            # Создаем пул соединений с использованием SSL
            self.pool = await asyncpg.create_pool(self.db_url, ssl=ctx)
            
            async with self.pool.acquire() as conn:
                # Создаем таблицу пользователей, если она еще не существует
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        uuid TEXT,
                        email TEXT,
                        expiry_date BIGINT,
                        is_active INTEGER DEFAULT 1
                    )
                ''')
            print("База данных PostgreSQL успешно инициализирована.")
        except Exception as e:
            print(f"Ошибка при настройке базы данных: {e}")
            raise e

    async def add_or_update_user(self, user_id, uuid, email, days=30):
        """Добавление нового пользователя или продление существующего"""
        expiry_add = days * 86400
        now = int(time.time())
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, uuid, email, expiry_date) 
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(user_id) DO UPDATE SET 
                expiry_date = CASE 
                    WHEN users.expiry_date > $5 THEN users.expiry_date + $6 
                    ELSE $5 + $6 
                END, 
                is_active = 1
            ''', user_id, uuid, email, now + expiry_add, now, expiry_add)

    async def get_expired_users(self):
        """Получение списка пользователей, у которых истек срок подписки"""
        async with self.pool.acquire() as conn:
            # Возвращает список записей (как словари)
            rows = await conn.fetch(
                'SELECT user_id, email FROM users WHERE expiry_date < $1 AND is_active = 1', 
                int(time.time())
            )
            return rows

    async def set_inactive(self, user_id):
        """Деактивация пользователя в базе данных"""
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE users SET is_active = 0 WHERE user_id = $1', user_id)

    async def get_user_status(self, user_id):
        """Получение данных о подписке конкретного пользователя"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT expiry_date, is_active FROM users WHERE user_id = $1', 
                user_id
            )
