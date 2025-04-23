import os
import random
import csv
import io
import threading
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_socketio import SocketIO, emit
import time
from server_monitoring.celery_worker import task_collect_metrics
import sqlite3
from server_monitoring.database import DB_NAME
from werkzeug.security import generate_password_hash, check_password_hash
from server_monitoring.collect import collect_metrics
from server_monitoring.auth import login_user as auth_login_user, register_user
from server_monitoring import database
from server_monitoring.analyze import send_telegram_alert
from server_monitoring.config import TWOFA_CODE_LENGTH, SOCKETIO_CORS_ALLOWED_ORIGINS
from server_monitoring.config import connection_status
from server_monitoring.database import get_metrics_for_period, get_all_metrics, get_server_by_id, get_user_by_id
from server_monitoring.socketio_manager import socketio
from server_monitoring.security import register_security_headers
from flask_login import login_required
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from server_monitoring.database import get_user_by_id
from server_monitoring.user import User
import re
import os
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.secret_key = "supersecretkey"
csrf = CSRFProtect(app)
socketio.init_app(app, cors_allowed_origins="*")  # или SOCKETIO_CORS_ALLOWED_ORIGINS
user_connections = {}
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

if not os.path.exists("app.log"):
    with open("app.log", "w", encoding="utf-8") as f:
        f.write("")

file_handler = RotatingFileHandler("app.log", maxBytes=100000, backupCount=10)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
file_handler.setFormatter(formatter)

app.logger.setLevel(logging.INFO)  # <—— ОБЯЗАТЕЛЬНО
app.logger.addHandler(file_handler)
app.logger.propagate = False       # <—— чтобы избежать дублирования


# Отключаем лишние логи Flask/Werkzeug
logging.getLogger("werkzeug").setLevel(logging.WARNING)


@login_manager.user_loader
def load_user(user_id):
    user = get_user_by_id(user_id)
    if user:
        return User(user["id"], user["username"], user["telegram_username"], user["twofa_enabled"], user["role"])
    return None


from flask_login import current_user


@app.before_request
def check_session():
    allowed_routes = (
        "login", "register", "twofa_verify", "resend_code",
        "static", "export_data", "socketio_test", "socketio_test_emit"
    )
    if request.endpoint not in allowed_routes and not current_user.is_authenticated:
        return redirect(url_for("login"))


# -------------- Авторизация --------------
@app.route("/register", methods=["GET", "POST"], endpoint="register")
def register_view():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        try:
            register_user(username, password)
            return redirect(url_for("login"))
        except Exception as e:
            return render_template("register.html", error=str(e))
    return render_template("register.html", error=None)


def register_user(username, password):
    # Валидация логина
    if len(username) < 4:
        raise Exception("Имя пользователя должно быть не короче 4 символов.")
    if not re.match("^[a-zA-Z0-9_]+$", username):
        raise Exception("Имя пользователя может содержать только буквы, цифры и _")

    # Валидация пароля
    if len(password) < 8:
        raise Exception("Пароль должен содержать минимум 8 символов.")
    if not re.search(r"[A-Z]", password):
        raise Exception("Пароль должен содержать хотя бы одну заглавную букву.")
    if not re.search(r"[a-z]", password):
        raise Exception("Пароль должен содержать хотя бы одну строчную букву.")
    if not re.search(r"\d", password):
        raise Exception("Пароль должен содержать хотя бы одну цифру.")
    if not re.search(r"[!@#$%^&*()_+{}\[\]:;\"'<>?,./\\\-]", password):
        raise Exception("Пароль должен содержать хотя бы один спецсимвол.")

    # Хеширование пароля
    hashed = generate_password_hash(password)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Проверка существования пользователя с таким именем
    cursor.execute("SELECT id FROM users WHERE username=?", (username,))
    if cursor.fetchone():
        raise Exception("Пользователь с таким именем уже существует.")

    # Определение роли: если еще нет пользователей, назначить admin, иначе user
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    role = "admin" if count == 0 else "user"

    # Сохранение нового пользователя с назначенной ролью
    cursor.execute('''
        INSERT INTO users (username, password, role)
        VALUES (?, ?, ?)
    ''', (username, hashed, role))
    conn.commit()
    conn.close()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        # Используем функцию аутентификации из auth
        user_record = auth_login_user(username, password)  # возвращает словарь пользователя

        if user_record:
            # Если включена 2FA, оставляем прежнюю логику двухфакторки
            if user_record["twofa_enabled"] == 1 and user_record["telegram_username"]:
                code = generate_2fa_code()
                session["twofa_code"] = code
                session["twofa_timestamp"] = time.time()
                session["partial_login"] = True
                session["user_id"] = user_record["id"]
                send_telegram_alert(user_record["telegram_username"], f"Ваш код для входа: {code}")
                return redirect(url_for("twofa_verify"))
            else:
                # Создаем объект пользователя и логиним через Flask-Login
                user_obj = User(
                    user_record["id"],
                    user_record["username"],
                    user_record["telegram_username"],
                    user_record["twofa_enabled"],
                    user_record["role"]
                )
                login_user(user_obj)
                app.logger.info(f"[LOGIN] Пользователь '{user_record['username']}' вошёл в систему")
  # теперь используем login_user из flask_login
                return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Неверный логин или пароль")
    return render_template("login.html", error=None)


