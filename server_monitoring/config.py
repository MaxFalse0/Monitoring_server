# server_monitoring/config.py

import os

DB_NAME = "monitoring.db"

THRESHOLDS = {
    "cpu": 80,
    "ram": 80,
    "disk": 90
}

# "autofix" порог, когда делаем auto-healing
AUTOHEAL_CPU = 95

# Telegram
TELEGRAM_BOT_TOKEN = "8180962728:AAFFZI2-SZT8Ig-0_VAy0wOYuEumJbY_VQs"

# 2FA
TWOFA_CODE_LENGTH = 6

# Храним записи метрик только 30 дней
DATA_RETENTION_DAYS = 30

# Роли
ROLES = ("admin", "user")

# Настройки WebSocket
SOCKETIO_CORS_ALLOWED_ORIGINS = "*"

# Папка загрузок (если понадобится экспорт/импорт)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")

# Расширяемый словарь статуса
connection_status = {
    "status": "Waiting for connection",
    "error": None
}
