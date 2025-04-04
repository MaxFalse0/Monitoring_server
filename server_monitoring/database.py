import sqlite3
import datetime
from server_monitoring.config import DB_NAME, DATA_RETENTION_DAYS

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

    # Таблица пользователей
    # Добавляем role (админ/юзер)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            telegram_username TEXT,
            twofa_enabled INTEGER DEFAULT 0,
            role TEXT DEFAULT 'user'
        )
    ''')

    # Таблица серверов (для многосерверного мониторинга)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            ip TEXT,
            port INTEGER,
            ssh_user TEXT,
            ssh_password TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
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
        SELECT id, username, password, telegram_username, twofa_enabled, role
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
            "twofa_enabled": row[4],
            "role": row[5]
        }
    return None

def set_twofa_enabled(user_id, enable: bool):
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

def set_user_role(user_id, role):
    """
    Пример: admin может назначать роли user -> admin
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users
        SET role=?
        WHERE id=?
    ''', (role, user_id))
    conn.commit()
    conn.close()

# ----------- SERVERS -----------

def create_server(user_id, name, ip, port, ssh_user, ssh_password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO servers (user_id, name, ip, port, ssh_user, ssh_password)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, name, ip, port, ssh_user, ssh_password))
    conn.commit()
    conn.close()

def get_servers_for_user(user_id, user_role):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if user_role == 'admin':
        cursor.execute('''
            SELECT id, user_id, name, ip, port, ssh_user, ssh_password
            FROM servers
            ORDER BY id
        ''')
    else:
        cursor.execute('''
            SELECT id, user_id, name, ip, port, ssh_user, ssh_password
            FROM servers
            WHERE user_id=?
            ORDER BY id
        ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    servers = []
    for r in rows:
        servers.append({
            "id": r[0],
            "user_id": r[1],
            "name": r[2],
            "ip": r[3],
            "port": r[4],
            "ssh_user": r[5],
            "ssh_password": r[6],
        })
    return servers

def get_server_by_id(server_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, name, ip, port, ssh_user, ssh_password
        FROM servers
        WHERE id=?
    ''', (server_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "user_id": row[1],
            "name": row[2],
            "ip": row[3],
            "port": row[4],
            "ssh_user": row[5],
            "ssh_password": row[6],
        }
    return None

def update_server(server_id, name, ip, port, ssh_user, ssh_password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE servers
        SET name=?, ip=?, port=?, ssh_user=?, ssh_password=?
        WHERE id=?
    ''', (name, ip, port, ssh_user, ssh_password, server_id))
    conn.commit()
    conn.close()

def delete_server(server_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM servers WHERE id=?', (server_id,))
    conn.commit()
    conn.close()

# ----------- REPORTS & CLEANUP --------------

def get_metrics_for_period(days=1):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT cpu, ram, disk, timestamp
        FROM metrics
        WHERE timestamp >= datetime('now', ?)
        ORDER BY timestamp ASC
    ''', (f'-{days} days',))
    rows = cursor.fetchall()
    conn.close()
    return rows

def cleanup_old_metrics():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM metrics
        WHERE timestamp < datetime('now', ?)
    ''', (f'-{DATA_RETENTION_DAYS} days',))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"cleanup_old_metrics: Deleted {deleted} old rows")

def get_all_metrics():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, timestamp, cpu, ram, disk, net_rx, net_tx
        FROM metrics
        ORDER BY id ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows
