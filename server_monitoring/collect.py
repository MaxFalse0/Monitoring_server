import paramiko
from server_monitoring.analyze import check_alerts
from server_monitoring import database
from flask_socketio import SocketIO, emit

# socketio нужно либо импортировать отдельно,
# либо передавать как параметр. Предположим, что у нас общий объект.
from server_monitoring.socketio_manager import socketio  # Если circular import, выносим socketio в init.


def get_server_metrics(server_ip, server_port, username, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {server_ip}:{server_port}...")
        client.connect(server_ip, port=server_port, username=username, password=password)
        print("Connection established.")

        # CPU
        stdin, stdout, stderr = client.exec_command(
            "top -bn1 | grep 'Cpu' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'"
        )
        cpu = stdout.read().decode().strip()

        # RAM
        stdin, stdout, stderr = client.exec_command("free | grep Mem | awk '{print $3/$2 * 100.0}'")
        ram = stdout.read().decode().strip()

        # Disk
        stdin, stdout, stderr = client.exec_command("df / | awk '/\\// {print $5}' | sed 's/%//'")
        disk = stdout.read().decode().strip()

        # Net
        cmd_net = "cat /proc/net/dev | grep -v 'lo:' | grep ':' | head -n 1 | awk '{print $2, $10}'"
        stdin, stdout, stderr = client.exec_command(cmd_net)
        net_data = stdout.read().decode().strip().split()
        net_rx, net_tx = map(float, net_data) if len(net_data) == 2 else (0.0, 0.0)

        # Users
        stdin, stdout, stderr = client.exec_command("who | wc -l")
        users = int(stdout.read().decode().strip())

        # Temperature
        stdin, stdout, stderr = client.exec_command("cat /sys/class/thermal/thermal_zone0/temp")
        temp_raw = stdout.read().decode().strip()
        temp = float(temp_raw) / 1000 if temp_raw.isdigit() else 0.0

        if not cpu or not ram or not disk:
            raise ValueError("Error getting CPU/RAM/Disk")

        cpu, ram, disk = float(cpu), float(ram), float(disk)
        print(
            f"Metrics collected: CPU={cpu}%, RAM={ram}%, Disk={disk}%, Users={users}, Temp={temp}°C, Net RX={net_rx}, Net TX={net_tx}")
        return cpu, ram, disk, net_rx, net_tx, users, temp

    except Exception as e:
        print(f"Error collecting metrics: {e}")
        return None, None, None, None, None, None, None
    finally:
        client.close()


def collect_metrics(server_ip, server_port, username, password,
                    connection_status, telegram_username=None, user_id=None):
    result = get_server_metrics(server_ip, server_port, username, password)
    if None not in result:
        cpu, ram, disk, net_rx, net_tx, users, temp = result
        database.save_metrics(user_id, cpu, ram, disk, net_rx, net_tx, users, temp)
        connection_status["status"] = "Connection successful, metrics collected"
        connection_status["error"] = None

        # WebSocket push
        socketio.emit("new_metrics", {
            "cpu": cpu, "ram": ram, "disk": disk,
            "net_rx": net_rx, "net_tx": net_tx,
            "users": users, "temp": temp
        })

        try:
            check_alerts(cpu, ram, disk, telegram_username, users, temp)
        except Exception as e:
            print(f"Error in check_alerts: {e}")
    else:
        connection_status["status"] = "Connection error"
        connection_status["error"] = "Failed to collect metrics. Check server data."
