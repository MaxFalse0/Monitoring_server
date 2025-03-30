from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import threading
from Monitoring_server.server_monitoring.collect import collect_metrics
from Monitoring_server.server_monitoring.auth import login_user, register_user
from Monitoring_server.server_monitoring import database

from Monitoring_server.server_monitoring.database import init_db

app = Flask(__name__)
app.secret_key = "supersecretkey"

connection_status = {"status": "Waiting for connection", "error": None}


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        try:
            register_user(username, password)
            return redirect(url_for("login"))
        except Exception as e:
            return render_template("register.html", error=f"Ошибка регистрации: {str(e)}")
    return render_template("register.html", error=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = login_user(username, password)
        if user:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Неверный логин или пароль. Попробуйте снова или зарегистрируйтесь.")
    return render_template("login.html", error=None)


@app.route("/", methods=["GET", "POST"])
def dashboard():
    global connection_status
    if "logged_in" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        server_ip = request.form["server_ip"]
        server_port = int(request.form["server_port"])
        username = request.form["username"]
        password = request.form["password"]

        connection_status["status"] = "Connecting to server..."
        connection_status["error"] = None

        threading.Thread(
            target=collect_metrics,
            args=(server_ip, server_port, username, password, connection_status),
            daemon=True
        ).start()

        return render_template("index.html", message=connection_status["status"], metrics=None,
                               status=connection_status)

    return render_template("index.html", message="Enter server data to start monitoring.", metrics=None,
                           status=connection_status)


@app.route("/data")
def get_data():
    if "logged_in" not in session:
        return jsonify({"error": "Not authorized"})
    latest_metrics = database.get_latest_metrics()
    return jsonify({"metrics": latest_metrics, "status": connection_status})


if __name__ == "__main__":
    init_db()
    try:
        register_user("admin", "admin")
        print("Test user created: admin/admin")
    except Exception as e:
        print("Test user already exists")
    app.run(debug=True)
