import paramiko
from server_monitoring.analyze import check_alerts
from server_monitoring import database

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

        # Net (первый не-lo)
        cmd_net = "cat /proc/net/dev | grep -v 'lo:' | grep ':' | head -n 1 | awk '{print $2, $10}'"
        stdin, stdout, stderr = client.exec_command(cmd_net)
        net_data = stdout.read().decode().strip().split()
        if len(net_data) != 2:
            raise ValueError("Error getting network metrics")
        net_rx, net_tx = map(float, net_data)

        if not all([cpu, ram, disk]):
            raise ValueError("Error getting CPU/RAM/Disk")

        cpu, ram, disk = float(cpu), float(ram), float(disk)
        print(f"Metrics collected: CPU={cpu}%, RAM={ram}%, Disk={disk}%, Net RX={net_rx}, Net TX={net_tx}")
        return cpu, ram, disk, net_rx, net_tx

    except Exception as e:
        print(f"Error collecting metrics: {e}")
        return None, None, None, None, None
    finally:
        client.close()

def collect_metrics(server_ip, server_port, username, password, connection_status, telegram_username=None):
    cpu, ram, disk, net_rx, net_tx = get_server_metrics(server_ip, server_port, username, password)
    if None not in (cpu, ram, disk):
        database.save_metrics(cpu, ram, disk, net_rx, net_tx)
        connection_status["status"] = "Connection successful, metrics collected"
        connection_status["error"] = None
        try:
            check_alerts(cpu, ram, disk, telegram_username)
        except Exception as e:
            print(f"Error in check_alerts: {e}")
    else:
        connection_status["status"] = "Connection error"
        connection_status["error"] = "Failed to collect metrics. Check server data."
