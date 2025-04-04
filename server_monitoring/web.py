import os
import random
import csv
import io
import threading
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_socketio import SocketIO, emit

from server_monitoring.collect import collect_metrics
from server_monitoring.auth import login_user, register_user
from server_monitoring import database
from server_monitoring.analyze import send_telegram_alert
from server_monitoring.config import TWOFA_CODE_LENGTH, SOCKETIO_CORS_ALLOWED_ORIGINS
from server_monitoring.config import connection_status
from server_monitoring.database import get_metrics_for_period, get_all_metrics, get_server_by_id, get_user_by_id
from server_monitoring.socketio_manager import socketio

app = Flask(__name__)
app.secret_key = "supersecretkey"

socketio.init_app(app, cors_allowed_origins="*")  # или SOCKETIO_CORS_ALLOWED_ORIGINS


@app.before_request
def check_session():
    allowed_routes = (
        "login", "register", "twofa_verify",
        "static", "export_data",  # export_data пусть тоже проверяется => либо убираем
        "socketio_test", "socketio_test_emit"
    )
    # Если не авторизован => уходим на login
    if request.endpoint not in allowed_routes and "logged_in" not in session:
        if "partial_login" in session and request.endpoint == "twofa_verify":
            return None
        elif "partial_login" in session:
            return redirect(url_for("twofa_verify"))
        else:
            return redirect(url_for("login"))

# -------------- Авторизация --------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        try:
            register_user(username, password)
            return redirect(url_for("login"))
        except Exception as e:
            return render_template("register.html", error=str(e))
    return render_template("register.html", error=None)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = login_user(username, password)
        if user:
            if user["twofa_enabled"] == 1 and user["telegram_username"]:
                code = generate_2fa_code()
                session["twofa_code"] = code
                session["partial_login"] = True
                session["user_id"] = user["id"]
                send_telegram_alert(user["telegram_username"], f"Ваш код для входа: {code}")
                return redirect(url_for("twofa_verify"))
            else:
                session["logged_in"] = True
                session["user_id"] = user["id"]
                session["telegram_username"] = user["telegram_username"]
                session["role"] = user["role"]
                return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Неверный логин или пароль")
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------- Главная страница ("/") --------------

@app.route("/", methods=["GET", "POST"])
def dashboard():
    """
    Если POST => ручной ввод IP/port/ssh => collect_metrics
    Если GET => показать список серверов + метрики
    """
    global connection_status
    user_id = session["user_id"]
    user_role = session["role"]

    if request.method == "POST":
        server_ip = request.form["server_ip"]
        server_port = int(request.form["server_port"])
        ssh_user = request.form["username"]
        ssh_password = request.form["password"]

        connection_status["status"] = "Connecting to server..."
        connection_status["error"] = None

        tg_username = session.get("telegram_username")
        # Запускаем сбор метрик в отдельном потоке
        # Передаём user_id, чтобы сохранить метрики "под" этим пользователем
        threading.Thread(
            target=collect_metrics,
            args=(server_ip, server_port, ssh_user, ssh_password, connection_status, tg_username, user_id),
            daemon=True
        ).start()

        return render_template("index.html",
                               message=connection_status["status"],
                               status=connection_status,
                               servers=get_user_servers())
    else:
        # GET => вывести список, показать актуальные метрики
        return render_template("index.html",
                               message="Enter server data or select existing server",
                               status=connection_status,
                               servers=get_user_servers())


@app.route("/connect_existing_server", methods=["POST"])
def connect_existing_server():
    """
    Вызывается при выборе сервера из списка (index.html).
    Используем сохранённые данные (ip,port и т.д.) и запускаем collect_metrics
    """
    global connection_status
    user_id = session["user_id"]
    user_role = session["role"]
    server_id = request.form.get("server_id")

    if not server_id:
        return redirect(url_for("dashboard"))

    s = get_server_by_id(server_id)
    if not s:
        return redirect(url_for("dashboard"))

    # Проверка: admin видит все, user видит только свои
    if user_role != "admin" and s["user_id"] != user_id:
        return "Недостаточно прав для подключения к этому серверу"

    connection_status["status"] = "Connecting to existing server..."
    connection_status["error"] = None

    tg_username = session.get("telegram_username")
    threading.Thread(
        target=collect_metrics,
        args=(s["ip"], s["port"], s["ssh_user"], s["ssh_password"], connection_status, tg_username, user_id),
        daemon=True
    ).start()

    return redirect(url_for("dashboard"))

