import threading
from Monitoring_server.server_monitoring.web import app
from Monitoring_server.server_monitoring.database import init_db

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
