# server_monitoring/config.py

import os

DB_NAME = "monitoring.db"

THRESHOLDS = {
    "cpu": 80,
    "ram": 80,
    "disk": 90
}

AUTOHEAL_CPU = 95

# Telegram
TELEGRAM_BOT_TOKEN = "8180962728:AAFFZI2-SZT8Ig-0_VAy0wOYuEumJbY_VQs"

# 2FA
TWOFA_CODE_LENGTH = 6

DATA_RETENTION_DAYS = 30

REMOTE_TEMP_SCRIPT = "/tmp/get_temp.sh"

ROLES = ("admin", "user")

SOCKETIO_CORS_ALLOWED_ORIGINS = "*"

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")

connection_status = {
    "status": "Not connected",
    "error": None,
    "server": None,
    "active": False
}

###################################
# Новые настройки для Celery
###################################
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

