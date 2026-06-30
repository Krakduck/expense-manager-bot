import aiosqlite
import logging
# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class UserDatabase:
    def __init__(self):
        # Определяем путь к БД
        self.db_path = '/data/bot_users.db'  #хостинг
        #self.db_path = 'bot_users.db'       #пк

    async def create_table(self):
        async with aiosqlite.connect(self.db_path) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS users ( 
                                        telegram_id INTEGER PRIMARY KEY,
                                        is_admin BOOLEAN NOT NULL,
                                        username TEXT NOT NULL,
                                        auto_answer TEXT 
                                    )
                                ''')
                await cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS expenses (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        chat_id INTEGER NOT NULL,
                                        buyer_id INTEGER NOT NULL,
                                        amount REAL NOT NULL,
                                        description TEXT,
                                        debtor_id INTEGER, -- Здесь будет ID друга или None (если на всех)
                                        FOREIGN KEY (buyer_id) REFERENCES users (telegram_id),
                                        FOREIGN KEY (debtor_id) REFERENCES users (telegram_id)
                                    ) ''')
                await cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS citation (
                                        telegram_id INTEGER PRIMARY KEY,
                                        text TEXT NOT NULL
                                    ) ''')
                await connection.commit()

    async def add_user(self, telegram_id, is_admin, username,auto_answer ):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                     await cursor.execute(
                         'INSERT INTO users (telegram_id, is_admin, username,auto_answer) VALUES (?, ?, ?,?)',
                         (telegram_id, is_admin, username,auto_answer,)
                     )
                     await connection.commit()
            return True
        except Exception as e:
            logger.info(f"Ошибка добавления: {e}")
            return False

    async def get_user(self, telegram_id):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        'SELECT * FROM users WHERE telegram_id = ?',
                        (telegram_id,)
                    )
                    result =await cursor.fetchone()

            if result:
                logger.info(f"RESULT ИЗ БАЗЫ: {result}")
                return {
                    'telegram_id': result[0],
                    'is_admin': result[1],
                    'username': result[2],
                    'auto_answer':result[3]#на выходе словарь будет
                }
            return None
        except Exception as e:
            logger.info(f"Ошибка поиска: {e}")
            return None

    async def get_user_by_username(self, username):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        'SELECT * FROM users WHERE username = ?',
                        (username,)
                    )
                    result =await cursor.fetchone()

            if result:
                logger.info(f"RESULT ИЗ БАЗЫ: {result}")
                # В result порядок такой же как в CREATE TABLE:
                # (telegram_id, is_admin, username, password)
                return {
                    'telegram_id': result[0],
                }
            return None
        except Exception as e:
            logger.info(f"Ошибка поиска: {e}")
            return None

    async def get_all_users_id(self):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT telegram_id FROM users")
                    data = await cursor.fetchall()

            return [row[0] for row in data]  # Вернет список вида: [djigurda, роман]
        except Exception as e:
            logger.info(f"Ошибка при получении статистики: {e}")
            return []

    async def update_user_param(self, telegram_id, column_name, new_value):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                    query = f"UPDATE users SET {column_name} = ? WHERE telegram_id = ?"
                    await cursor.execute(query, (new_value, telegram_id))
                    await connection.commit()

            return True
        except Exception as e:
            logger.info(f"Ошибка при обновлении {column_name}: {e}")
            return False

    async def delete_user(self, telegram_id):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                    query = f"DELETE FROM users WHERE telegram_id = ?"
                    await cursor.execute(query, (telegram_id,))
                    await connection.commit()

            return True
        except Exception as e:
            logger.info(f"ошибка {telegram_id}: {e}")
            return False

    async def delete_all_users(self):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                    query = f"DELETE FROM users"
                    await cursor.execute(query)
                    await connection.commit()

            return True
        except Exception as e:
            logger.info(f"ошибка:{e}")
            return False



    async def add_transaction(self,chat_id, buyer_id, amount, description, debtor_id):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                     await cursor.execute(
                         'INSERT INTO expenses (chat_id, buyer_id, amount, description, debtor_id) VALUES (?, ?, ?, ?, ?)',
                         (chat_id, buyer_id, amount, description, debtor_id)
                     )
                     await connection.commit()
            return True
        except Exception as e:
            logger.info(f"Ошибка добавления: {e}")
            return False

    async def get_transaction(self,chat_id):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                # Включаем режим, чтобы строки из БД возвращались как словари
                connection.row_factory = aiosqlite.Row
                async with connection.cursor() as cursor:
                    # Запрашиваем ВСЕ поля (*) из таблицы расходов
                    await cursor.execute("SELECT * FROM expenses WHERE chat_id = ?",(chat_id,))
                    data = await cursor.fetchall()
            return data
        except Exception as e:
            logger.info(f"Ошибка при получении транзакций: {e}")
            return []

    async def clear_debt(self,chat_id):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(f"DELETE FROM expenses WHERE chat_id = ?",(chat_id,))
                    await connection.commit()

            return True
        except Exception as e:
            logger.info(f"ошибка:{e}")
            return False



    async def save_citation(self,telegram_id,text):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        'INSERT INTO citations (telegram_id, text) VALUES (?, ?)',
                        (telegram_id,text)
                    )
                    await connection.commit()
            return True
        except Exception as e:
            logger.info(f"<UNK> <UNK> <UNK> <UNK>: {e}")
            return False

    async def get_citation(self, telegram_id):
        try:
            async with aiosqlite.connect(self.db_path) as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        'SELECT * FROM citations WHERE telegram_id = ?',
                        (telegram_id,)
                    )
                    result =await cursor.fetchone()

            if result:
                logger.info(f"RESULT ИЗ БАЗЫ: {result}")
                return {
                    'telegram_id': result[0],
                    'text': result[1],
                }
            return None
        except Exception as e:
            logger.info(f"Ошибка поиска: {e}")
            return None