"""
Patient Blueprint - Dashboard, Appointments, Booking, Profile
blueprints/patient.py
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from database import get_db
from datetime import datetime, timedelta

patient_bp = Blueprint('patient', __name__)


def patient_required(f):
    """Require patient role"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'patient':
            flash('Access denied. Patient privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


@patient_bp.route('/dashboard')
@login_required
@patient_required
def dashboard():
    """Patient dashboard"""
    db = get_db()

    patient = db.execute(
        'SELECT patient_id FROM patients WHERE user_id = ?',
        (current_user.user_id,)
    ).fetchone()

    if not patient:
        flash('Patient profile not found', 'danger')
        return redirect(url_for('auth.logout'))

    patient_id = patient['patient_id']

    # Departments list
    departments = db.execute(
        'SELECT * FROM departments ORDER BY name'
    ).fetchall()

    # Upcoming appointments
    today = datetime.now().strftime('%Y-%m-%d')
    upcoming_appointments = db.execute('''
        SELECT a.*, 
               u.name AS doctor_name, 
               doc.specialization, 
               dept.name AS dept_name
        FROM appointments a
        JOIN doctors doc ON a.doctor_id = doc.doctor_id
        JOIN users u ON doc.user_id = u.user_id
        LEFT JOIN departments dept ON doc.dept_id = dept.dept_id
        WHERE a.patient_id = ? 
          AND a.appointment_date >= ? 
          AND a.status != 'Cancelled'
        ORDER BY a.appointment_date, a.appointment_time
        LIMIT 5
    ''', (patient_id, today)).fetchall()

    # Stats
    total_appointments = db.execute(
        'SELECT COUNT(*) AS count FROM appointments WHERE patient_id = ?',
        (patient_id,)
    ).fetchone()['count']

    completed_appointments = db.execute('''
        SELECT COUNT(*) AS count 
        FROM appointments 
        WHERE patient_id = ? AND status = 'Completed'
    ''', (patient_id,)).fetchone()['count']

    return render_template(
        'patient/dashboard.html',
        departments=departments,
        upcoming_appointments=upcoming_appointments,
        total_appointments=total_appointments,
        completed_appointments=completed_appointments
    )


@patient_bp.route('/doctors')
@login_required
@patient_required
def doctors():
    """List all doctors with availability"""
    db = get_db()

    dept_id = request.args.get('dept_id', type=int)

    today = datetime.now().strftime('%Y-%m-%d')
    week_later = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

    if dept_id:
        doctors_list = db.execute('''
            SELECT d.*, u.name, u.email, dept.name AS dept_name,
                   COUNT(DISTINCT da.date) AS available_days
            FROM doctors d
            JOIN users u ON d.user_id = u.user_id
            LEFT JOIN departments dept ON d.dept_id = dept.dept_id
            LEFT JOIN doctor_availability da 
                ON d.doctor_id = da.doctor_id
               AND da.date BETWEEN ? AND ? 
               AND da.is_available = 1
            WHERE d.status = 'active' AND d.dept_id = ?
            GROUP BY d.doctor_id
            ORDER BY u.name
        ''', (today, week_later, dept_id)).fetchall()
    else:
        doctors_list = db.execute('''
            SELECT d.*, u.name, u.email, dept.name AS dept_name,
                   COUNT(DISTINCT da.date) AS available_days
            FROM doctors d
            JOIN users u ON d.user_id = u.user_id
            LEFT JOIN departments dept ON d.dept_id = dept.dept_id
            LEFT JOIN doctor_availability da 
                ON d.doctor_id = da.doctor_id
               AND da.date BETWEEN ? AND ? 
               AND da.is_available = 1
            WHERE d.status = 'active'
            GROUP BY d.doctor_id
            ORDER BY u.name
        ''', (today, week_later)).fetchall()

    departments = db.execute(
        'SELECT * FROM departments ORDER BY name'
    ).fetchall()

    return render_template(
        'patient/doctors.html',
        doctors=doctors_list,
        departments=departments,
        selected_dept=dept_id
    )


@patient_bp.route('/doctor/<int:doctor_id>/availability')
@login_required
@patient_required
def doctor_availability(doctor_id):
    """Show doctor availability"""
    db = get_db()

    doctor = db.execute('''
        SELECT d.*, u.name, u.email, dept.name AS dept_name
        FROM doctors d
        JOIN users u ON d.user_id = u.user_id
        LEFT JOIN departments dept ON d.dept_id = dept.dept_id
        WHERE d.doctor_id = ?
    ''', (doctor_id,)).fetchone()

    availabilities = []
    for i in range(7):
        date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
        slots = db.execute('''
            SELECT *
            FROM doctor_availability
            WHERE doctor_id = ? AND date = ? AND is_available = 1
            ORDER BY start_time
        ''', (doctor_id, date)).fetchall()

        if slots:
            availabilities.append({
                'date': date,
                'day_name': datetime.strptime(date, '%Y-%m-%d').strftime('%A'),
                'slots': slots
            })

    return render_template(
        'patient/doctor_availability.html',
        doctor=doctor,
        availabilities=availabilities
    )


@patient_bp.route('/appointment/book', methods=['GET', 'POST'])
@login_required
@patient_required
def book_appointment():
    """Book an appointment"""
    db = get_db()

    patient = db.execute(
        'SELECT patient_id FROM patients WHERE user_id = ?',
        (current_user.user_id,)
    ).fetchone()
    patient_id = patient['patient_id']

    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        reason = request.form.get('reason')

        if not all([doctor_id, appointment_date, appointment_time]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('patient.book_appointment'))

        if appointment_date < datetime.now().strftime('%Y-%m-%d'):
            flash('Cannot book past appointments.', 'danger')
            return redirect(url_for('patient.book_appointment'))

        # Double-booking check
        existing = db.execute('''
            SELECT *
            FROM appointments
            WHERE doctor_id = ?
              AND appointment_date = ?
              AND appointment_time = ?
              AND status NOT IN ('Cancelled', 'Rescheduled')
        ''', (doctor_id, appointment_date, appointment_time)).fetchone()

        if existing:
            flash('Time slot already booked.', 'danger')
            return redirect(url_for('patient.book_appointment'))

        # Check doctor availability
        available = db.execute('''
            SELECT *
            FROM doctor_availability
            WHERE doctor_id = ?
              AND date = ?
              AND is_available = 1
              AND time(?) BETWEEN time(start_time) AND time(end_time)
        ''', (doctor_id, appointment_date, appointment_time)).fetchone()

        if not available:
            flash('Doctor is not available at this time.', 'danger')
            return redirect(url_for('patient.book_appointment'))

        try:
            db.execute('''
                INSERT INTO appointments 
                    (patient_id, doctor_id, appointment_date, appointment_time, status, reason)
                VALUES (?, ?, ?, ?, 'Booked', ?)
            ''', (patient_id, doctor_id, appointment_date, appointment_time, reason))

            db.commit()
            flash('Appointment booked!', 'success')
            return redirect(url_for('patient.appointments'))

        except Exception as e:
            db.rollback()
            flash(f'Error: {e}', 'danger')

    doctors = db.execute('''
        SELECT d.*, u.name, dept.name AS dept_name
        FROM doctors d
        JOIN users u ON d.user_id = u.user_id
        LEFT JOIN departments dept ON d.dept_id = dept.dept_id
        WHERE d.status = 'active'
        ORDER BY u.name
    ''').fetchall()

    departments = db.execute(
        'SELECT * FROM departments ORDER BY name'
    ).fetchall()

    return render_template(
        'patient/book_appointment.html',
        doctors=doctors,
        departments=departments
    )


@patient_bp.route('/appointments')
@login_required
@patient_required
def appointments():
    """View all patient appointments"""
    db = get_db()

    patient = db.execute(
        'SELECT patient_id FROM patients WHERE user_id = ?',
        (current_user.user_id,)
    ).fetchone()
    patient_id = patient['patient_id']

    all_appointments = db.execute('''
        SELECT a.*, 
               u.name AS doctor_name, 
               doc.specialization, 
               dept.name AS dept_name, 
               doc.contact
        FROM appointments a
        JOIN doctors doc ON a.doctor_id = doc.doctor_id
        JOIN users u ON doc.user_id = u.user_id
        LEFT JOIN departments dept ON doc.dept_id = dept.dept_id
        WHERE a.patient_id = ?
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    ''', (patient_id,)).fetchall()

    return render_template(
        'patient/appointments.html',
        appointments=all_appointments
    )


@patient_bp.route('/appointment/cancel/<int:appointment_id>')
@login_required
@patient_required
def cancel_appointment(appointment_id):
    """Cancel appointment"""
    db = get_db()

    patient = db.execute(
        'SELECT patient_id FROM patients WHERE user_id = ?',
        (current_user.user_id,)
    ).fetchone()

    try:
        appointment = db.execute('''
            SELECT * 
            FROM appointments 
            WHERE appointment_id = ? AND patient_id = ?
        ''', (appointment_id, patient['patient_id'])).fetchone()

        if not appointment:
            flash('Appointment not found.', 'danger')
            return redirect(url_for('patient.appointments'))

        if appointment['appointment_date'] < datetime.now().strftime('%Y-%m-%d'):
            flash('Cannot cancel past appointments.', 'danger')
            return redirect(url_for('patient.appointments'))

        db.execute('''
            UPDATE appointments 
            SET status = 'Cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE appointment_id = ?
        ''', (appointment_id,))

        db.commit()
        flash('Appointment cancelled.', 'success')

    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'danger')

    return redirect(url_for('patient.appointments'))


