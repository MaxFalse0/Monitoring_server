from Monitoring_server.server_monitoring.config import THRESHOLDS, EMAIL_SETTINGS
import smtplib
from email.mime.text import MIMEText

def check_alerts(cpu, ram, disk):
    alerts = []  # Список для хранения предупреждений
    if cpu > THRESHOLDS["cpu"]:
        alerts.append(f"Высокая загрузка CPU: {cpu}%")
    if ram > THRESHOLDS["ram"]:
        alerts.append(f"Высокая загрузка RAM: {ram}%")
    if disk > THRESHOLDS["disk"]:
        alerts.append(f"Мало места на диске: {disk}% занято")
    if alerts:
        try:
            send_email("\n".join(alerts))
        except Exception as e:
            print(f"Не удалось отправить уведомление: {e}")

def send_email(message):
    msg = MIMEText(message)
    msg["Subject"] = "Server Alert!"
    msg["From"] = EMAIL_SETTINGS["sender"]
    msg["To"] = EMAIL_SETTINGS["receiver"]
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            # Для Gmail нужен App Password вместо обычного пароля
            server.login(EMAIL_SETTINGS["sender"], EMAIL_SETTINGS["password"])
            server.send_message(msg)
            print("Уведомление отправлено на email")
    except smtplib.SMTPAuthenticationError:
        print("Ошибка аутентификации SMTP: проверьте логин и пароль в EMAIL_SETTINGS")
    except Exception as e:
        print(f"Ошибка отправки email: {e}")