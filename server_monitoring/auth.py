import sqlite3
from server_monitoring.config import DB_NAME
from werkzeug.security import generate_password_hash, check_password_hash

def register_user(username, password):
    hashed = generate_password_hash(password)  # хешируем пароль
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Проверим, нет ли пользователя с таким именем:
    cursor.execute("SELECT id FROM users WHERE username=?", (username,))
    existing = cursor.fetchone()
    if existing:
        raise Exception("Пользователь с таким именем уже существует.")
    cursor.execute('''
        INSERT INTO users (username, password)
        VALUES (?, ?)
    ''', (username, hashed))
    conn.commit()
    conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, password, telegram_username, twofa_enabled, role
        FROM users
        WHERE username=?
    ''', (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        user_id, user_name, user_pass, user_tg, user_2fa, user_role = row
        # Проверяем хеш
        if check_password_hash(user_pass, password):
            return {
                "id": user_id,
                "username": user_name,
                "password": user_pass,
                "telegram_username": user_tg,
                "twofa_enabled": user_2fa,
                "role": user_role
            }
    return None
