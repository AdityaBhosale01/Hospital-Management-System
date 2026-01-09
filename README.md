<<<<<<< HEAD
# Hospital Management System

A Flask-based web application that manages hospital operations such as patient registration, doctor management, appointments, and authentication.  
This project uses a modular blueprint structure to separate Admin, Doctor, Patient, and Auth functionalities.

---

## 🚀 Features

### **Admin**
- Add, edit, and remove doctors  
- View all patients  
- Manage appointments  
- Monitor hospital activity  

### **Doctor**
- View assigned patients  
- Update diagnosis, prescription, and reports  
- Check appointment schedule  

### **Patient**
- Register and log in  
- Book appointments  
- View medical history  
- Access prescriptions  

### **Authentication**
- Secure login system  
- Role-based access (Admin, Doctor, Patient)

---

## 🛠️ Tech Stack

- **Python** (Flask)
- **HTML, CSS, Bootstrap**
- **SQLite / SQLAlchemy**
- **Blueprint Architecture**

---

## 📂 Project Structure

Hospital-Management-System/
│── app.py
│── database.py
│── models.py
│── requirements.txt
│── README.md
│
├── blueprints/
│ ├── auth.py
│ ├── admin.py
│ ├── doctor.py
│ ├── patient.py
│ └── init.py
│
├── templates/
│ ├── base.html
│ ├── auth_login.html
│ ├── admin_dashboard.html
│ ├── doctor_dashboard.html
│ └── patient_dashboard.html
│
└── static/
├── css/
├── js/
└── images/

---

## ⚙️ Installation and Setup

### **1. Clone the repository**
git clone https://github.com/<your-username>/<your-repo>.git
cd Hospital-Management-System

### **2. Create a virtual environment**
python -m venv venv

### **3. Activate the environment**

Windows:
venv\Scripts\activate

### **4. Install dependencies**
pip install -r requirements.txt

### **5. Run the project**
python app.py

### **6. Open in browser**
http://127.0.0.1:5000/
---

## 🗄️ Database

- The app uses **SQLite** by default.
- A new `.db` file is created automatically if not present.
- You can modify DB models inside `models.py`.

---

## 🧪 Testing

You can use tools like:
- Postman (for API testing)
- Flask test client
- Browser testing for UI

---

## 🔮 Future Enhancements

- Add email/SMS notifications  
- Doctor schedule automation  
- Appointment reminders  
- API endpoints for mobile integration  
- Role-based dashboards with charts  

---

## 👨‍💻 Author
**Aditya**  
BTech CSE — Hospital Management System Project  
Feel free to reach out for improvements or collaboration.

---
=======
# Hospital-Management-System
>>>>>>> 58e0d73e593825739c1e235529d456f27d754f60
