import asyncpg
import json
import asyncio

class DBHandler:
    def __init__(self, config):
        """
        config = {
            "user": "postgres",
            "password": "dermai",
            "database": "dermai_assistant_bot",
            "host": "127.0.0.1",
            "port": 5432
        }
        """
        self.config = config
        self.pool = None

    async def init_db(self):
        """Создает подключение к базе и таблицу patients, если её нет"""
        self.pool = await asyncpg.create_pool(**self.config)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    id SERIAL PRIMARY KEY,
                    sex CHAR(1),
                    age INT,
                    allergies TEXT,
                    test_answers JSONB,
                    test_result VARCHAR(10)
                );
            """)
        print("✅ Таблица patients готова")

    async def create_patient_initial(self, sex: str, age: int, allergies: str) -> int:
        """
        Создает пациента с начальными данными
        Возвращает id нового пациента
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO patients (sex, age, allergies)
                VALUES ($1, $2, $3)
                RETURNING id;
            """, sex, age, allergies)
            return result["id"]

    async def save_test_results(self, patient_id: int, answers: dict, result: str):
        """
        Сохраняет ответы теста и итоговый результат кожи
        answers: словарь {категория: ответ, ...}
        result: итоговый код типа кожи (например "OSPW")
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE patients
                SET test_answers = $1,
                    test_result = $2
                WHERE id = $3;
            """, json.dumps(answers), result, patient_id)

# ================================
# Пример использования (для теста)
# ================================
if __name__ == "__main__":
    DB_CONFIG = {
        "user": "postgres",
        "password": "dermai",
        "database": "dermai_assistant_bot",
        "host": "127.0.0.1",
        "port": 5432
    }

    async def main():
        db = DBHandler(DB_CONFIG)
        await db.init_db()
        patient_id = await db.create_patient_initial("М", 25, "Нет")
        print(f"Создан пациент с id={patient_id}")
        await db.save_test_results(patient_id, {"O/D": "O", "S/R": "S"}, "OS")
        print("Сохранили тестовые ответы и результат")

    asyncio.run(main())
