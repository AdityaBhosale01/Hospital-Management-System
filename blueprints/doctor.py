"""
Doctor Blueprint - Dashboard, Appointments, Treatment, Availability
blueprints/doctor.py
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from database import get_db
from datetime import datetime, timedelta

doctor_bp = Blueprint('doctor', __name__)


def doctor_required(f):
    """Decorator to require doctor role"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'doctor':
            flash('Access denied. Doctor privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


@doctor_bp.route('/dashboard')
@login_required
@doctor_required
def dashboard():
    """Doctor dashboard"""
    db = get_db()

    # Get doctor ID
    doctor = db.execute('SELECT doctor_id FROM doctors WHERE user_id = ?',
                        (current_user.user_id,)).fetchone()

    if not doctor:
        flash('Doctor profile not found', 'danger')
        return redirect(url_for('auth.logout'))

    doctor_id = doctor['doctor_id']

    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    week_later = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

    # Upcoming appointments (today and next 7 days)
    upcoming_appointments = db.execute('''
        SELECT a.*, u.name as patient_name, p.contact, p.age, p.gender
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN users u ON p.user_id = u.user_id
        WHERE a.doctor_id = ? AND a.appointment_date >= ? AND a.appointment_date <= ?
        AND a.status != 'Cancelled'
        ORDER BY a.appointment_date, a.appointment_time
    ''', (doctor_id, today, week_later)).fetchall()

    # Today's appointments
    today_appointments = db.execute('''
        SELECT a.*, u.name as patient_name, p.contact, p.age, p.gender
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN users u ON p.user_id = u.user_id
        WHERE a.doctor_id = ? AND a.appointment_date = ?
        AND a.status != 'Cancelled'
        ORDER BY a.appointment_time
    ''', (doctor_id, today)).fetchall()

    # Assigned patients (unique patients with appointments)
    assigned_patients = db.execute('''
        SELECT DISTINCT p.patient_id, u.name, p.age, p.gender, p.contact, p.blood_group,
               COUNT(a.appointment_id) as total_appointments
        FROM patients p
        JOIN users u ON p.user_id = u.user_id
        JOIN appointments a ON p.patient_id = a.patient_id
        WHERE a.doctor_id = ?
        GROUP BY p.patient_id
        ORDER BY u.name
    ''', (doctor_id,)).fetchall()

    # Statistics
    total_appointments = db.execute('''
        SELECT COUNT(*) as count FROM appointments WHERE doctor_id = ?
    ''', (doctor_id,)).fetchone()['count']

    completed_appointments = db.execute('''
        SELECT COUNT(*) as count FROM appointments 
        WHERE doctor_id = ? AND status = 'Completed'
    ''', (doctor_id,)).fetchone()['count']

    pending_appointments = db.execute('''
        SELECT COUNT(*) as count FROM appointments 
        WHERE doctor_id = ? AND status = 'Booked' AND appointment_date >= ?
    ''', (doctor_id, today)).fetchone()['count']

    return render_template('doctor/dashboard.html',
                           upcoming_appointments=upcoming_appointments,
                           today_appointments=today_appointments,
                           assigned_patients=assigned_patients,
                           total_appointments=total_appointments,
                           completed_appointments=completed_appointments,
                           pending_appointments=pending_appointments)


@doctor_bp.route('/appointments')
@login_required
@doctor_required
def appointments():
    """View all appointments"""
    db = get_db()

    doctor = db.execute('SELECT doctor_id FROM doctors WHERE user_id = ?',
                        (current_user.user_id,)).fetchone()
    doctor_id = doctor['doctor_id']

    # Get all appointments
    all_appointments = db.execute('''
        SELECT a.*, u.name as patient_name, p.contact, p.age, p.gender, p.blood_group
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN users u ON p.user_id = u.user_id
        WHERE a.doctor_id = ?
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    ''', (doctor_id,)).fetchall()

    return render_template('doctor/appointments.html', appointments=all_appointments)


@doctor_bp.route('/appointment/update/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
@doctor_required
def update_appointment(appointment_id):
    """Update appointment status and add treatment"""
    db = get_db()

    if request.method == 'POST':
        status = request.form.get('status')
        diagnosis = request.form.get('diagnosis')
        prescription = request.form.get('prescription')
        notes = request.form.get('notes')
        follow_up_date = request.form.get('follow_up_date')

        try:
            # Update appointment status
            db.execute('''
                UPDATE appointments SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE appointment_id = ?
            ''', (status, appointment_id))

            # Check if treatment record exists
            existing_treatment = db.execute('''
                SELECT treatment_id FROM treatments WHERE appointment_id = ?
            ''', (appointment_id,)).fetchone()

            if existing_treatment:
                # Update existing treatment
                db.execute('''
                    UPDATE treatments 
                    SET diagnosis = ?, prescription = ?, notes = ?, 
                        follow_up_date = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE appointment_id = ?
                ''', (diagnosis, prescription, notes, follow_up_date, appointment_id))
            else:
                # Insert new treatment record
                db.execute('''
                    INSERT INTO treatments (appointment_id, diagnosis, prescription, notes, follow_up_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (appointment_id, diagnosis, prescription, notes, follow_up_date))

            db.commit()
            flash('Appointment and treatment updated successfully!', 'success')
            return redirect(url_for('doctor.appointments'))

        except Exception as e:
            db.rollback()
            flash(f'Error: {str(e)}', 'danger')

    # Get appointment details
    appointment = db.execute('''
        SELECT a.*, u.name as patient_name, p.age, p.gender, p.contact, 
               p.blood_group, p.address
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN users u ON p.user_id = u.user_id
        WHERE a.appointment_id = ?
    ''', (appointment_id,)).fetchone()

    # Get existing treatment if any
    treatment = db.execute('''
        SELECT * FROM treatments WHERE appointment_id = ?
    ''', (appointment_id,)).fetchone()

    return render_template('doctor/update_treatment.html',
                           appointment=appointment,
                           treatment=treatment)


@doctor_bp.route('/availability', methods=['GET', 'POST'])
@login_required
@doctor_required
def availability():
    """Manage doctor availability"""
    db = get_db()

    doctor = db.execute('SELECT doctor_id FROM doctors WHERE user_id = ?',
                        (current_user.user_id,)).fetchone()
    doctor_id = doctor['doctor_id']

    if request.method == 'POST':
        # Get form data
        dates = request.form.getlist('date[]')
        start_times = request.form.getlist('start_time[]')
        end_times = request.form.getlist('end_time[]')
        availabilities = request.form.getlist('is_available[]')

        try:
            for i in range(len(dates)):
                date = dates[i]
                start_time = start_times[i]
                end_time = end_times[i]
                is_available = 1 if str(i) in availabilities else 0

                # Check if exists
                existing = db.execute('''
                    SELECT availability_id FROM doctor_availability
                    WHERE doctor_id = ? AND date = ? AND start_time = ?
                ''', (doctor_id, date, start_time)).fetchone()

                if existing:
                    # Update
                    db.execute('''
                        UPDATE doctor_availability
                        SET end_time = ?, is_available = ?
                        WHERE availability_id = ?
                    ''', (end_time, is_available, existing['availability_id']))
                else:
                    # Insert
                    db.execute('''
                        INSERT INTO doctor_availability (doctor_id, date, start_time, end_time, is_available)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (doctor_id, date, start_time, end_time, is_available))

            db.commit()
            flash('Availability updated successfully!', 'success')
            return redirect(url_for('doctor.availability'))

        except Exception as e:
            db.rollback()
            flash(f'Error: {str(e)}', 'danger')

    # Get next 7 days availability
    availabilities = []
    for i in range(7):
        date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
        day_availability = db.execute('''
            SELECT * FROM doctor_availability
            WHERE doctor_id = ? AND date = ?
            ORDER BY start_time
        ''', (doctor_id, date)).fetchall()

        availabilities.append({
            'date': date,
            'slots': day_availability
        })

    return render_template('doctor/availability.html', availabilities=availabilities)


@doctor_bp.route('/patient/<int:patient_id>/history')
@login_required
@doctor_required
def patient_history(patient_id):
    """View complete treatment history of a patient"""
    db = get_db()

    doctor = db.execute('SELECT doctor_id FROM doctors WHERE user_id = ?',
                        (current_user.user_id,)).fetchone()
    doctor_id = doctor['doctor_id']

    # Get patient details
    patient = db.execute('''
        SELECT p.*, u.name, u.email
        FROM patients p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.patient_id = ?
    ''', (patient_id,)).fetchone()

    # Get all appointments and treatments for this patient with this doctor
    history = db.execute('''
        SELECT a.*, t.diagnosis, t.prescription, t.notes, t.follow_up_date
        FROM appointments a
        LEFT JOIN treatments t ON a.appointment_id = t.appointment_id
        WHERE a.patient_id = ? AND a.doctor_id = ?
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    ''', (patient_id, doctor_id)).fetchall()

    return render_template('doctor/patient_history.html',
                           patient=patient,
                           history=history)