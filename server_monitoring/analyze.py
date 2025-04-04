from server_monitoring.config import THRESHOLDS, TELEGRAM_BOT_TOKEN
import requests

def check_alerts(cpu, ram, disk, telegram_username=None):
    alerts = []
    if cpu > THRESHOLDS["cpu"]:
        alerts.append(f"Высокая загрузка CPU: {cpu:.1f}%")
    if ram > THRESHOLDS["ram"]:
        alerts.append(f"Высокая загрузка RAM: {ram:.1f}%")
    if disk > THRESHOLDS["disk"]:
        alerts.append(f"Мало места на диске: {disk:.1f}% занято")

    if alerts and telegram_username:
        message = "\n".join(alerts)
        send_telegram_alert(telegram_username, message)

def send_telegram_alert(user_telegram_username, message):
    """
    Упрощённо считаем, что user_telegram_username — это chat_id (число).
    """
    try:
        chat_id = int(user_telegram_username)
    except ValueError:
        print("Телеграм username не является chat_id, не отправляем сообщение.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"Отправлено сообщение в Telegram (chat_id={chat_id}).")
        else:
            print(f"Ошибка отправки в Telegram: {resp.text}")
    except Exception as e:
        print(f"Ошибка при отправке Telegram: {e}")
