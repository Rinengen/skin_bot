import csv
import asyncio
import os
import json

CSV_FILE = "patients.csv"
HEADERS = ["id_patient", "age", "sex", "allergies", "answers_json", "skin_code"]

# Глобальный Lock для асинхронной записи
LOCK = asyncio.Lock()

# Создаем файл с заголовком, если его нет
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()

async def save_initial_data(id_patient: str, age: int, sex: str, allergies: str):
    """Сохраняем базовые данные пациента."""
    async with LOCK:
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writerow({
                "id_patient": id_patient,
                "age": age,
                "sex": sex,
                "allergies": allergies,
                "answers_json": "",  # пока пусто
                "skin_code": ""
            })

async def save_test_results(id_patient: str, answers_json: str, skin_code: str):
    """Обновляем результаты теста для пациента."""
    async with LOCK:
        rows = []
        # Читаем все строки
        with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Обновляем конкретного пациента
        updated = False
        for row in rows:
            if row.get("id_patient") == id_patient:
                row["answers_json"] = answers_json
                row["skin_code"] = skin_code
                updated = True
                break

        if not updated:
            # На всякий случай: если пациента нет, добавляем
            rows.append({
                "id_patient": id_patient,
                "age": "",
                "sex": "",
                "allergies": "",
                "answers_json": answers_json,
                "skin_code": skin_code
            })

        # Записываем обратно
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)

            
async def save_dermatoscopy_result(id_patient, skin_type):
    """Добавление результата дерматоскопического анализа"""
    async with LOCK:
        rows = []
        with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in rows:
            if row.get("id_patient") == id_patient:
                row["skin_type_dermatoscopy"] = skin_type
                break

        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)