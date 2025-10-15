import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters
from utils.bot import SkinBot
from utils.db import DBHandler

# DB_CONFIG = {
#     "user": "postgres",
#     "password": "dermai",
#     "database": "dermai_assistant_bot",
#     "host": "127.0.0.1",
#     "port": 5432
# }

TOKEN = "here bot TOKEN"

if __name__ == "__main__":

    bot = SkinBot(token=TOKEN)
    bot.run()
