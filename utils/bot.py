# bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from utils.test import SkinTest
from utils.dataset_csv import save_initial_data, save_test_results
import asyncio
import os
import json
from utils.dataset_csv import save_initial_data, save_test_results, LOCK

import uuid
from datetime import datetime
from utils.dataset_csv import save_dermatoscopy_result


REPORTS_DIR = "reports"

CONSENT, DEMO, Q_STATE = range(3)

class SkinBot:
    def __init__(self, token):
        self.token = token
        self.test = SkinTest()
        self.questions = self.test.questions
        os.makedirs(REPORTS_DIR, exist_ok=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 Привет! Я бот для определения типа кожи.\n"
            "Чтобы пройти тест, напиши /test"
        )

    async def consent_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [InlineKeyboardButton("Нет", callback_data="no")]
        ]
        markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(
            "Мы собираем анонимные данные. Согласны участвовать?", reply_markup=markup
        )
        return CONSENT

    async def handle_consent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        choice = query.data.lower()

        if choice in ["да", "yes"]:
            buttons = [
                [InlineKeyboardButton("М", callback_data="М")],
                [InlineKeyboardButton("Ж", callback_data="Ж")]
            ]
            markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text("Укажите ваш пол:", reply_markup=markup)
            return DEMO
        else:
            await query.edit_message_text("Тест отменен.")
            return ConversationHandler.END

    async def handle_demo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Выбор пола через кнопки
        if "sex" not in context.user_data:
            query = update.callback_query
            await query.answer()
            sex = query.data.upper()
            if sex not in ["М", "Ж"]:
                await query.edit_message_text("Выберите М или Ж")
                return DEMO
            context.user_data["sex"] = sex
            await query.edit_message_text("Введите ваш возраст:")
            return DEMO

        # Возраст и аллергии вводятся текстом как раньше
        elif "age" not in context.user_data:
            try:
                age = int(update.message.text)
                context.user_data["age"] = age
                await update.message.reply_text("Укажите аллергии (текст):")
                return DEMO
            except ValueError:
                await update.message.reply_text("Введите число")
                return DEMO

        else:
            context.user_data["allergies"] = update.message.text
        # Далее идет генерация id, сохранение в CSV и переход к тесту как ран
            # генерируем уникальный id
            id_patient = str(uuid.uuid4())
            context.user_data["id_patient"] = id_patient
            context.user_data["answers_json"] = {}
            context.user_data["index"] = 0

            # сохраняем начальные данные
            await save_initial_data(
                id_patient=context.user_data["id_patient"],
                age=context.user_data["age"],
                sex=context.user_data["sex"],
                allergies=context.user_data["allergies"]
            )

            await self.ask_question(update, context)
            return Q_STATE

    async def ask_question(self, update_or_query, context):
        idx = context.user_data["index"]
        category, question, options = self.questions[idx]

        buttons = [
            [InlineKeyboardButton(f"A: {options['A']}", callback_data="A")],
            [InlineKeyboardButton(f"B: {options['B']}", callback_data="B")]
        ]
        markup = InlineKeyboardMarkup(buttons)
        text = f"{question}\n\nВыберите вариант:"

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

        if context.user_data["index"] >= len(self.questions):
            # Преобразуем словарь ответов в JSON-строку
            answers_json_str = json.dumps(context.user_data["answers_json"], ensure_ascii=False)

            # Классификация по алгоритму
            answers_list = list(context.user_data["answers_json"].items())
            result = self.test.classify_baumann(answers_list)

            # Сохраняем результаты в CSV
            await save_test_results(
                id_patient=context.user_data["id_patient"],
                answers_json=answers_json_str,
                skin_code=result["code"]
            )

            await query.edit_message_text(
                f"✅ Тест завершён!\n\nВаш тип кожи: *{result['code']}*\n\n{result['desc']}",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        else:
            await self.ask_question(query, context)
            return Q_STATE
        

    async def request_dermatoscopy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Обработка команды /photo — генерируем отчёт"""
            user_id = update.effective_user.id
            id_patient = context.user_data.get("id_patient")

            if not id_patient:
                await update.message.reply_text("⚠️ Сначала пройдите тест командой /test.")
                return

            await update.message.reply_text("🔍 Анализируем изображение дерматоскопа...")

            # --- Симулируем результат анализа ---
            skin_type = "Normal / Dry"

            # --- Сохраняем результат в CSV ---
            await save_dermatoscopy_result(id_patient, skin_type)

            # --- Формируем отчёт в DOCX ---
            filename = os.path.join(REPORTS_DIR, f"regina.docx")
            doc = Document()
            doc.add_heading("Отчёт дерматоскопического анализа", level=1)
            doc.add_paragraph(f"Пациент ID: {id_patient}")
            doc.add_paragraph(f"Дата анализа: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            doc.add_paragraph(f"Тип кожи по дерматоскопии: {skin_type}")
            doc.add_paragraph("\nРекомендации: поддерживающий уход, без признаков патологии.")
            doc.save(filename)

            # --- Отправляем пользователю ---
            await update.message.reply_document(
                document=open(filename, "rb"),
                caption="🧾 Ваш отчёт по дерматоскопическому анализу"
            )

    def run(self):
        from telegram.ext import ApplicationBuilder
        app = ApplicationBuilder().token(self.token).build()

        conv = ConversationHandler(
            entry_points=[CommandHandler("test", self.consent_start)],
            states={
                CONSENT: [CallbackQueryHandler(self.handle_consent, pattern="^(yes|no)$")],
                DEMO: [
                    CallbackQueryHandler(self.handle_demo, pattern="^(М|Ж)$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_demo)  # для возраста и аллергий
                ],
                Q_STATE: [CallbackQueryHandler(self.handle_answer, pattern="^(A|B)$")]
            },
            fallbacks=[],
            per_message=False
        )

        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("photo", self.request_dermatoscopy)) 
        app.add_handler(conv)

        print("Бот запущен 🚀")
        app.run_polling()
