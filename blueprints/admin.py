"""
Admin Blueprint - Dashboard, Doctor Management, Patient Management, Appointments
blueprints/admin.py
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.security import generate_password_hash
from database import get_db
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator to require admin role"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with statistics"""
    db = get_db()

    # Get counts
    doctors_count = db.execute('SELECT COUNT(*) as count FROM doctors WHERE status = "active"').fetchone()['count']
    patients_count = db.execute('SELECT COUNT(*) as count FROM patients WHERE status = "active"').fetchone()['count']
    appointments_count = db.execute('SELECT COUNT(*) as count FROM appointments').fetchone()['count']

    # Recent appointments
    recent_appointments = db.execute('''
        SELECT a.*, 
               u1.name AS patient_name, 
               u2.name AS doctor_name, 
               doc.specialization
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN users u1 ON p.user_id = u1.user_id
        JOIN doctors doc ON a.doctor_id = doc.doctor_id
        JOIN users u2 ON doc.user_id = u2.user_id
        JOIN departments d ON doc.dept_id = d.dept_id
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 10
    ''').fetchall()

    # Appointments by status
    status_stats = db.execute('''
        SELECT status, COUNT(*) as count
        FROM appointments
        GROUP BY status
    ''').fetchall()

    return render_template('admin/dashboard.html',
                           doctors_count=doctors_count,
                           patients_count=patients_count,
                           appointments_count=appointments_count,
                           recent_appointments=recent_appointments,
                           status_stats=status_stats)


@admin_bp.route('/doctors')
@login_required
@admin_required
def doctors():
    """List all doctors"""
    db = get_db()
    search = request.args.get('search', '')

    if search:
        doctors_list = db.execute('''
            SELECT d.*, u.name, u.email, u.status as user_status, dept.name as dept_name
            FROM doctors d
            JOIN users u ON d.user_id = u.user_id
            LEFT JOIN departments dept ON d.dept_id = dept.dept_id
            WHERE u.name LIKE ? OR d.specialization LIKE ?
            ORDER BY u.name
        ''', (f'%{search}%', f'%{search}%')).fetchall()
    else:
        doctors_list = db.execute('''
            SELECT d.*, u.name, u.email, u.status as user_status, dept.name as dept_name
            FROM doctors d
            JOIN users u ON d.user_id = u.user_id
            LEFT JOIN departments dept ON d.dept_id = dept.dept_id
            ORDER BY u.name
        ''').fetchall()

    return render_template('admin/doctors.html', doctors=doctors_list, search=search)


