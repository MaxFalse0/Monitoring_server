import sqlite3
from server_monitoring.config import DB_NAME
from werkzeug.security import generate_password_hash, check_password_hash
import re

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

    # Хешируем и сохраняем
    hashed = generate_password_hash(password)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username=?", (username,))
    if cursor.fetchone():
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
