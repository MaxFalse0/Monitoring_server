import sqlite3
from server_monitoring.config import DB_NAME

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Таблица метрик
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            cpu REAL,
            ram REAL,
            disk REAL,
            net_rx REAL,
            net_tx REAL
        )
    ''')

    # Таблица пользователей (добавили telegram_username и twofa_enabled)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            telegram_username TEXT,
            twofa_enabled INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def save_metrics(cpu, ram, disk, net_rx, net_tx):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO metrics (cpu, ram, disk, net_rx, net_tx)
        VALUES (?, ?, ?, ?, ?)
    ''', (cpu, ram, disk, net_rx, net_tx))
    conn.commit()
    conn.close()

def get_latest_metrics():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT cpu, ram, disk, net_rx, net_tx
        FROM metrics
        ORDER BY id DESC
        LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "cpu": row[0],
            "ram": row[1],
            "disk": row[2],
            "net_rx": row[3],
            "net_tx": row[4]
        }
    return None

def update_user_telegram(user_id, telegram_username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users
        SET telegram_username=?
        WHERE id=?
    ''', (telegram_username, user_id))
    conn.commit()
    conn.close()

def get_user_by_id(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, password, telegram_username, twofa_enabled
        FROM users
        WHERE id=?
    ''', (user_id,))
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

def set_twofa_enabled(user_id, enable: bool):
    """
    Включаем/выключаем 2FA. enable=True -> 1, enable=False -> 0
    """
    val = 1 if enable else 0
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users
        SET twofa_enabled=?
        WHERE id=?
    ''', (val, user_id))
    conn.commit()
    conn.close()
