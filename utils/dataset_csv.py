import csv
import asyncio
import os
import json

CSV_FILE = "patients.csv"

# --- Единая структура полей ---
HEADERS = [
    "id_patient",
    "age",
    "sex",
    "allergies",
    "answers_json",
    "skin_code",
    "skin_type_dermatoscopy",
    "match_percent",
    "final_skin_type",
    "time_of_year"
]

LOCK = asyncio.Lock()

# --- Инициализация CSV ---
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()

# ===============================================================
#                        ФУНКЦИИ СОХРАНЕНИЯ
# ===============================================================

async def save_initial_data(id_patient: str, age: int, sex: str, allergies: str):
    """Создание новой записи при старте диалога."""
    async with LOCK:
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writerow({
                "id_patient": id_patient,
                "age": age,
                "sex": sex,
                "allergies": allergies,
                "answers_json": "",
                "skin_code": "",
                "skin_type_dermatoscopy": "",
                "match_percent": "",
                "final_skin_type": "",
                "time_of_year": ""
            })


async def save_test_results(id_patient: str, answers_json: str, skin_code: str, time_of_year: str = ""):
    """Сохранение результатов теста."""
    async with LOCK:
        rows = []
        with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        updated = False
        for row in rows:
            if row.get("id_patient") == id_patient:
                row["answers_json"] = answers_json
                row["skin_code"] = skin_code
                if time_of_year:
                    row["time_of_year"] = time_of_year
                updated = True
                break

        if not updated:
            rows.append({
                "id_patient": id_patient,
                "age": "",
                "sex": "",
                "allergies": "",
                "answers_json": answers_json,
                "skin_code": skin_code,
                "skin_type_dermatoscopy": "",
                "match_percent": "",
                "final_skin_type": "",
                "time_of_year": time_of_year
            })

        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)


async def save_dermatoscopy_result(id_patient, skin_code, skin_type_dermatoscopy):
    """Сохранение результатов анализа по фото и автоматическое вычисление совпадения."""
    async with LOCK:
        rows = []
        with open(CSV_FILE, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        found = False
        comparison = {"match_percent": 0, "final_skin_type": skin_type_dermatoscopy}
        for row in rows:
            if row["id_patient"] == id_patient:
                row["skin_type_dermatoscopy"] = skin_type_dermatoscopy
                comparison = compare_skin_types(skin_code, skin_type_dermatoscopy)
                row["match_percent"] = comparison["match_percent"]
                row["final_skin_type"] = comparison["final_skin_type"]
                found = True
                break

        if not found:
            comparison = compare_skin_types("", skin_type_dermatoscopy)
            rows.append({
                "id_patient": id_patient,
                "age": "",
                "sex": "",
                "allergies": "",
                "answers_json": "",
                "skin_code": "",
                "skin_type_dermatoscopy": skin_type_dermatoscopy,
                "match_percent": comparison["match_percent"],
                "final_skin_type": comparison["final_skin_type"],
                "time_of_year": ""
            })

        with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)

        return comparison  # 🔥 Возвращаем результат сразу


# ===============================================================
#                  АНАЛИТИКА И ФИНАЛЬНЫЙ ТИП КОЖИ
# ===============================================================
def compare_skin_types(skin_code: str, skin_type_dermatoscopy: str) -> dict:
    """
    Сравнивает тип кожи по тесту и по дерматоскопии посимвольно.
    Возвращает процент совпадения и финальный тип кожи.
    
    Логика:
    - Для каждой позиции из 4 символов:
        - Если символы совпадают, увеличиваем счётчик совпадений и добавляем этот символ в финальный код
        - Если нет — добавляем символ из дерматоскопии
    - match_percent = (совпадения / 4) * 100
    """
    # Очистка входных данных
    s1 = (skin_code or "").strip().upper()[:4]
    s2 = (skin_type_dermatoscopy or "").strip().upper()[:4]

    # Если один из кодов пустой, финальный тип = непустой, совпадение = 0%
    if not s1:
        return {"match_percent": 0, "final_skin_type": s2}
    if not s2:
        return {"match_percent": 0, "final_skin_type": s1}

    matches = 0
    final_type = []

    for i, (c_test, c_derm) in enumerate(zip(s1, s2)):
        if c_test == c_derm:
            matches += 1
            final_type.append(c_test)
        else:
            final_type.append(c_derm)

    match_percent = round((matches / 4) * 100, 2)
    final_skin_type = "".join(final_type)

    # Для дебага: выводим в консоль
    print(f"[DEBUG] test: {s1}, derm: {s2}, matches: {matches}, final: {final_skin_type}, %: {match_percent}")

    return {"match_percent": match_percent, "final_skin_type": final_skin_type}



# ===============================================================
#                КОНВЕРТАЦИЯ В JSON ДЛЯ LLM/RAG
# ===============================================================

def get_patient_json(id_patient: str) -> str:
    """Возвращает JSON с финальными полями для LLM/RAG."""
    final_fields = ["age", "sex", "allergies", "final_skin_type", "time_of_year"]
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["id_patient"] == id_patient:
                # Формируем словарь только с нужными полями
                filtered = {k: row[k] for k in final_fields}
                return json.dumps(filtered, ensure_ascii=False, indent=2)
    return "{}"

