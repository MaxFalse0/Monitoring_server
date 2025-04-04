import os
import threading

from server_monitoring.database import init_db
from server_monitoring.web import app
from server_monitoring.telegram_bot import run_bot

if __name__ == "__main__":
    # Создаём/обновляем таблицы в базе
    init_db()

    # Избегаем двойного запуска бота при debug=True:
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()

    # Запускаем Flask в debug-режиме
    app.run(debug=True)