@admin_bp.route('/doctor/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_doctor():
    """Add new doctor"""
    db = get_db()

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        specialization = request.form.get('specialization')
        dept_id = request.form.get('dept_id')
        contact = request.form.get('contact')
        qualification = request.form.get('qualification')
        experience = request.form.get('experience')

        # Validation
        if not all([name, email, password, specialization]):
            flash('Please fill in all required fields', 'danger')
            departments = db.execute('SELECT * FROM departments ORDER BY name').fetchall()
            return render_template('admin/add_doctor.html', departments=departments)

        # Check if email exists
        existing = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            flash('Email already exists', 'danger')
            departments = db.execute('SELECT * FROM departments ORDER BY name').fetchall()
            return render_template('admin/add_doctor.html', departments=departments)

        try:
            # Create user
            hashed_password = generate_password_hash(password)
            cursor = db.execute('''
                INSERT INTO users (name, email, password, role, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, email, hashed_password, 'doctor', 'active'))

            user_id = cursor.lastrowid

            # Create doctor record
            db.execute('''
                INSERT INTO doctors (user_id, specialization, dept_id, contact, qualification, experience, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, specialization, dept_id, contact, qualification, experience, 'active'))

            doctor_id = cursor.lastrowid

            # Add default availability for next 7 days
            for i in range(7):
                date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
                time_slots = [('09:00', '12:00'), ('14:00', '17:00')]
                for start, end in time_slots:
                    db.execute('''
                        INSERT INTO doctor_availability (doctor_id, date, start_time, end_time, is_available)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (doctor_id, date, start, end, 1))

            db.commit()
            flash('Doctor added successfully!', 'success')
            return redirect(url_for('admin.doctors'))

        except Exception as e:
            db.rollback()
            flash(f'Error adding doctor: {str(e)}', 'danger')

    departments = db.execute('SELECT * FROM departments ORDER BY name').fetchall()
    return render_template('admin/add_doctor.html', departments=departments)


@admin_bp.route('/doctor/edit/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_doctor(doctor_id):
    """Edit doctor details"""
    db = get_db()

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        specialization = request.form.get('specialization')
        dept_id = request.form.get('dept_id')
        contact = request.form.get('contact')
        qualification = request.form.get('qualification')
        experience = request.form.get('experience')
        status = request.form.get('status')

        try:
            # Get doctor's user_id
            doctor = db.execute('SELECT user_id FROM doctors WHERE doctor_id = ?', (doctor_id,)).fetchone()

            # Update user
            db.execute('''
                UPDATE users SET name = ?, email = ?, status = ?
                WHERE user_id = ?
            ''', (name, email, status, doctor['user_id']))

            # Update doctor
            db.execute('''
                UPDATE doctors SET specialization = ?, dept_id = ?, contact = ?, 
                qualification = ?, experience = ?, status = ?
                WHERE doctor_id = ?
            ''', (specialization, dept_id, contact, qualification, experience, status, doctor_id))

            db.commit()
            flash('Doctor updated successfully!', 'success')
            return redirect(url_for('admin.doctors'))

        except Exception as e:
            db.rollback()
            flash(f'Error updating doctor: {str(e)}', 'danger')

    doctor = db.execute('''
        SELECT d.*, u.name, u.email, u.status as user_status
        FROM doctors d
        JOIN users u ON d.user_id = u.user_id
        WHERE d.doctor_id = ?
    ''', (doctor_id,)).fetchone()

    departments = db.execute('SELECT * FROM departments ORDER BY name').fetchall()
    return render_template('admin/edit_doctor.html', doctor=doctor, departments=departments)


@admin_bp.route('/doctor/delete/<int:doctor_id>')
@login_required
@admin_required
def delete_doctor(doctor_id):
    """Delete/blacklist doctor"""
    db = get_db()
    try:
        doctor = db.execute('SELECT user_id FROM doctors WHERE doctor_id = ?', (doctor_id,)).fetchone()

        # Update status to blacklisted
        db.execute('UPDATE users SET status = ? WHERE user_id = ?', ('blacklisted', doctor['user_id']))
        db.execute('UPDATE doctors SET status = ? WHERE doctor_id = ?', ('blacklisted', doctor_id))

        db.commit()
        flash('Doctor has been blacklisted', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('admin.doctors'))


@admin_bp.route('/patients')
@login_required
@admin_required
def patients():
    """List all patients"""
    db = get_db()
    search = request.args.get('search', '')

    if search:
        patients_list = db.execute('''
            SELECT p.*, u.name, u.email, u.status as user_status
            FROM patients p
            JOIN users u ON p.user_id = u.user_id
            WHERE u.name LIKE ? OR p.contact LIKE ? OR p.patient_id LIKE ?
            ORDER BY u.name
        ''', (f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()
    else:
        patients_list = db.execute('''
            SELECT p.*, u.name, u.email, u.status as user_status
            FROM patients p
            JOIN users u ON p.user_id = u.user_id
            ORDER BY u.name
        ''').fetchall()

    return render_template('admin/patients.html', patients=patients_list, search=search)


@admin_bp.route('/patient/edit/<int:patient_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_patient(patient_id):
    """Edit patient details"""
    db = get_db()

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        age = request.form.get('age')
        gender = request.form.get('gender')
        contact = request.form.get('contact')
        address = request.form.get('address')
        blood_group = request.form.get('blood_group')
        emergency_contact = request.form.get('emergency_contact')
        status = request.form.get('status')

        try:
            patient = db.execute('SELECT user_id FROM patients WHERE patient_id = ?', (patient_id,)).fetchone()

            db.execute('UPDATE users SET name = ?, email = ?, status = ? WHERE user_id = ?',
                       (name, email, status, patient['user_id']))

            db.execute('''
                UPDATE patients SET age = ?, gender = ?, contact = ?, address = ?,
                blood_group = ?, emergency_contact = ?, status = ?
                WHERE patient_id = ?
            ''', (age, gender, contact, address, blood_group, emergency_contact, status, patient_id))

            db.commit()
            flash('Patient updated successfully!', 'success')
            return redirect(url_for('admin.patients'))

        except Exception as e:
            db.rollback()
            flash(f'Error: {str(e)}', 'danger')

    patient = db.execute('''
        SELECT p.*, u.name, u.email, u.status as user_status
        FROM patients p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.patient_id = ?
    ''', (patient_id,)).fetchone()

    return render_template('admin/edit_patient.html', patient=patient)


@admin_bp.route('/patient/delete/<int:patient_id>')
@login_required
@admin_required
def delete_patient(patient_id):
    """Delete/blacklist patient"""
    db = get_db()
    try:
        patient = db.execute('SELECT user_id FROM patients WHERE patient_id = ?', (patient_id,)).fetchone()

        db.execute('UPDATE users SET status = ? WHERE user_id = ?', ('blacklisted', patient['user_id']))
        db.execute('UPDATE patients SET status = ? WHERE patient_id = ?', ('blacklisted', patient_id))

        db.commit()
        flash('Patient has been blacklisted', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('admin.patients'))


@admin_bp.route('/appointments')
@login_required
@admin_required
def appointments():
    """View all appointments"""
    db = get_db()

    appointments_list = db.execute('''
        SELECT a.*, 
               u1.name as patient_name, p.contact as patient_contact,
               u2.name as doctor_name, doc.specialization,
               dept.name as dept_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN users u1 ON p.user_id = u1.user_id
        JOIN doctors doc ON a.doctor_id = doc.doctor_id
        JOIN users u2 ON doc.user_id = u2.user_id
        JOIN departments d ON doc.dept_id = d.dept_id
        LEFT JOIN departments dept ON doc.dept_id = dept.dept_id
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    ''').fetchall()

    return render_template('admin/appointments.html', appointments=appointments_list)


@admin_bp.route('/appointment/update/<int:appointment_id>', methods=['POST'])
@login_required
@admin_required
def update_appointment(appointment_id):
    """Update appointment status"""
    db = get_db()
    status = request.form.get('status')

    try:
        db.execute('''
            UPDATE appointments SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE appointment_id = ?
        ''', (status, appointment_id))
        db.commit()
        flash('Appointment status updated!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('admin.appointments'))