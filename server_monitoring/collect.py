import paramiko
import time
from .config import REMOTE_TEMP_SCRIPT
from .database import save_metrics
import os


def get_net_bytes(client):
    cmd = """
        awk '
        NR>2 {
            iface=$1;
            gsub(":", "", iface);
            if (iface !~ /lo|docker|veth|br|virbr|vmnet/) {
                rx+=$2;
                tx+=$10;
            }
        }
        END {
            print rx, tx;
        }' /proc/net/dev
    """
    try:
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode().strip().split()
        if len(out) == 2:
            return float(out[0]), float(out[1])
    except Exception as e:
        print(f"[NET ERROR] {e}")
    return 0.0, 0.0


def get_temp(client):
    try:
        sftp = client.open_sftp()
        sftp.put("server_monitoring/static/scripts/get_temp.sh", REMOTE_TEMP_SCRIPT)
        sftp.chmod(REMOTE_TEMP_SCRIPT, 0o755)
        sftp.close()

        stdin, stdout, _ = client.exec_command(f"bash {REMOTE_TEMP_SCRIPT}")
        temp_str = stdout.read().decode().strip()

        if temp_str and temp_str.replace('.', '', 1).isdigit():
            temp = float(temp_str)
            return temp if temp > 0 else None
        else:
            return None
    except Exception as e:
        print(f"[TEMP ERROR] {e}")
        return None



def collect_metrics(server_ip, port, ssh_user, ssh_password, status_dict, tg_username, user_id):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(server_ip, port=port, username=ssh_user, password=ssh_password, timeout=10)

        while True:
            stdin, stdout, _ = client.exec_command("top -bn1 | grep '%Cpu' | awk '{print 100 - $8}'")
            cpu = float(stdout.read().decode().strip())

            stdin, stdout, _ = client.exec_command("free | grep Mem | awk '{print $3/$2 * 100.0}'")
            ram = float(stdout.read().decode().strip())

            stdin, stdout, _ = client.exec_command("df / | tail -1 | awk '{print $5}'")
            disk = float(stdout.read().decode().strip().replace('%', ''))

            stdin, stdout, _ = client.exec_command("who | wc -l")
            users = int(stdout.read().decode().strip())

            temp = get_temp(client)

            rx1, tx1 = get_net_bytes(client)
            time.sleep(2)
            rx2, tx2 = get_net_bytes(client)
            delta_rx = rx2 - rx1
            delta_tx = tx2 - tx1

            net_rx = delta_rx / 2  # B/s
            net_tx = delta_tx / 2  # B/s

            metrics = {
                "cpu": round(cpu, 1),
                "ram": round(ram, 4),
                "disk": round(disk, 1),
                "users": users,
                "temp": round(temp, 1) if temp is not None else None,
                "net_rx": round(net_rx, 2),
                "net_tx": round(net_tx, 2)
            }

            print(
                f"Metrics: CPU={metrics['cpu']}%, RAM={metrics['ram']}%, Disk={metrics['disk']}%, Users={users}, Temp={metrics['temp']}°C, RX={net_rx} B/s, TX={net_tx} B/s")

            save_metrics(
                user_id=user_id,
                cpu=metrics["cpu"],
                ram=metrics["ram"],
                disk=metrics["disk"],
                users=metrics["users"],
                temp=metrics["temp"],
                net_rx=metrics["net_rx"],
                net_tx=metrics["net_tx"]
            )

            status_dict["status"] = "Сервер подключён и данные собираются"
            status_dict["error"] = None

    except Exception as e:
        print(f"[COLLECT ERROR] {e}")
        status_dict["status"] = "Ошибка подключения"
        status_dict["error"] = str(e)
