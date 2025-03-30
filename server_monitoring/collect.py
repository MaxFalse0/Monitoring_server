import paramiko
from Monitoring_server.server_monitoring.analyze import check_alerts
from Monitoring_server.server_monitoring import database

def get_server_metrics(server_ip, server_port, username, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to server {server_ip}:{server_port}...")
        client.connect(server_ip, port=server_port, username=username, password=password)
        print("Connection established.")

        stdin, stdout, stderr = client.exec_command("top -bn1 | grep 'Cpu' | sed 's/.*, *\([0-9.]*\)%* id.*/\1/' | awk '{print 100 - $1}'")
        cpu = stdout.read().decode().strip()
        if not cpu:
            raise ValueError("Error getting CPU metric")

        stdin, stdout, stderr = client.exec_command("free | grep Mem | awk '{print $3/$2 * 100.0}'")
        ram = stdout.read().decode().strip()
        if not ram:
            raise ValueError("Error getting RAM metric")

        stdin, stdout, stderr = client.exec_command("df / | awk '/\// {print $5}' | sed 's/%//'")
        disk = stdout.read().decode().strip()
        if not disk:
            raise ValueError("Error getting disk metric")

        cpu, ram, disk = float(cpu), float(ram), float(disk)
        print(f"Metrics collected: CPU = {cpu}%, RAM = {ram}%, Disk = {disk}%")
        return cpu, ram, disk

    except Exception as e:
        print(f"Error connecting or collecting metrics: {e}")
        return None, None, None
    finally:
        client.close()

def collect_metrics(server_ip, server_port, username, password, connection_status):
    cpu, ram, disk = get_server_metrics(server_ip, server_port, username, password)
    if cpu is not None and ram is not None and disk is not None:
        print(f"Metrics collected: CPU = {cpu}%, RAM = {ram}%, Disk = {disk}%")
        database.save_metrics(cpu, ram, disk)
        connection_status["status"] = "Connection successful, metrics collected"
        connection_status["error"] = None
        try:
            check_alerts(cpu, ram, disk)
        except Exception as e:
            print(f"Error in check_alerts: {e}")
    else:
        connection_status["status"] = "Connection error"
        connection_status["error"] = "Failed to collect metrics. Check server data."