@app.route("/logout")
@login_required
def logout():
    username = current_user.username
    logout_user()
    app.logger.info(f"[LOGOUT] Пользователь '{username}' вышел из системы")
    return redirect(url_for("login"))



# -------------- Главная страница ("/") --------------

user_connections = {}  # глобальный словарь для статусов по user_id


@app.route("/", methods=["GET", "POST"])
@login_required
def dashboard():
    user_id = current_user.id
    tg_username = current_user.telegram_username

    if request.method == "POST":
        server_ip = request.form["server_ip"]
        server_port = int(request.form["server_port"])
        ssh_user = request.form["username"]
        ssh_password = request.form["password"]

        if user_id not in user_connections or not user_connections[user_id].get("active", False):
            user_connections[user_id] = {
                "status": "Подключаемся к серверу...",
                "error": None,
                "server": f"{server_ip}:{server_port}",
                "active": True
            }

            threading.Thread(
                target=collect_metrics,
                args=(server_ip, server_port, ssh_user, ssh_password, user_connections[user_id], tg_username, user_id),
                daemon=True
            ).start()

        app.logger.info(f"[CONNECT] Пользователь '{current_user.username}' подключился к серверу {server_ip}:{server_port}")
        return render_template("index.html",
                               message=user_connections[user_id]["status"],
                               status=user_connections[user_id],
                               servers=get_user_servers())

    connection_status = user_connections.get(user_id, {
        "status": "Не подключено",
        "error": None,
        "server": None,
        "active": False
    })
    return render_template("index.html",
                           message=connection_status["status"],
                           status=connection_status,
                           servers=get_user_servers())


@app.route("/connect_existing_server", methods=["POST"])
@login_required
def connect_existing_server():
    user_id = current_user.id
    user_role = current_user.role
    server_id = request.form.get("server_id")
    tg_username = current_user.telegram_username

    s = get_server_by_id(server_id)
    if not s or (user_role != "admin" and s["user_id"] != user_id):
        return redirect(url_for("dashboard"))

    if user_id not in user_connections or not user_connections[user_id].get("active", False):
        user_connections[user_id] = {
            "status": "Подключаемся к выбранному серверу...",
            "error": None,
            "server": f"{s['ip']}:{s['port']}",
            "active": True
        }

        threading.Thread(
            target=collect_metrics,
            args=(s["ip"], s["port"], s["ssh_user"], s["ssh_password"], user_connections[user_id], tg_username, user_id),
            daemon=True
        ).start()
        app.logger.info(f"[CONNECT] Пользователь '{current_user.username}' подключился к сохранённому серверу {s['ip']}:{s['port']}")
    return redirect(url_for("dashboard"))





def get_user_servers():
    """
    Возвращает список серверов для текущего пользователя (или все, если admin).
    """
    # Если пользователь не авторизован, current_user.is_authenticated вернет False.
    if not current_user.is_authenticated:
        return []
    user_id = current_user.id
    role = current_user.role
    servers = database.get_servers_for_user(user_id, role)
    return servers


