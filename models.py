"""
Models for Flask-Login and database operations
"""

from flask_login import UserMixin


class User(UserMixin):
    """User model for Flask-Login"""

    def __init__(self, user_id, name, email, password, role):
        self.id = user_id
        self.user_id = user_id
        self.name = name
        self.email = email
        self.password = password
        self.role = role

    def get_id(self):
        return str(self.user_id)

    def is_admin(self):
        return self.role == 'admin'

    def is_doctor(self):
        return self.role == 'doctor'

    def is_patient(self):
        return self.role == 'patient'