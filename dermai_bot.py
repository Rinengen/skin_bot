import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, ConversationHandler
)

# =============================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# =============================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =============================
# ВОПРОСЫ ТЕСТА (по Бауманн)
# =============================
# =============================
# ВОПРОСЫ (с вариантами A/B)
# =============================

QUESTIONS = [
    # 1️⃣ OILY vs DRY
    ("O/D", "1️⃣ Как часто ваша кожа блестит в течение дня?", {
        "A": "Блестит уже к обеду, особенно в Т-зоне",
        "B": "Почти не блестит, даже к вечеру"
    }),
    ("O/D", "2️⃣ Как выглядят ваши поры?", {
        "A": "Расширенные, особенно на носу и лбу",
        "B": "Мелкие или почти незаметные"
    }),
    ("O/D", "3️⃣ Как кожа ощущается после умывания?", {
        "A": "Через час — как обычно, без стянутости",
        "B": "Чувствуется сухость или стянутость"
    }),
    ("O/D", "4️⃣ Как часто появляются прыщи или чёрные точки?", {
        "A": "Регулярно, особенно в Т-зоне",
        "B": "Редко или почти никогда"
    }),

    # 2️⃣ SENSITIVE vs RESISTANT
    ("S/R", "5️⃣ Реагирует ли кожа покраснением, зудом или жжением на косметику?", {
        "A": "Да, часто",
        "B": "Почти никогда"
    }),
    ("S/R", "6️⃣ Краснеет ли кожа от ветра, холода или горячей воды?", {
        "A": "Да, легко краснеет",
        "B": "Нет, остаётся спокойной"
    }),
    ("S/R", "7️⃣ Можете ли использовать кислоты (AHA/BHA) или ретинол без раздражения?", {
        "A": "Нет, вызывают жжение или шелушение",
        "B": "Да, без проблем"
    }),
    ("S/R", "8️⃣ Есть ли у вас розацеа, купероз или хроническое раздражение?", {
        "A": "Да",
        "B": "Нет"
    }),

    # 3️⃣ PIGMENTED vs NON-PIGMENTED
    ("P/N", "9️⃣ Остаются ли тёмные пятна после прыщей?", {
        "A": "Да, надолго",
        "B": "Нет, кожа быстро выравнивается"
    }),
    ("P/N", "🔟 Есть ли веснушки или пигментные пятна?", {
        "A": "Да",
        "B": "Нет"
    }),
    ("P/N", "1️⃣1️⃣ Темнеет ли кожа после воспалений или царапин?", {
        "A": "Да",
        "B": "Нет"
    }),
    ("P/N", "1️⃣2️⃣ Используете ли вы осветляющие средства?", {
        "A": "Да, регулярно",
        "B": "Нет, не использую"
    }),

    # 4️⃣ WRINKLE-PRONE vs TIGHT
    ("W/T", "1️⃣3️⃣ Есть ли у вас морщины в покое (не при мимике)?", {
        "A": "Да, особенно вокруг глаз или на лбу",
        "B": "Нет или почти незаметны"
    }),
    ("W/T", "1️⃣4️⃣ Кожа кажется тонкой/дряблой или плотной/упругой?", {
        "A": "Тонкая, дряблая",
        "B": "Плотная, эластичная"
    }),
    ("W/T", "1️⃣5️⃣ Быстро ли возвращается кожа в форму после щипка?", {
        "A": "Медленно",
        "B": "Сразу"
    }),
    ("W/T", "1️⃣6️⃣ Вы выглядите старше своего возраста?", {
        "A": "Да, старше",
        "B": "Нет, моложе или ровно по возрасту"
    })
]

Q_STATE = range(1)


# =============================
# СТАРТ
# =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для определения типа кожи по системе Бауманн.\n"
        "Чтобы пройти тест, напиши /test"
    )