@app.route("/data")
@login_required
def get_data():
    user_id = current_user.id
    user_role = current_user.role
    latest = database.get_latest_metrics(user_id, user_role)

    # Получаем connection_status именно для этого пользователя
    connection_status = user_connections.get(user_id, {
        "status": "Не подключено",
        "error": None,
        "server": None,
        "active": False
    })

    if not latest:
        return jsonify({"metrics": {}, "status": connection_status})

    metrics = {
        "cpu": latest["cpu"],
        "ram": latest["ram"],
        "disk": latest["disk"],
        "rx": latest["net_rx"],
        "tx": latest["net_tx"],
        "users": latest["users"],
        "temp": latest["temp"],
        "swap": latest["swap"],
        "uptime": latest["uptime"],
        "processes": latest["processes"],
        "threads": latest["threads"],
        "rx_err": latest["rx_err"],
        "tx_err": latest["tx_err"],
        "power": latest["power"]
    }

    return jsonify({"metrics": metrics, "status": connection_status})





# -------------- Telegram, 2FA --------------

@app.route("/tg_connect", methods=["GET", "POST"])
@login_required
def tg_connect():
    user = get_user_by_id(current_user.id)
    if not user:
        return redirect(url_for("logout"))

    if request.method == "POST":
        new_tg = request.form["telegram_username"].strip()
        if not new_tg.isdigit():
            return render_template("tg_connect.html", current_tg=user["telegram_username"],
                                   error="Введите только числовой Telegram ID (chat_id).")
        database.update_user_telegram(current_user.id, new_tg)
        session["telegram_username"] = new_tg
        send_telegram_alert(new_tg, "✅ Вы успешно подключили Telegram-бота!")
        app.logger.info(f"[2FA] Пользователь '{current_user.username}' привязал Telegram (chat_id={new_tg})")
        return redirect(url_for("tg_connect"))

    return render_template("tg_connect.html",
                           current_tg=user["telegram_username"],
                           bot_name="@AllertServMonitorBot",
                           error=None)


@app.route("/twofa_verify", methods=["GET", "POST"])
def twofa_verify():
    import time
    if "partial_login" not in session:
        return redirect(url_for("login"))

    error = None

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        current_time = time.time()
        code_time = session.get("twofa_timestamp")

        if not code_time or current_time - code_time > 60:
            error = "Код истёк. Пожалуйста, запросите новый."
        elif code != session.get("twofa_code"):
            error = "Неверный код"
        else:
            # Успешная авторизация по 2FA: получаем данные пользователя и логиним через Flask-Login
            user_id = session["user_id"]
            user = get_user_by_id(user_id)
            # Очистка временных данных двухфакторной аутентификации
            session.pop("partial_login", None)
            session.pop("twofa_code", None)
            session.pop("twofa_timestamp", None)
            # Создаем объект пользователя для Flask-Login и отмечаем его как аутентифицированного
            user_obj = User(user["id"], user["username"], user["telegram_username"], user["twofa_enabled"],
                            user["role"])
            login_user(user_obj)
            return redirect(url_for("dashboard"))

    # Вычисляем оставшееся время действия кода
    remaining = 0
    if "twofa_timestamp" in session:
        elapsed = time.time() - session["twofa_timestamp"]
        remaining = max(0, int(60 - elapsed))

    return render_template("twofa_verify.html", error=error, remaining=remaining)


@app.route("/resend_code")
def resend_code():
    import time
    from server_monitoring.analyze import send_telegram_alert

    if "partial_login" not in session:
        return jsonify({"status": "error", "message": "Сессия истекла"})

    code = generate_2fa_code()
    session["twofa_code"] = code
    session["twofa_timestamp"] = time.time()

    user = get_user_by_id(session["user_id"])
    if user and user["telegram_username"]:
        send_telegram_alert(user["telegram_username"], f"Ваш новый код для входа: {code}")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Нет Telegram-профиля"})


