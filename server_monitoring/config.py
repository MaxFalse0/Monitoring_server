DB_NAME = "monitoring.db"
THRESHOLDS = {
    "cpu": 80,
    "ram": 80,
    "disk": 90
}
EMAIL_SETTINGS = {
    "sender": "salmanov.maxim2016@yandex.ru",
    "password": "passwd",
    "receiver": "receiver_email@gmail.com"
}
SSH_CONFIG = {
    "default_user": "root"
}

# Глобальная переменная для статуса подключения
connection_status = {"status": "Ожидание подключения", "error": None}
