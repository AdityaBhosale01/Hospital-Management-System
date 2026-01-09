"""
Database initialization and management
Creates all tables and seed data programmatically
"""

import sqlite3
from flask import g
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

DATABASE = 'hospital.db'


def get_db():
    """Get database connection"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


def init_db():
    """Initialize database with all tables and seed data"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'doctor', 'patient')),
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'blacklisted')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Departments Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Doctors Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            specialization TEXT NOT NULL,
            dept_id INTEGER,
            contact TEXT,
            qualification TEXT,
            experience INTEGER,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'blacklisted')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
        )
    ''')

    # Doctor Availability Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctor_availability (
            availability_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            is_available BOOLEAN DEFAULT 1,
            FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE,
            UNIQUE(doctor_id, date, start_time)
        )
    ''')

    # Patients Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            age INTEGER,
            gender TEXT CHECK(gender IN ('Male', 'Female', 'Other')),
            contact TEXT,
            address TEXT,
            blood_group TEXT,
            emergency_contact TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'blacklisted')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    ''')

    # Appointments Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            status TEXT DEFAULT 'Booked' CHECK(status IN ('Booked', 'Completed', 'Cancelled', 'Rescheduled')),
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
            FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE
        )
    ''')

    # Treatment Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS treatments (
            treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER UNIQUE NOT NULL,
            diagnosis TEXT,
            prescription TEXT,
            notes TEXT,
            follow_up_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id) ON DELETE CASCADE
        )
    ''')

    conn.commit()

    # Seed initial data
    seed_data(conn)

    conn.close()


def seed_data(conn):
    """Insert initial seed data"""
    cursor = conn.cursor()

    # Check if admin exists
    cursor.execute("SELECT * FROM users WHERE email = ?", ('admin@hospital.com',))
    if not cursor.fetchone():
        # Create admin user
        admin_password = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (name, email, password, role, status)
            VALUES (?, ?, ?, ?, ?)
        ''', ('System Admin', 'admin@hospital.com', admin_password, 'admin', 'active'))

        # Create departments
        departments = [
            ('Cardiology', 'Heart and cardiovascular system'),
            ('Neurology', 'Brain and nervous system'),
            ('Orthopedics', 'Bones and joints'),
            ('Pediatrics', 'Children healthcare'),
            ('Dermatology', 'Skin conditions'),
            ('General Medicine', 'General health issues'),
            ('ENT', 'Ear, Nose, and Throat'),
            ('Ophthalmology', 'Eye care')
        ]

        cursor.executemany('''
            INSERT INTO departments (name, description) VALUES (?, ?)
        ''', departments)

        # Create sample doctors
        doctor_data = [
            ('Dr. John Smith', 'john.smith@hospital.com', 'Cardiology', '9876543210', 'MD Cardiology', 15),
            ('Dr. Sarah Johnson', 'sarah.j@hospital.com', 'Neurology', '9876543211', 'MD Neurology', 12),
            ('Dr. Michael Brown', 'michael.b@hospital.com', 'Orthopedics', '9876543212', 'MS Orthopedics', 10),
            ('Dr. Emily Davis', 'emily.d@hospital.com', 'Pediatrics', '9876543213', 'MD Pediatrics', 8),
        ]

        for name, email, spec, contact, qual, exp in doctor_data:
            password = generate_password_hash('doctor123')
            cursor.execute('''
                INSERT INTO users (name, email, password, role, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, email, password, 'doctor', 'active'))

            user_id = cursor.lastrowid

            # Get department ID
            cursor.execute('SELECT dept_id FROM departments WHERE name = ?', (spec,))
            dept = cursor.fetchone()
            dept_id = dept[0] if dept else None

            cursor.execute('''
                INSERT INTO doctors (user_id, specialization, dept_id, contact, qualification, experience, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, spec, dept_id, contact, qual, exp, 'active'))

            doctor_id = cursor.lastrowid

            # Add availability for next 7 days
            for i in range(7):
                date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
                time_slots = [
                    ('09:00', '12:00'),
                    ('14:00', '17:00')
                ]
                for start, end in time_slots:
                    cursor.execute('''
                        INSERT INTO doctor_availability (doctor_id, date, start_time, end_time, is_available)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (doctor_id, date, start, end, 1))

        conn.commit()
        print("Seed data created successfully!")
        print("Admin credentials: admin@hospital.com / admin123")
        print("Doctor credentials: john.smith@hospital.com / doctor123")