@app.route("/twofa_setup", methods=["GET", "POST"])
@login_required
def twofa_setup():
    user = get_user_by_id(current_user.id)
    if not user["telegram_username"]:
        return render_template("twofa_setup.html",
                               error="Сначала подключите Telegram (/tg_connect)",
                               twofa_enabled=user["twofa_enabled"])
    if request.method == "POST":
        action = request.form.get("action")
        if action == "enable":
            database.set_twofa_enabled(current_user.id, True)
            send_telegram_alert(user["telegram_username"], "2FA включена.")
        elif action == "disable":
            database.set_twofa_enabled(current_user.id, False)
            send_telegram_alert(user["telegram_username"], "2FA выключена.")
        app.logger.info(f"[2FA] Пользователь '{current_user.username}' {'включил' if action == 'enable' else 'отключил'} двухфакторную аутентификацию")
        return redirect(url_for("twofa_setup"))
    return render_template("twofa_setup.html",
                           error=None,
                           twofa_enabled=user["twofa_enabled"])


# -------------- Роли --------------

@app.route("/set_role/<int:target_user_id>/<role>")
@login_required
def set_role(target_user_id, role):
    if current_user.role != "admin":
        return "Недостаточно прав"
    if role not in ("admin", "user"):
        return "Неверная роль"
    database.set_user_role(target_user_id, role)
    return f"Пользователю {target_user_id} назначена роль {role}"


@app.route("/users")
@login_required
def users():
    # Только администратор имеет доступ
    if current_user.role != "admin":
        return "Недостаточно прав для доступа к управлению пользователями", 403
    user_list = database.get_all_users()
    return render_template("users.html", users=user_list)


# -------------- Управление серверами --------------

@app.route("/servers", methods=["GET", "POST"])
def servers_list():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    user_id = current_user.id
    role = current_user.role

    if request.method == "POST":
        name = request.form["name"]
        ip = request.form["ip"]
        port = int(request.form["port"])
        ssh_user = request.form["ssh_user"]
        ssh_password = request.form["ssh_password"]
        database.create_server(user_id, name, ip, port, ssh_user, ssh_password)
        app.logger.info(f"[SERVER ADD] Пользователь '{current_user.username}' добавил сервер {name} ({ip}:{port})")
        return redirect(url_for("servers_list"))

    servers = database.get_servers_for_user(user_id, role)
    return render_template("servers.html", servers=servers, is_admin=(role == "admin"))


@app.route("/servers/<int:server_id>/edit", methods=["GET", "POST"])
@login_required
def servers_edit(server_id):
    role = current_user.role
    user_id = current_user.id
    s = get_server_by_id(server_id)
    if not s:
        return "Нет такого сервера"
    if role != "admin" and s["user_id"] != user_id:
        return "Недостаточно прав"

    if request.method == "POST":
        name = request.form["name"]
        ip = request.form["ip"]
        port = int(request.form["port"])
        ssh_user = request.form["ssh_user"]
        ssh_password = request.form["ssh_password"]
        database.update_server(server_id, name, ip, port, ssh_user, ssh_password)
        return redirect(url_for("servers_list"))
    app.logger.info(f"[SERVER EDIT] Пользователь '{current_user.username}' обновил сервер ID={server_id}")
    return render_template("servers_edit.html", server=s)


@app.route("/servers/<int:server_id>/delete", methods=["POST"])
@login_required
def servers_delete(server_id):
    role = current_user.role
    user_id = current_user.id
    s = get_server_by_id(server_id)
    if not s:
        return "Сервер не найден"
    if role != "admin" and s["user_id"] != user_id:
        return "Недостаточно прав"
    database.delete_server(server_id)
    app.logger.info(f"[SERVER DELETE] Пользователь '{current_user.username}' удалил сервер ID={server_id}")
    return redirect(url_for("servers_list"))


# -------------- Отчёты --------------

