from server_monitoring.web import app
from server_monitoring.socketio_manager import socketio
from server_monitoring.database import init_db

if __name__ == "__main__":
    init_db()
    socketio.run(app, debug=True, host="127.0.0.1", port=5000)
