import sqlite3
from Monitoring_server.server_monitoring.config import DB_NAME

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS metrics (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                      cpu REAL,
                      ram REAL,
                      disk REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      username TEXT UNIQUE,
                      password TEXT)''')
    conn.commit()
    conn.close()

def save_metrics(cpu, ram, disk):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO metrics (cpu, ram, disk) VALUES (?, ?, ?)", (cpu, ram, disk))
    conn.commit()
    conn.close()

def get_latest_metrics():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT cpu, ram, disk FROM metrics ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"cpu": row[0], "ram": row[1], "disk": row[2]}
    else:
        return None