# =============================
# НАЧАЛО ТЕСТА
# =============================
async def test_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["answers"] = []
    context.user_data["index"] = 0
    await ask_question(update, context)
    return Q_STATE

# =============================
# ВОПРОС С ВАРИАНТАМИ
# =============================
async def ask_question(update_or_query, context):
    idx = context.user_data["index"]
    category, question, options = QUESTIONS[idx]

    buttons = [
        [InlineKeyboardButton(text=f"A: {options['A']}", callback_data="A")],
        [InlineKeyboardButton(text=f"B: {options['B']}", callback_data="B")]
    ]
    markup = InlineKeyboardMarkup(buttons)

    text = f"{question}\n\nВыберите вариант:"
    if hasattr(update_or_query, "message"):
        await update_or_query.message.reply_text(text, reply_markup=markup)
    else:
        await update_or_query.edit_message_text(text, reply_markup=markup)

# =============================
# ОБРАБОТКА ОТВЕТА
# =============================
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ans = query.data
    idx = context.user_data["index"]
    category, question, options = QUESTIONS[idx]
    context.user_data["answers"].append((category, ans))
    context.user_data["index"] += 1

    if context.user_data["index"] >= len(QUESTIONS):
        result = classify_baumann(context.user_data["answers"])
        await query.edit_message_text(
            f"✅ Тест завершён!\n\nВаш тип кожи: *{result['code']}*\n\n{result['desc']}",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    else:
        await ask_question(query, context)
        return Q_STATE

# =============================
# КЛАССИФИКАЦИЯ
# =============================
def classify_baumann(answers):
    summary = {"O/D": [], "S/R": [], "P/N": [], "W/T": []}
    for cat, ans in answers:
        summary[cat].append(ans)

    result = {}
    code = ""

    # 1. Жирность
    od = summary["O/D"]
    result["O/D"] = "O" if od.count("A") > od.count("B") else ("D" if od.count("B") > od.count("A") else od[-1].replace("A", "O").replace("B", "D"))

    # 2. Чувствительность
    sr = summary["S/R"]
    result["S/R"] = "S" if sr.count("A") > sr.count("B") else ("R" if sr.count("B") > sr.count("A") else sr[-1].replace("A", "S").replace("B", "R"))

    # 3. Пигментация
    pn = summary["P/N"]
    result["P/N"] = "P" if pn.count("A") > pn.count("B") else ("N" if pn.count("B") > pn.count("A") else pn[-1].replace("A", "P").replace("B", "N"))

    # 4. Старение
    wt = summary["W/T"]
    result["W/T"] = "W" if wt.count("A") > wt.count("B") else ("T" if wt.count("B") > wt.count("A") else wt[-1].replace("A", "W").replace("B", "T"))

    code = result["O/D"] + result["S/R"] + result["P/N"] + result["W/T"]
    desc = explain_skin_type(code)
    return {"code": code, "desc": desc}

# =============================
# ТЕКСТОВОЕ ОБЪЯСНЕНИЕ
# =============================
def explain_skin_type(code: str) -> str:
    explanations = {
        "O": "Жирная", "D": "Сухая",
        "S": "Чувствительная", "R": "Устойчивая",
        "P": "Пигментированная", "N": "Без склонности к пигментации",
        "W": "Склонна к морщинам", "T": "Плотная/упругая"
    }
    parts = [explanations.get(c, "") for c in code]
    return f"Тип кожи: {', '.join(parts)}."

# =============================
# MAIN
# =============================
def main():
    application = ApplicationBuilder().token("8240689092:AAHsXDuEKVN74l2Z4yu_8khC6HqhV8gcOMo").build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("test", test_start)],
        states={Q_STATE: [CallbackQueryHandler(handle_answer, pattern="^(A|B)$")],
        },
        fallbacks=[],
        per_message=False,   # важно: сохраняет контекст между callback
    )


    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv)

    print("Бот запущен 🚀")
    application.run_polling()

if __name__ == "__main__":
    main()