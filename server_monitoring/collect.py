import paramiko
import time
from .config import REMOTE_TEMP_SCRIPT
from .database import save_metrics
import os
from server_monitoring.analyze import check_alerts


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


def get_swap_usage(client):
    try:
        # Команда вычисляет процент использования swap
        cmd = "free | grep Swap | awk '{if ($2>0) printf \"%.1f\", $3/$2*100; else print 0}'"
        stdin, stdout, stderr = client.exec_command(cmd)
        swap_str = stdout.read().decode().strip()
        if swap_str and swap_str.replace('.', '', 1).isdigit():
            return float(swap_str)
        else:
            return 0.0
    except Exception as e:
        print(f"[SWAP ERROR] {e}")
        return 0.0


def get_uptime(client):
    try:
        # Получаем время работы в секундах из /proc/uptime и форматируем
        stdin, stdout, stderr = client.exec_command("cat /proc/uptime | awk '{print $1}'")
        uptime_str = stdout.read().decode().strip()
        if uptime_str:
            uptime_seconds = float(uptime_str)
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{days}d {hours}h {minutes}m"
        else:
            return "N/A"
    except Exception as e:
        print(f"[UPTIME ERROR] {e}")
        return "N/A"


def get_proc_thread_counts(client):
    try:
        stdin, stdout, stderr = client.exec_command("ps -e | wc -l")
        proc_str = stdout.read().decode().strip()
        procs = int(proc_str) if proc_str.isdigit() else 0

        stdin, stdout, stderr = client.exec_command("ps -eLf | wc -l")
        thread_str = stdout.read().decode().strip()
        threads = int(thread_str) if thread_str.isdigit() else 0

        return procs, threads
    except Exception as e:
        print(f"[PROC/THREAD ERROR] {e}")
        return 0, 0


def get_power_consumption(client):
    try:
        # Попытка получить энергопотребление через ipmitool
        cmd = "ipmitool sensor | grep 'Pwr Consumption' | awk '{print $NF}'"
        stdin, stdout, stderr = client.exec_command(cmd)
        power_str = stdout.read().decode().strip()
        if power_str and power_str.replace('.', '', 1).isdigit():
            return float(power_str)
        else:
            return 0.0
    except Exception as e:
        print(f"[POWER ERROR] {e}")
        return 0.0


def get_interface_errors(client):
    try:
        # Вычисляем суммарные ошибки приема (поле 4) и передачи (поле 12) для всех интерфейсов
        cmd = """
awk 'NR>2 {
    iface=$1; 
    gsub(":", "", iface);
    if (iface !~ /lo|docker|veth|br|virbr|vmnet/) {
         rx_err+=$4;
         tx_err+=$12;
    }
}
END {
    print rx_err, tx_err;
}' /proc/net/dev
"""
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode().strip().split()
        if len(out) == 2:
            return float(out[0]), float(out[1])
        else:
            return 0.0, 0.0
    except Exception as e:
        print(f"[IFACE ERROR] {e}")
        return 0.0, 0.0


def collect_metrics(server_ip, port, ssh_user, ssh_password, status_dict, tg_username, user_id):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(server_ip, port=port, username=ssh_user, password=ssh_password, timeout=10)

        status_dict["active"] = True
        status_dict["server"] = f"{server_ip}:{port}"

        while status_dict.get("active", False):
            # Объединяем несколько команд для ускорения получения базовых метрик
            combined_command = (
                "top -bn1 | grep '%Cpu' | awk '{print 100 - $8}';"
                "free | grep Mem | awk '{print $3/$2 * 100.0}';"
                "df / | tail -1 | awk '{print $5}' | tr -d '%';"
                "who | wc -l"
            )
            stdin, stdout, _ = client.exec_command(combined_command)
            output = stdout.read().decode().splitlines()
            if len(output) >= 4:
                cpu = float(output[0])
                ram = float(output[1])
                disk = float(output[2])
                users = int(output[3])
            else:
                raise Exception("Ошибка получения базовых метрик")

            # Получаем сетевые данные за 0.5 секунды
            rx1, tx1 = get_net_bytes(client)
            time.sleep(0.5)
            rx2, tx2 = get_net_bytes(client)
            net_rx = round((rx2 - rx1) / 0.5, 2)
            net_tx = round((tx2 - tx1) / 0.5, 2)

            # Остальные метрики
            temp = get_temp(client)
            swap = get_swap_usage(client)
            uptime_str = get_uptime(client)
            procs, threads = get_proc_thread_counts(client)
            rx_err, tx_err = get_interface_errors(client)
            power = get_power_consumption(client)

            metrics = {
                "cpu": round(cpu, 1),
                "ram": round(ram),
                "disk": round(disk, 1),
                "users": users,
                "temp": round(temp, 1) if temp is not None else None,
                "net_rx": net_rx,
                "net_tx": net_tx,
                "swap": round(swap, 1),
                "uptime": uptime_str,
                "processes": procs,
                "threads": threads,
                "rx_err": rx_err,
                "tx_err": tx_err,
                "power": round(power, 1)
            }

            print(f"Metrics: CPU={metrics['cpu']}%, RAM={metrics['ram']}%, Disk={metrics['disk']}%, Users={users}, "
                  f"Temp={metrics['temp']}°C, RX={net_rx} B/s, TX={net_tx} B/s, Swap={metrics['swap']}%, "
                  f"Uptime={uptime_str}, Procs={procs}, Threads={threads}, RX_err={rx_err}, TX_err={tx_err}, "
                  f"Power={metrics['power']}W")

            save_metrics(
                user_id=user_id,
                cpu=metrics["cpu"],
                ram=metrics["ram"],
                disk=metrics["disk"],
                net_rx=metrics["net_rx"],
                net_tx=metrics["net_tx"],
                users=metrics["users"],
                temp=metrics["temp"],
                swap=metrics["swap"],
                uptime=metrics["uptime"],
                processes=metrics["processes"],
                threads=metrics["threads"],
                rx_err=metrics["rx_err"],
                tx_err=metrics["tx_err"],
                power=metrics["power"]
            )

            check_alerts(
                cpu=metrics["cpu"],
                ram=metrics["ram"],
                disk=metrics["disk"],
                telegram_username=tg_username,
                users=metrics["users"],
                temp=metrics["temp"],
                server_ip=server_ip
            )

            status_dict["status"] = "Сервер подключён и данные собираются"
            status_dict["error"] = None

            time.sleep(3)  # сбор метрик каждые 3 секунды
    except Exception as e:
        print(f"[COLLECT ERROR] {e}")
        status_dict["status"] = "Ошибка подключения"
        status_dict["error"] = str(e)
    finally:
        status_dict["active"] = False
        status_dict["server"] = None
        client.close()
