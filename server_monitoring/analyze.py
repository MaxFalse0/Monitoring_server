import requests
import paramiko
from server_monitoring.config import THRESHOLDS, TELEGRAM_BOT_TOKEN, AUTOHEAL_CPU
import os
import json


# Дополнительные пороги
USER_THRESHOLD = 50
TEMP_THRESHOLD = 75


def check_alerts(cpu, ram, disk, telegram_username=None, users=None, temp=None, server_ip=None):
    alerts = []
    if cpu > THRESHOLDS["cpu"]:
        msg = f"Высокая загрузка CPU: {cpu:.1f}%"
        if server_ip:
            msg += f" на сервере {server_ip}"
        alerts.append(msg)
    if ram > THRESHOLDS["ram"]:
        msg = f"Высокая загрузка RAM: {ram:.1f}%"
        if server_ip:
            msg += f" на сервере {server_ip}"
        alerts.append(msg)
    if disk > THRESHOLDS["disk"]:
        msg = f"Мало места на диске: {disk:.1f}% занято"
        if server_ip:
            msg += f" на сервере {server_ip}"
        alerts.append(msg)
    if users is not None and users > USER_THRESHOLD:
        msg = f"Много пользователей в системе: {users}"
        if server_ip:
            msg += f" на сервере {server_ip}"
        alerts.append(msg)
    if temp is not None and temp > TEMP_THRESHOLD:
        msg = f"Высокая температура: {temp:.1f}°C"
        if server_ip:
            msg += f" на сервере {server_ip}"
        alerts.append(msg)

    if cpu > AUTOHEAL_CPU:
        print("Auto-healing triggered: CPU>95%. Demo - restart service or something...")

    if alerts and telegram_username:
        message = "\n".join(alerts)
        send_telegram_alert(telegram_username, message)


MAP_PATH = "user_map.json"

def send_telegram_alert(user, message):
    print(f"[DEBUG] Пытаюсь отправить сообщение: {message} → {user}")

    try:
        chat_id = int(user)  # Пробуем как ID
        print(f"[DEBUG] Используем как chat_id: {chat_id}")
    except ValueError:
        # Обрабатываем username
        username = str(user).strip().lstrip("@").lower()
        print(f"[DEBUG] Обрабатываем username: {username}")
        chat_id = None
        if os.path.exists(MAP_PATH):
            with open(MAP_PATH, "r", encoding="utf-8") as f:
                user_map = json.load(f)
                chat_id = user_map.get(username)
                print(f"[DEBUG] Найден chat_id: {chat_id}")
        if not chat_id:
            print(f"[Telegram] ❌ Неизвестный Telegram username: {username}")
            return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[Telegram] ✅ Сообщение отправлено: {chat_id}")
        else:
            print(f"[Telegram] ❌ Ошибка Telegram: {resp.text}")
    except Exception as e:
        print(f"[Telegram] ❌ Сбой отправки: {e}")