@patient_bp.route('/history')
@login_required
@patient_required
def history():
    """Appointment history with treatments"""
    db = get_db()

    patient = db.execute(
        'SELECT patient_id FROM patients WHERE user_id = ?',
        (current_user.user_id,)
    ).fetchone()
    patient_id = patient['patient_id']

    history_records = db.execute('''
        SELECT a.*, 
               u.name AS doctor_name, 
               doc.specialization, 
               dept.name AS dept_name,
               t.diagnosis, 
               t.prescription, 
               t.notes, 
               t.follow_up_date
        FROM appointments a
        JOIN doctors doc ON a.doctor_id = doc.doctor_id
        JOIN users u ON doc.user_id = u.user_id
        LEFT JOIN departments dept ON doc.dept_id = dept.dept_id
        LEFT JOIN treatments t ON a.appointment_id = t.appointment_id
        WHERE a.patient_id = ? 
          AND a.status = 'Completed'
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    ''', (patient_id,)).fetchall()

    return render_template(
        'patient/history.html',
        history=history_records
    )


@patient_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
@patient_required
def edit_profile():
    """Edit profile"""
    db = get_db()

    patient = db.execute('''
        SELECT p.*, u.name, u.email
        FROM patients p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.user_id = ?
    ''', (current_user.user_id,)).fetchone()

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        age = request.form.get('age')
        gender = request.form.get('gender')
        contact = request.form.get('contact')
        address = request.form.get('address')
        blood_group = request.form.get('blood_group')
        emergency_contact = request.form.get('emergency_contact')

        try:
            db.execute('''
                UPDATE users 
                SET name = ?, email = ? 
                WHERE user_id = ?
            ''', (name, email, current_user.user_id))

            db.execute('''
                UPDATE patients 
                SET age = ?, gender = ?, contact = ?, address = ?, 
                    blood_group = ?, emergency_contact = ?
                WHERE user_id = ?
            ''', (age, gender, contact, address, blood_group, emergency_contact, current_user.user_id))

            db.commit()
            flash('Profile updated.', 'success')
            return redirect(url_for('patient.dashboard'))

        except Exception as e:
            db.rollback()
            flash(f'Error: {e}', 'danger')

    return render_template(
        'patient/edit_profile.html',
        patient=patient
    )
