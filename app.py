"""
Hospital Management System - Main Application
Flask-based HMS with Admin, Doctor, and Patient roles
"""
from flask import Flask, g
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

# Import blueprints
from blueprints.admin import admin_bp
from blueprints.doctor import doctor_bp
from blueprints.patient import patient_bp
from blueprints.auth import auth_bp

# Import database and models
from database import init_db, get_db
from models import User

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['DATABASE'] = 'hospital.db'

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    cursor = db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        return User(user_data['user_id'], user_data['name'], user_data['email'],
                    user_data['password'], user_data['role'])
    return None


# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(doctor_bp, url_prefix='/doctor')
app.register_blueprint(patient_bp, url_prefix='/patient')


@app.route('/')
def index():
    """Home page - redirect based on user role"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'doctor':
            return redirect(url_for('doctor.dashboard'))
        elif current_user.role == 'patient':
            return redirect(url_for('patient.dashboard'))
    return redirect(url_for('auth.login'))


@app.teardown_appcontext
def close_connection(exception):
    """Close database connection"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


if __name__ == '__main__':
    # Initialize database on first run
    if not os.path.exists('hospital.db'):
        print("Creating database and tables...")
        init_db()
        print("Database initialized successfully!")

    app.run(debug=True, port=5000)