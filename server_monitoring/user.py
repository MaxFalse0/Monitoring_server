from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, username, telegram_username, twofa_enabled, role):
        self.id = id
        self.username = username
        self.telegram_username = telegram_username
        self.twofa_enabled = twofa_enabled
        self.role = role
