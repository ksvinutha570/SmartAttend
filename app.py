from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "smartattend_secret_key"

DATABASE = "smartattend.db"


# Database connection
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Create database tables
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            usn TEXT,
            semester TEXT,
            section TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_name TEXT NOT NULL,
            subject_code TEXT UNIQUE NOT NULL,
            faculty_id INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(student_id, subject_id, date)
        )
    """)

    # Create default administrator if not present
    admin = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        ("admin@smartattend.com",)
    ).fetchone()

    if not admin:
        conn.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
        """, (
            "Administrator",
            "admin@smartattend.com",
            generate_password_hash("Admin@123"),
            "admin"
        ))

    conn.commit()
    conn.close()


# Login required decorator
def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


# Role required decorator
def role_required(role):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))

            if session.get("role") != role:
                flash("You are not authorized to access this page.", "error")
                return redirect(url_for("dashboard"))

            return function(*args, **kwargs)
        return wrapper
    return decorator


# Home page
@app.route("/")
def home():
    return render_template("index.html")


# Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        role = request.form["role"]
        usn = request.form.get("usn", "").strip()
        semester = request.form.get("semester", "").strip()
        section = request.form.get("section", "").strip()

        if not name or not email or not password:
            flash("Please fill all required fields.", "error")
            return redirect(url_for("register"))

        if role not in ["student", "faculty"]:
            flash("Invalid registration role.", "error")
            return redirect(url_for("register"))

        if role == "student" and not usn:
            flash("USN is required for students.", "error")
            return redirect(url_for("register"))

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO users
                (name, email, password, role, usn, semester, section)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                email,
                generate_password_hash(password),
                role,
                usn,
                semester,
                section
            ))

            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Email already registered.", "error")
            return redirect(url_for("register"))

        finally:
            conn.close()

    return render_template("register.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# Dashboard based on role
@app.route("/dashboard")
@login_required
def dashboard():
    role = session.get("role")

    if role == "admin":
        return redirect(url_for("admin"))

    if role == "faculty":
        return redirect(url_for("faculty"))

    if role == "student":
        return redirect(url_for("student"))

    session.clear()
    return redirect(url_for("login"))


# Admin dashboard
@app.route("/admin")
@login_required
@role_required("admin")
def admin():
    conn = get_db()

    students = conn.execute(
        "SELECT * FROM users WHERE role = 'student'"
    ).fetchall()

    faculty = conn.execute(
        "SELECT * FROM users WHERE role = 'faculty'"
    ).fetchall()

    subjects = conn.execute(
        "SELECT * FROM subjects"
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        students=students,
        faculty=faculty,
        subjects=subjects
    )


# Add subject
@app.route("/add_subject", methods=["POST"])
@login_required
@role_required("admin")
def add_subject():
    subject_name = request.form["subject_name"].strip()
    subject_code = request.form["subject_code"].strip()
    faculty_id = request.form.get("faculty_id")

    if not subject_name or not subject_code:
        flash("Enter subject name and code.", "error")
        return redirect(url_for("admin"))

    conn = get_db()

    try:
        conn.execute("""
            INSERT INTO subjects (subject_name, subject_code, faculty_id)
            VALUES (?, ?, ?)
        """, (
            subject_name,
            subject_code,
            int(faculty_id) if faculty_id else None
        ))
        conn.commit()
        flash("Subject added successfully.", "success")

    except sqlite3.IntegrityError:
        flash("Subject code already exists.", "error")

    finally:
        conn.close()

    return redirect(url_for("admin"))


# Faculty dashboard
@app.route("/faculty")
@login_required
@role_required("faculty")
def faculty():
    conn = get_db()

    subjects = conn.execute("""
        SELECT * FROM subjects
        WHERE faculty_id = ?
    """, (session["user_id"],)).fetchall()

    students = conn.execute("""
        SELECT * FROM users
        WHERE role = 'student'
    """).fetchall()

    conn.close()

    return render_template(
        "faculty.html",
        subjects=subjects,
        students=students
    )


# Mark attendance page
@app.route("/attendance/<int:subject_id>", methods=["GET", "POST"])
@login_required
@role_required("faculty")
def attendance(subject_id):
    conn = get_db()

    subject = conn.execute("""
        SELECT * FROM subjects
        WHERE id = ? AND faculty_id = ?
    """, (subject_id, session["user_id"])).fetchone()

    if not subject:
        conn.close()
        flash("Subject not found or not assigned to you.", "error")
        return redirect(url_for("faculty"))

    students = conn.execute("""
        SELECT * FROM users
        WHERE role = 'student'
        ORDER BY name
    """).fetchall()

    if request.method == "POST":
        attendance_date = request.form["date"]

        for student in students:
            status = request.form.get(f"status_{student['id']}")

            if status in ["Present", "Absent"]:
                conn.execute("""
                    INSERT INTO attendance
                    (student_id, subject_id, date, status)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(student_id, subject_id, date)
                    DO UPDATE SET status = excluded.status
                """, (
                    student["id"],
                    subject_id,
                    attendance_date,
                    status
                ))

        conn.commit()
        flash("Attendance saved successfully.", "success")

    conn.close()

    return render_template(
        "attendance.html",
        subject=subject,
        students=students
    )


# Student dashboard
@app.route("/student")
@login_required
@role_required("student")
def student():
    conn = get_db()

    records = conn.execute("""
        SELECT
            subjects.subject_name,
            subjects.subject_code,
            COUNT(attendance.id) AS total_classes,
            SUM(CASE WHEN attendance.status = 'Present' THEN 1 ELSE 0 END)
            AS present_classes
        FROM subjects
        LEFT JOIN attendance
        ON subjects.id = attendance.subject_id
        AND attendance.student_id = ?
        GROUP BY subjects.id
    """, (session["user_id"],)).fetchall()

    conn.close()

    report = []

    for record in records:
        total = record["total_classes"]
        present = record["present_classes"] or 0

        percentage = (present / total * 100) if total else 0

        report.append({
            "subject_name": record["subject_name"],
            "subject_code": record["subject_code"],
            "total_classes": total,
            "present_classes": present,
            "percentage": round(percentage, 2)
        })

    return render_template("student.html", records=report)


# Attendance history
@app.route("/attendance_history")
@login_required
@role_required("student")
def attendance_history():
    conn = get_db()

    records = conn.execute("""
        SELECT
            subjects.subject_name,
            attendance.date,
            attendance.status
        FROM attendance
        JOIN subjects ON subjects.id = attendance.subject_id
        WHERE attendance.student_id = ?
        ORDER BY attendance.date DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "attendance.html",
        subject=None,
        students=[],
        records=records
    )


# Logout
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))


# Initialize database
init_db()


if __name__ == "__main__":
    app.run(debug=True)