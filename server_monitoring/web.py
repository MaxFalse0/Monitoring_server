import threading
import random
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from server_monitoring.collect import collect_metrics
from server_monitoring.auth import login_user, register_user
from server_monitoring import database
from server_monitoring.analyze import send_telegram_alert
from server_monitoring.config import TWOFA_CODE_LENGTH

app = Flask(__name__)
app.secret_key = "supersecretkey"

connection_status = {"status": "Waiting for connection", "error": None}

@app.before_request
def check_session():
    """
    Разрешаем доступ к /login, /register, /twofa_verify, /static и всё остальное
    требует 'logged_in' в session.

    Если есть partial_login (логин/пароль прошли, но 2FA не подтверждена),
    пускаем только на /twofa_verify.
    """
    allowed_routes = ("login", "register", "twofa_verify", "static")
    if request.endpoint not in allowed_routes and "logged_in" not in session:
        # Если пользователь ввёл логин/пароль, но ещё не ввёл 2FA-код
        if "partial_login" in session:
            if request.endpoint != "twofa_verify":
                return redirect(url_for("twofa_verify"))
        else:
            return redirect(url_for("login"))


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
    """
    Авторизация + проверка, включена ли 2FA
    """
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = login_user(username, password)
        if user:
            # Если 2FA включена и у пользователя есть telegram_username
            if user["twofa_enabled"] == 1 and user["telegram_username"]:
                # Генерируем код
                twofa_code = generate_2fa_code()
                # Сохраняем в session
                session["twofa_code"] = twofa_code
                session["partial_login"] = True
                session["user_id"] = user["id"]
                # Шлём код
                msg = f"Ваш код для входа: {twofa_code}"
                send_telegram_alert(user["telegram_username"], msg)
                return redirect(url_for("twofa_verify"))
            else:
                # Если 2FA не нужна
                session["logged_in"] = True
                session["user_id"] = user["id"]
                session["telegram_username"] = user["telegram_username"]
                return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Неверный логин или пароль.")
    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
def dashboard():
    """
    Главная страница.
    """
    global connection_status
    if request.method == "POST":
        server_ip = request.form["server_ip"]
        server_port = int(request.form["server_port"])
        ssh_user = request.form["username"]
        ssh_password = request.form["password"]

        connection_status["status"] = "Connecting to server..."
        connection_status["error"] = None

        tg_username = session.get("telegram_username")
        threading.Thread(
            target=collect_metrics,
            args=(server_ip, server_port, ssh_user, ssh_password, connection_status, tg_username),
            daemon=True
        ).start()

        return render_template("index.html",
                               message=connection_status["status"],
                               metrics=None,
                               status=connection_status)

    return render_template("index.html",
                           message="Enter server data to start monitoring.",
                           metrics=None,
                           status=connection_status)


@app.route("/data")
def get_data():
    latest_metrics = database.get_latest_metrics()
    return jsonify({"metrics": latest_metrics, "status": connection_status})


# -------------- Telegram Connect --------------

@app.route("/tg_connect", methods=["GET", "POST"])
def tg_connect():
    """
    Страница подключения телеграм-бота (сохраняем chat_id).
    При успехе отправляем в Telegram приветственное сообщение.
    """
    if "logged_in" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = database.get_user_by_id(user_id)

    if request.method == "POST":
        new_tg = request.form["telegram_username"].strip()
        database.update_user_telegram(user_id, new_tg)
        session["telegram_username"] = new_tg

        # Отправим в Telegram сообщение, что бот подключен
        send_telegram_alert(new_tg, "Вы успешно подключили бота!")

        return redirect(url_for("tg_connect"))

    return render_template("tg_connect.html",
                           current_tg=user["telegram_username"],
                           bot_name="@YourMonitoringBotHere")


# -------------- 2FA ----------------

@app.route("/twofa_setup", methods=["GET", "POST"])
def twofa_setup():
    """
    Включение/выключение 2FA, если есть Telegram.
    """
    if "logged_in" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = database.get_user_by_id(user_id)
    if not user["telegram_username"]:
        return render_template("twofa_setup.html",
                               error="Сначала подключите Telegram на странице /tg_connect",
                               twofa_enabled=user["twofa_enabled"])

    if request.method == "POST":
        action = request.form.get("action")
        if action == "enable":
            database.set_twofa_enabled(user_id, True)
            send_telegram_alert(user["telegram_username"], "2FA включена. При следующем входе потребуется код.")
        elif action == "disable":
            database.set_twofa_enabled(user_id, False)
            send_telegram_alert(user["telegram_username"], "2FA выключена. Теперь вход только по паролю.")

        return redirect(url_for("twofa_setup"))

    return render_template("twofa_setup.html",
                           error=None,
                           twofa_enabled=user["twofa_enabled"])


@app.route("/twofa_verify", methods=["GET", "POST"])
def twofa_verify():
    """
    Пользователь вводит одноразовый код.
    Если верно -> logged_in=True
    """
    if "partial_login" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        code = request.form["code"].strip()
        if code == session.get("twofa_code"):
            # Успешно
            user_id = session["user_id"]
            user = database.get_user_by_id(user_id)

            session["logged_in"] = True
            session.pop("partial_login", None)
            session.pop("twofa_code", None)
            session["telegram_username"] = user["telegram_username"]

            return redirect(url_for("dashboard"))
        else:
            return render_template("twofa_verify.html", error="Неверный код, попробуйте ещё раз.")

    return render_template("twofa_verify.html", error=None)


# ---------------- Helper ----------------

def generate_2fa_code():
    digits = "0123456789"
    return "".join(random.choice(digits) for _ in range(TWOFA_CODE_LENGTH))
