from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from utils.test import SkinTest
from utils.dataset_csv import (
    save_initial_data,
    save_test_results,
    save_dermatoscopy_result,
    get_patient_json
)
import asyncio
import os
import json
import uuid
from datetime import datetime

REPORTS_DIR = "reports"
CONSENT, DEMO, Q_STATE, TIME_OF_YEAR = range(4)


class SkinBot:
    def __init__(self, token):
        self.token = token
        self.test = SkinTest()
        self.questions = self.test.questions
        os.makedirs(REPORTS_DIR, exist_ok=True)

    # =============================================================
    # ЭТАП 0: СТАРТ
    # =============================================================

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [
            [InlineKeyboardButton("🧪 Пройти тест", callback_data="start_test")]
        ]
        markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(
            "👋 Здравствуйте!\n\n"
            "Это AI-ассистент для подбора уходовой косметики по типу кожи.\n\n"
            "Пожалуйста, следуйте инструкции, чтобы получить персональные рекомендации.",
            reply_markup=markup
        )

    async def handle_start_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        return await self.consent_start(update, context)

    # =============================================================
    # ЭТАП 1: СОГЛАСИЕ И АНКЕТА
    # =============================================================

    async def consent_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [
            [InlineKeyboardButton("✅ Да", callback_data="yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="no")]
        ]
        markup = InlineKeyboardMarkup(buttons)
        msg = (
            "🧩 Мы собираем анонимные данные для улучшения рекомендаций.\n"
            "Вы согласны принять участие?"
        )
        if hasattr(update, "callback_query"):
            await update.callback_query.edit_message_text(msg, reply_markup=markup)
        else:
            await update.message.reply_text(msg, reply_markup=markup)
        return CONSENT

    async def handle_consent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "no":
            await query.edit_message_text(
                "❌ Спасибо за уделенное время, тест отменён в связи с желанием пациента. До встречи!\n"
                "Чтобы перезапустить бота и начать заново - введите команду: /start \n"
            )
            return ConversationHandler.END

        buttons = [
            [InlineKeyboardButton("Мужсой", callback_data="М")],
            [InlineKeyboardButton("Женский", callback_data="Ж")]
        ]
        await query.edit_message_text("Укажите ваш пол:", reply_markup=InlineKeyboardMarkup(buttons))
        return DEMO

    async def handle_demo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # --- Выбор пола ---
        if "sex" not in context.user_data:
            query = update.callback_query
            await query.answer()
            context.user_data["sex"] = query.data
            await query.edit_message_text("Введите ваш возраст (число от 0 до 120):")
            return DEMO

        # --- Ввод возраста ---
        elif "age" not in context.user_data:
            try:
                age = int(update.message.text)
            except ValueError:
                await update.message.reply_text("⚠️ Пожалуйста, введите число.")
                return DEMO

            if not (0 <= age <= 120):
                await update.message.reply_text("⚠️ Возраст должен быть в диапазоне 0–120. Попробуйте снова:")
                return DEMO

            context.user_data["age"] = age
            await update.message.reply_text("Укажите аллергии (если нет — напишите 'нет'):")
            return DEMO

        # --- Ввод аллергий ---
        else:
            context.user_data["allergies"] = update.message.text.strip() or "нет"
            context.user_data["id_patient"] = str(uuid.uuid4())
            context.user_data["answers_json"] = {}
            context.user_data["index"] = 0

            # --- Сохраняем начальные данные в CSV ---
            await save_initial_data(
                id_patient=context.user_data["id_patient"],
                age=context.user_data["age"],
                sex=context.user_data["sex"],
                allergies=context.user_data["allergies"]
            )

            # --- Переход к первому вопросу теста ---
            await update.message.reply_text(
                "Переходим к сокращенному тесту Лесли Баумна (модернизированный)."
            )
            await self.ask_question(update, context)
            return Q_STATE

    # =============================================================
    # ЭТАП 2: ТЕСТ БАУМАН
    # =============================================================

    async def ask_question(self, update_or_query, context):
        idx = context.user_data["index"]
        category, question, options = self.questions[idx]

        buttons = [
            [InlineKeyboardButton(f"A: {options['A']}", callback_data="A")],
            [InlineKeyboardButton(f"B: {options['B']}", callback_data="B")]
        ]
        markup = InlineKeyboardMarkup(buttons)
        # Если есть заметка, добавляем её
        note_text = options.get("note", "")
        text = f"{question}\n\n{note_text}\n\nВыберите вариант:"

        if hasattr(update_or_query, "message"):
            await update_or_query.message.reply_text(text, reply_markup=markup)
        else:
            await update_or_query.edit_message_text(text, reply_markup=markup)

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        ans = query.data

        idx = context.user_data["index"]
        category, _, _ = self.questions[idx]
        context.user_data["answers_json"][category] = ans
        context.user_data["index"] += 1

        # если тест закончен
        if context.user_data["index"] >= len(self.questions):
            answers_list = list(context.user_data["answers_json"].items())
            result = self.test.classify_baumann(answers_list)
            context.user_data["skin_code"] = result["code"]

            # --- Уточняющий вопрос о времени года ---
            buttons = [
                [InlineKeyboardButton("Осень/Зима", callback_data="Осень/Зима")],
                [InlineKeyboardButton("Весна/Лето", callback_data="Весна/Лето")]
            ]
            await query.edit_message_text(
                f"✅ Тест завершён!\n\nТип кожи: *{result['code']}*\n{result['desc']}\n\n"
                "📌 В какое время года планируется использовать уходовую косметику?",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
            return TIME_OF_YEAR
        else:
            await self.ask_question(query, context)
            return Q_STATE

    # =============================================================
    # ЭТАП 2.5: УТОЧНЕНИЕ ВРЕМЕНИ ГОДА
    # =============================================================

    async def handle_time_of_year(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        season = query.data

        context.user_data["time_of_year"] = season
        id_patient = context.user_data.get("id_patient")
        if id_patient:
            await save_test_results(
                id_patient=id_patient,
                answers_json=json.dumps(context.user_data["answers_json"], ensure_ascii=False),
                skin_code=context.user_data["skin_code"],
                time_of_year=season
            )

        await query.edit_message_text(
            f"✅ Сезон выбран: *{season}*\n\nТеперь можно перейти к анализу фото.",
            parse_mode="Markdown"
        )

        buttons = [[InlineKeyboardButton("📸 Провести анализ фото", callback_data="photo_stage")]]
        await query.message.reply_text("Следующий шаг:", reply_markup=InlineKeyboardMarkup(buttons))
        return ConversationHandler.END

    # =============================================================
    # ЭТАП 3: АНАЛИЗ ФОТО (симуляция дерматоскопии)
    # =============================================================

    async def handle_photo_stage(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        id_patient = context.user_data.get("id_patient")
        if not id_patient:
            await query.message.reply_text("⚠️ Сначала пройдите тест.")
            return

        await query.edit_message_text("📸 Эмулируем получение фото дерматоскопа...")
        await asyncio.sleep(1.5)
        await query.message.reply_text("🔍 Анализ изображения...")
        await asyncio.sleep(2.0)

        skin_type_dermatoscopy = "OSPW"
        skin_desc = "Жирная, чувствительная, пигментированная, склонна к морщинам."
        skin_code = context.user_data.get("skin_code")
        comparison = await save_dermatoscopy_result(id_patient, skin_code, skin_type_dermatoscopy)
        match_percent = comparison["match_percent"]
        final_skin_type = comparison["final_skin_type"]

        pdf_path = r"C:\Users\minik\Desktop\dermatoscopy_andery.pdf"
        if not os.path.exists(pdf_path):
            await query.message.reply_text("❌ PDF-файл отчёта не найден на сервере.")
            return

        await query.message.reply_text("📄 Формируем отчёт...")
        await asyncio.sleep(1.0)

        patient_json = get_patient_json(id_patient)

        caption = (
            f"📋 *Результаты анализа:*\n\n"
            f"💠 Тип кожи по тесту: *{context.user_data.get('skin_code', '—')}*\n"
            f"🔬 Тип кожи по дерматоскопии: *{skin_type_dermatoscopy}*\n  {skin_desc}\n"
            f"📊 Совпадение: *{match_percent}%*\n"
            f"✅ Финальный тип кожи: *{final_skin_type}*\n"
            f"*Отладка - посылаемый промт JSON: {patient_json}\n*"
        )

        with open(pdf_path, "rb") as f:
            await query.message.reply_document(document=f, caption=caption, parse_mode="Markdown")

        buttons = [[InlineKeyboardButton("💄 Подобрать уход", callback_data="care_stage")]]
        await query.message.reply_text("Теперь можно подобрать уход:", reply_markup=InlineKeyboardMarkup(buttons))

    # =============================================================
    # ЭТАП 4: ПОДБОР УХОДА (заглушка перед LLM)
    # =============================================================

    async def handle_care_stage(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "🤖 Подбор персонализированного ухода...\n(этап интеграции с LLM)\n"
            "*Это пока заглушка, дальше нет ничего*"
        )

    # =============================================================
    # ЗАПУСК
    # =============================================================

    def run(self):
        from telegram.ext import ApplicationBuilder

        app = ApplicationBuilder().token(self.token).build()

        conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.handle_start_button, pattern="^start_test$")],
            states={
                CONSENT: [CallbackQueryHandler(self.handle_consent, pattern="^(yes|no)$")],
                DEMO: [
                    CallbackQueryHandler(self.handle_demo, pattern="^(М|Ж)$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_demo)
                ],
                Q_STATE: [CallbackQueryHandler(self.handle_answer, pattern="^(A|B)$")],
                TIME_OF_YEAR: [CallbackQueryHandler(self.handle_time_of_year)]
            },
            fallbacks=[],
            per_message=False
        )

        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(conv)
        app.add_handler(CallbackQueryHandler(self.handle_photo_stage, pattern="^photo_stage$"))
        app.add_handler(CallbackQueryHandler(self.handle_care_stage, pattern="^care_stage$"))

        print("Бот запущен 🚀")
        app.run_polling()