@app.route("/report")
@login_required
def report():
    # Используем current_user для получения id и роли
    user_id = current_user.id
    role = current_user.role

    days = request.args.get("days", "1")
    try:
        days = int(days)
    except:
        days = 1

    try:
        rows = get_metrics_for_period(user_id, role, days)
        if not rows:
            return render_template("report.html", days=days)

        cpus = [r[0] for r in rows if r[0] is not None]
        rams = [r[1] for r in rows if r[1] is not None]
        disks = [r[2] for r in rows if r[2] is not None]
        users_ = [r[3] for r in rows if r[3] is not None]
        temps = [r[4] for r in rows if r[4] is not None]
        net_rxs = [r[5] for r in rows if r[5] is not None]
        net_txs = [r[6] for r in rows if r[6] is not None]
        swaps = [r[7] for r in rows if r[7] is not None]
        latest_uptime = rows[-1][8]
        procs = [r[9] for r in rows if r[9] is not None]
        threads = [r[10] for r in rows if r[10] is not None]
        rx_errs = [r[11] for r in rows if r[11] is not None]
        tx_errs = [r[12] for r in rows if r[12] is not None]
        powers = [r[13] for r in rows if r[13] is not None]

        cpu_avg = sum(cpus)/len(cpus) if cpus else None
        cpu_min = min(cpus) if cpus else None
        cpu_max = max(cpus) if cpus else None

        ram_avg = sum(rams)/len(rams) if rams else None
        ram_min = min(rams) if rams else None
        ram_max = max(rams) if rams else None

        disk_avg = sum(disks)/len(disks) if disks else None
        disk_min = min(disks) if disks else None
        disk_max = max(disks) if disks else None

        users_avg = sum(users_)/len(users_) if users_ else None
        users_min = min(users_) if users_ else None
        users_max = max(users_) if users_ else None

        temp_avg = sum(temps)/len(temps) if temps else None
        temp_min = min(temps) if temps else None
        temp_max = max(temps) if temps else None

        net_rx_avg = sum(net_rxs)/len(net_rxs) if net_rxs else None
        net_rx_min = min(net_rxs) if net_rxs else None
        net_rx_max = max(net_rxs) if net_rxs else None

        net_tx_avg = sum(net_txs)/len(net_txs) if net_txs else None
        net_tx_min = min(net_txs) if net_txs else None
        net_tx_max = max(net_txs) if net_txs else None

        swap_avg = sum(swaps)/len(swaps) if swaps else None
        swap_min = min(swaps) if swaps else None
        swap_max = max(swaps) if swaps else None

        procs_avg = sum(procs)/len(procs) if procs else None
        procs_min = min(procs) if procs else None
        procs_max = max(procs) if procs else None

        threads_avg = sum(threads)/len(threads) if threads else None
        threads_min = min(threads) if threads else None
        threads_max = max(threads) if threads else None

        rx_err_avg = sum(rx_errs)/len(rx_errs) if rx_errs else None
        rx_err_min = min(rx_errs) if rx_errs else None
        rx_err_max = max(rx_errs) if rx_errs else None

        tx_err_avg = sum(tx_errs)/len(tx_errs) if tx_errs else None
        tx_err_min = min(tx_errs) if tx_errs else None
        tx_err_max = max(tx_errs) if tx_errs else None

        power_avg = sum(powers)/len(powers) if powers else None
        power_min = min(powers) if powers else None
        power_max = max(powers) if powers else None

        # Функция форматирования: если значение существует – округляет, иначе возвращает сообщение "нет данных"
        def fmt(value, ndigits=2):
            return round(value, ndigits) if value is not None else "нет данных"

        return render_template("report.html",
                               days=days,
                               cpu_avg=fmt(cpu_avg), cpu_min=fmt(cpu_min), cpu_max=fmt(cpu_max),
                               ram_avg=fmt(ram_avg), ram_min=fmt(ram_min), ram_max=fmt(ram_max),
                               disk_avg=fmt(disk_avg), disk_min=fmt(disk_min), disk_max=fmt(disk_max),
                               users_avg=fmt(users_avg, 0), users_min=fmt(users_min, 0), users_max=fmt(users_max, 0),
                               temp_avg=fmt(temp_avg, 1), temp_min=fmt(temp_min, 1), temp_max=fmt(temp_max, 1),
                               net_rx_avg=fmt(net_rx_avg), net_rx_min=fmt(net_rx_min) if net_rx_min is not None else 0,
                               net_rx_max=fmt(net_rx_max) if net_rx_max is not None else 0,
                               net_tx_avg=fmt(net_tx_avg), net_tx_min=fmt(net_tx_min) if net_tx_min is not None else 0,
                               net_tx_max=fmt(net_tx_max) if net_tx_max is not None else 0,
                               swap_avg=fmt(swap_avg), swap_min=fmt(swap_min), swap_max=fmt(swap_max),
                               latest_uptime=latest_uptime,
                               procs_avg=fmt(procs_avg, 0), procs_min=fmt(procs_min, 0), procs_max=fmt(procs_max, 0),
                               threads_avg=fmt(threads_avg, 0), threads_min=fmt(threads_min, 0), threads_max=fmt(threads_max, 0),
                               rx_err_avg=fmt(rx_err_avg), rx_err_min=fmt(rx_err_min), rx_err_max=fmt(rx_err_max),
                               tx_err_avg=fmt(tx_err_avg), tx_err_min=fmt(tx_err_min), tx_err_max=fmt(tx_err_max),
                               power_avg=fmt(power_avg), power_min=fmt(power_min), power_max=fmt(power_max)
                               )
    except Exception as e:
        return f"Ошибка при формировании отчёта: {str(e)}"



