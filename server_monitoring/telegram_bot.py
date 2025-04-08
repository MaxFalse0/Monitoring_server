import logging
import time
import json
import os

from telegram.ext import Updater, CommandHandler
from telegram import Update
from telegram.ext.callbackcontext import CallbackContext
from server_monitoring.config import TELEGRAM_BOT_TOKEN

MAP_PATH = "user_map.json"

def load_map():
    if os.path.exists(MAP_PATH):
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_map(data):
    with open(MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def start_command(update: Update, context: CallbackContext):
    if update.message.from_user.is_bot:
        return

    chat_id = update.effective_chat.id
    username = update.message.from_user.username

    if username:
        user_map = load_map()
        user_map[username.lower()] = chat_id
        save_map(user_map)

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

    updater.start_polling()
    print("Telegram bot is running in background.")
    while True:
        time.sleep(1)
