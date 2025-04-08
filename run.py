from server_monitoring.database import init_db
from server_monitoring.telegram_bot import run_bot
import threading

if __name__ == "__main__":
    init_db()
    # Стартуем Telegram-бота в отдельном потоке
    threading.Thread(target=run_bot, daemon=True).start()

    # Стартуем Flask-приложение
    from server_monitoring.web import app, socketio
    socketio.run(app, debug=True, host="127.0.0.1", port=5000, use_reloader=False)
