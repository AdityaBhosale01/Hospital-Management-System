"""
Authentication Blueprint - Login, Logout, Register
blueprints/auth.py
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login route"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Please provide both email and password', 'danger')
            return render_template('auth/login.html')

        db = get_db()
        cursor = db.execute('SELECT * FROM users WHERE email = ?', (email,))
        user_data = cursor.fetchone()

        if user_data and check_password_hash(user_data['password'], password):
            # Check if user is blacklisted
            if user_data['status'] == 'blacklisted':
                flash('Your account has been suspended. Please contact admin.', 'danger')
                return render_template('auth/login.html')

            user = User(user_data['user_id'], user_data['name'], user_data['email'],
                        user_data['password'], user_data['role'])
            login_user(user)

            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'doctor':
                return redirect(url_for('doctor.dashboard'))
            elif user.role == 'patient':
                return redirect(url_for('patient.dashboard'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Patient registration route"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        age = request.form.get('age')
        gender = request.form.get('gender')
        contact = request.form.get('contact')
        address = request.form.get('address')
        blood_group = request.form.get('blood_group')
        emergency_contact = request.form.get('emergency_contact')

        # Validation
        if not all([name, email, password, confirm_password]):
            flash('Please fill in all required fields', 'danger')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return render_template('auth/register.html')

        db = get_db()

        # Check if email already exists
        cursor = db.execute('SELECT * FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            flash('Email already registered', 'danger')
            return render_template('auth/register.html')

        try:
            # Create user
            hashed_password = generate_password_hash(password)
            cursor = db.execute('''
                INSERT INTO users (name, email, password, role, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, email, hashed_password, 'patient', 'active'))

            user_id = cursor.lastrowid

            # Create patient record
            db.execute('''
                INSERT INTO patients (user_id, age, gender, contact, address, blood_group, emergency_contact, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, age, gender, contact, address, blood_group, emergency_contact, 'active'))

            db.commit()

            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout route"""
    logout_user()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('auth.login'))