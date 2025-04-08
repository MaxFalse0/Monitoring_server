# server_monitoring/celery_worker.py

from celery import Celery
from server_monitoring.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from server_monitoring.collect import collect_metrics

celery = Celery('server_monitoring', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

@celery.task
def task_collect_metrics(server_ip, port, ssh_user, ssh_password, user_id, tg_username):
    """
    Асинхронная задача для сбора метрик. Вызывается через Celery.
    """
    print(f"[Celery] Starting metric collection for {server_ip}:{port} for user_id={user_id}")
    # Обратите внимание: для обратной связи в UI используется connection_status в веб-приложении,
    # здесь же мы просто вызываем функцию сбора метрик.
    status_dict = {"status": "Task started", "active": True, "error": None}
    collect_metrics(server_ip, port, ssh_user, ssh_password, status_dict, tg_username, user_id)