# -------------- Экспорт CSV --------------

@app.route("/export")
@login_required
def export_data():
    user_id = current_user.id
    role = current_user.role

    rows = get_all_metrics(user_id, role)
    if not rows:
        return "Нет данных для экспорта."

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "cpu", "ram", "disk", "net_rx", "net_tx", "users", "temp"])
    for row in rows:
        writer.writerow(row)
    output.seek(0)
    app.logger.info(f"[EXPORT] Пользователь '{current_user.username}' экспортировал CSV-файл метрик")
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="metrics_export.csv"
    )
    


# -------------- Динамический дашборд --------------

@app.route("/dashboard_custom")
@login_required
def dashboard_custom():
    metrics = ["cpu", "ram", "disk", "temp", "users", "rx", "tx"]
    metric_labels = {
        "cpu": "Процессор",
        "ram": "Оперативная память",
        "disk": "Диск",
        "temp": "Температура",
        "users": "Пользователи",
        "rx": "Сеть ↓ (RX)",
        "tx": "Сеть ↑ (TX)"
    }
    return render_template("dashboard_custom.html", metrics=metrics, metric_labels=metric_labels)


# -------------- WebSocket test --------------
@socketio.on("connect")
def on_connect():
    print("Client connected via SocketIO")
    emit("server_event", {"data": "Добро пожаловать! WebSocket connection established."})


@app.route("/disconnect")
@login_required
def disconnect():
    user_id = current_user.id
    if user_id in user_connections:
        user_connections[user_id]["active"] = False
        user_connections[user_id]["status"] = "Отключено"
        user_connections[user_id]["server"] = None
        user_connections[user_id]["error"] = None
    app.logger.info(f"[DISCONNECT] Пользователь '{current_user.username}' отключился от сервера")
    return redirect(url_for("dashboard_custom"))



# ------------ Вспомогательное -----------

def generate_2fa_code():
    import random
    digits = "0123456789"
    return "".join(random.choice(digits) for _ in range(TWOFA_CODE_LENGTH))


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.route("/logs")
@login_required
def logs():
    if current_user.role != "admin":
        return "Недостаточно прав для просмотра журнала логов", 403
    try:
        with open("app.log", "r", encoding="utf-8") as f:
            log_content = f.read()
    except Exception as e:
        log_content = f"Ошибка чтения журнала логов: {str(e)}"
    return render_template("logs.html", log_content=log_content)


@app.route("/admin")
@login_required
def admin_panel():
    if current_user.role != "admin":
        return "Недостаточно прав для доступа к админ-панели", 403

    logs = []
    log_files = sorted(
        [f for f in os.listdir() if f.startswith("app.log")],
        reverse=True
    )

    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                logs.extend(f.readlines())
        except:
            pass

    # Оставляем последние 500 строк, самые новые сверху
    logs = logs[-500:][::-1]

    user_list = database.get_all_users()
    return render_template("admin_panel.html", users=user_list, logs="".join(logs))

@app.errorhandler(Exception)
def handle_global_exception(e):
    app.logger.error(f"[ERROR] Критическая ошибка: {str(e)}")
    return render_template("404.html"), 500
