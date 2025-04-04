import os
from server_monitoring.web import app, socketio
from server_monitoring.database import init_db
from server_monitoring.scheduler import start_scheduler

if __name__ == "__main__":
    # Инициализируем/обновляем БД (создаёт таблицы при отсутствии)
    init_db()

    # Запускаем планировщик (APSсheduler) с учётом pytz
    sched = start_scheduler()

    # Запуск Flask + SocketIO
    # (Чтобы работал WebSocket, вызываем socketio.run, а не app.run)
    socketio.run(app, debug=True, host="127.0.0.1", port=5000)
