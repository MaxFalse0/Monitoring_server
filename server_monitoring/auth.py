import sqlite3
from server_monitoring.config import DB_NAME

def register_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (username, password)
        VALUES (?, ?)
    ''', (username, password))
    conn.commit()
    conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, password, telegram_username, twofa_enabled
        FROM users
        WHERE username=? AND password=?
    ''', (username, password))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "password": row[2],
            "telegram_username": row[3],
            "twofa_enabled": row[4]
        }
    return None
