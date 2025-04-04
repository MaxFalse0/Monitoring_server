import logging
import time

from telegram.ext import Updater, CommandHandler
from telegram import Update
from telegram.ext.callbackcontext import CallbackContext
from server_monitoring.config import TELEGRAM_BOT_TOKEN

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def start_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    text = (
        "Привет! Я бот для уведомлений о мониторинге.\n"
        f"Ваш chat_id: {chat_id}\n\n"
        "Скопируйте это число и введите на сайте (tg_connect), "
        "чтобы получать уведомления и использовать 2FA."
    )
    update.message.reply_text(text)

def run_bot():
    print("Telegram bot is starting...")

    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start_command))
    # Не добавляем MessageHandler => на любые другие сообщения молчим

    updater.start_polling()
    print("Telegram bot is running in background (thread).")

    # Вместо idle() в потоке делаем самописный цикл
    while True:
        time.sleep(1)