def get_user_servers():
    """
    Возвращает список серверов для текущего пользователя (или все, если admin)
    """
    if "logged_in" not in session:
        return []
    user_id = session["user_id"]
    role = session["role"]
    servers = database.get_servers_for_user(user_id, role)
    return servers

@app.route("/data")
def get_data():
    """
    Возвращает последнюю метрику (CPU,RAM и т.д.) для этого пользователя (или всех, если admin).
    """
    user_id = session["user_id"]
    user_role = session["role"]
    latest_metrics = database.get_latest_metrics(user_id, user_role)
    return jsonify({"metrics": latest_metrics, "status": connection_status})

# -------------- Telegram, 2FA --------------

@app.route("/tg_connect", methods=["GET","POST"])
def tg_connect():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    user = get_user_by_id(user_id)

    if request.method=="POST":
        new_tg = request.form["telegram_username"].strip()
        database.update_user_telegram(user_id, new_tg)
        session["telegram_username"] = new_tg
        send_telegram_alert(new_tg, "Вы успешно подключили бота!")
        return redirect(url_for("tg_connect"))

    return render_template("tg_connect.html",
                           current_tg=user["telegram_username"],
                           bot_name="@YourMonitoringBotHere")

@app.route("/twofa_verify", methods=["GET","POST"])
def twofa_verify():
    if "partial_login" not in session:
        return redirect(url_for("login"))
    if request.method=="POST":
        code = request.form["code"].strip()
        if code == session.get("twofa_code"):
            user_id = session["user_id"]
            user = get_user_by_id(user_id)
            session["logged_in"] = True
            session.pop("partial_login", None)
            session.pop("twofa_code", None)
            session["telegram_username"] = user["telegram_username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        else:
            return render_template("twofa_verify.html", error="Неверный код")
    return render_template("twofa_verify.html", error=None)

@app.route("/twofa_setup", methods=["GET","POST"])
def twofa_setup():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if not user["telegram_username"]:
        return render_template("twofa_setup.html",
                               error="Сначала подключите Telegram (/tg_connect)",
                               twofa_enabled=user["twofa_enabled"])
    if request.method=="POST":
        action = request.form.get("action")
        if action=="enable":
            database.set_twofa_enabled(user_id, True)
            send_telegram_alert(user["telegram_username"], "2FA включена.")
        elif action=="disable":
            database.set_twofa_enabled(user_id, False)
            send_telegram_alert(user["telegram_username"], "2FA выключена.")
        return redirect(url_for("twofa_setup"))
    return render_template("twofa_setup.html",
                           error=None,
                           twofa_enabled=user["twofa_enabled"])

# -------------- Роли --------------

@app.route("/set_role/<int:target_user_id>/<role>")
def set_role(target_user_id, role):
    if "logged_in" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "admin":
        return "Недостаточно прав"
    if role not in ("admin","user"):
        return "Неверная роль"
    database.set_user_role(target_user_id, role)
    return f"Пользователю {target_user_id} назначена роль {role}"

# -------------- Управление серверами --------------

@app.route("/servers", methods=["GET","POST"])
def servers_list():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    role = session["role"]

    if request.method=="POST":
        name = request.form["name"]
        ip = request.form["ip"]
        port = int(request.form["port"])
        ssh_user = request.form["ssh_user"]
        ssh_password = request.form["ssh_password"]
        database.create_server(user_id, name, ip, port, ssh_user, ssh_password)
        return redirect(url_for("servers_list"))

    servers = database.get_servers_for_user(user_id, role)
    return render_template("servers.html", servers=servers, is_admin=(role=="admin"))

@app.route("/servers/<int:server_id>/edit", methods=["GET","POST"])
def servers_edit(server_id):
    if "logged_in" not in session:
        return redirect(url_for("login"))
    role = session["role"]
    user_id = session["user_id"]
    s = get_server_by_id(server_id)
    if not s:
        return "Нет такого сервера"
    if role != "admin" and s["user_id"] != user_id:
        return "Недостаточно прав"

    if request.method=="POST":
        name = request.form["name"]
        ip = request.form["ip"]
        port = int(request.form["port"])
        ssh_user = request.form["ssh_user"]
        ssh_password = request.form["ssh_password"]
        database.update_server(server_id, name, ip, port, ssh_user, ssh_password)
        return redirect(url_for("servers_list"))

    return render_template("servers_edit.html", server=s)

@app.route("/servers/<int:server_id>/delete", methods=["POST"])
def servers_delete(server_id):
    if "logged_in" not in session:
        return redirect(url_for("login"))
    role = session["role"]
    user_id = session["user_id"]
    s = get_server_by_id(server_id)
    if not s:
        return "Сервер не найден"
    if role != "admin" and s["user_id"] != user_id:
        return "Недостаточно прав"
    database.delete_server(server_id)
    return redirect(url_for("servers_list"))

# -------------- Отчёты --------------

@app.route("/report")
def report():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    role = session["role"]

    days = request.args.get("days","1")
    try:
        days = int(days)
    except:
        days = 1
    rows = get_metrics_for_period(user_id, role, days)
    if not rows:
        return f"Нет данных за последние {days} дн."

    # rows = [ (cpu, ram, disk, users, temp, timestamp), ... ]
    cpus   = [r[0] for r in rows]
    rams   = [r[1] for r in rows]
    disks  = [r[2] for r in rows]
    users_ = [r[3] for r in rows]
    temps  = [r[4] for r in rows]

    cpu_min, cpu_max = min(cpus), max(cpus)
    cpu_avg = sum(cpus)/len(cpus)

    ram_min, ram_max = min(rams), max(rams)
    ram_avg = sum(rams)/len(rams)

    disk_min, disk_max = min(disks), max(disks)
    disk_avg = sum(disks)/len(disks)

    users_min, users_max = min(users_), max(users_)
    users_avg = sum(users_)/len(users_)

    temp_min, temp_max = min(temps), max(temps)
    temp_avg = sum(temps)/len(temps)

    return render_template("report.html",
                           days=days,
                           cpu_min=cpu_min, cpu_max=cpu_max, cpu_avg=cpu_avg,
                           ram_min=ram_min, ram_max=ram_max, ram_avg=ram_avg,
                           disk_min=disk_min, disk_max=disk_max, disk_avg=disk_avg,
                           users_min=users_min, users_max=users_max, users_avg=users_avg,
                           temp_min=temp_min, temp_max=temp_max, temp_avg=temp_avg
    )

# -------------- Экспорт CSV --------------

@app.route("/export")
def export_data():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    role = session["role"]

    rows = get_all_metrics(user_id, role)
    if not rows:
        return "Нет данных для экспорта."

    # rows = [ (id, timestamp, cpu, ram, disk, net_rx, net_tx, users, temp), ... ]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id","timestamp","cpu","ram","disk","net_rx","net_tx","users","temp"])
    for row in rows:
        writer.writerow(row)
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="metrics_export.csv"
    )

# -------------- Динамический дашборд --------------

@app.route("/dashboard_custom")
def dashboard_custom():
    if "logged_in" not in session:
        return redirect(url_for("login"))

    show_cpu  = (request.args.get("cpu","1")  == "1")
    show_ram  = (request.args.get("ram","1")  == "1")
    show_disk = (request.args.get("disk","1") == "1")

    return render_template("dashboard_custom.html",
                           show_cpu=show_cpu,
                           show_ram=show_ram,
                           show_disk=show_disk)

# -------------- WebSocket test --------------
@socketio.on("connect")
def on_connect():
    print("Client connected via SocketIO")
    emit("server_event", {"data":"Добро пожаловать! WebSocket connection established."})

@socketio.on("disconnect")
def on_disconnect():
    print("Client disconnected")

# ------------ Вспомогательное -----------

def generate_2fa_code():
    import random
    digits = "0123456789"
    return "".join(random.choice(digits) for _ in range(TWOFA_CODE_LENGTH))
