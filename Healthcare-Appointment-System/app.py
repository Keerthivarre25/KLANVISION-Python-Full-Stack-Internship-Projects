from flask import Flask, request, redirect, render_template_string, flash, session, url_for
import sqlite3, os
from functools import wraps
from markupsafe import escape, Markup
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-demo-secret")
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data.db")

def query(sql, args=(), one=False):
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        cur = c.execute(sql, args)
        if sql.lstrip().upper().startswith("SELECT"):
            return cur.fetchone() if one else cur.fetchall()
        c.commit()
        return cur.lastrowid

HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>
body{font-family:system-ui;background:#f4f7fb;color:#15253a;margin:0}
header{background:#163e75;color:white;padding:24px}
nav a{color:white;margin-right:18px}
main{max-width:1050px;margin:28px auto;padding:0 18px}
.card{background:white;border-radius:12px;padding:22px;margin:16px 0;box-shadow:0 3px 14px #0001}
input,select{padding:10px;margin:6px 5px 6px 0;border:1px solid #bbc6d3;border-radius:6px;max-width:100%}
button{background:#1769aa;color:white;border:0;padding:11px 16px;border-radius:6px;cursor:pointer}
table{border-collapse:collapse;width:100%;background:white}
td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}
th{background:#e7eef7}.alert{background:#fff0c8;padding:12px;margin:8px 0}
.scroll{overflow-x:auto}.muted{color:#526477}
</style></head><body><header><h1>{{ title }}</h1><nav>{{ nav|safe }}</nav></header>
<main>{% with msgs=get_flashed_messages() %}{% for m in msgs %}<div class="alert">{{m}}</div>{% endfor %}{% endwith %}{{ body|safe }}</main></body></html>"""

def current_user():
    uid = session.get("user_id")
    return query("SELECT * FROM users WHERE id=?", (uid,), True) if uid else None

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.")
                return redirect(url_for("login"))
            if user["role"] not in roles:
                flash("You do not have permission to access that page.")
                return redirect(url_for("home"))
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def nav_links():
    user = current_user()
    if not user:
        return '<a href="/login">Login</a>'
    links = ['<a href="/">Dashboard</a>']
    if user["role"] == "admin":
        links += ['<a href="/patients">Patients</a>', '<a href="/doctors">Doctors</a>', '<a href="/appointments">Appointments</a>']
    elif user["role"] == "doctor":
        links += ['<a href="/appointments">My Appointments</a>']
    else:
        links += ['<a href="/doctors">Find Doctors</a>', '<a href="/appointments">My Appointments</a>']
    links.append('<a href="/logout">Logout</a>')
    return " ".join(links)

def page(title, body):
    return render_template_string(
        HTML,
        title=title,
        body=Markup(str(body)),
        nav=Markup(nav_links())
    )

def table(rows):
    if not rows:
        return "<p>No records found.</p>"
    heads = rows[0].keys()
    out = '<div class="scroll"><table><tr>' + "".join(f"<th>{escape(str(h))}</th>" for h in heads) + "</tr>"
    for row in rows:
        out += "<tr>" + "".join(f"<td>{escape(str(row[h] if row[h] is not None else ''))}</td>" for h in heads) + "</tr>"
    return out + "</table></div>"

def field(name, typ="text", required=True):
    return f'<input name="{name}" type="{typ}" placeholder="{name.replace("_"," ").title()}" {"required" if required else ""}>'

def form(fields, action, button="Save"):
    return '<form method="post" action="' + action + '">' + "".join(field(*x) if isinstance(x, tuple) else field(x) for x in fields) + f'<button>{button}</button></form>'

def init():
    with sqlite3.connect(DB) as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,phone TEXT,age INTEGER,gender TEXT);
        CREATE TABLE IF NOT EXISTS doctors(id INTEGER PRIMARY KEY,name TEXT NOT NULL,specialization TEXT,experience INTEGER,contact TEXT);
        CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY,patient_id INTEGER NOT NULL,doctor_id INTEGER NOT NULL,slot TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Scheduled',FOREIGN KEY(patient_id) REFERENCES patients(id),FOREIGN KEY(doctor_id) REFERENCES doctors(id));
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,linked_id INTEGER);
        """)
        # Demo accounts are linked to the first existing patient/doctor records.
        demo_patient = c.execute("SELECT id FROM patients WHERE email=?", ("demo.patient@example.com",)).fetchone()
        if not demo_patient:
            c.execute("INSERT INTO patients(name,email,phone,age,gender) VALUES(?,?,?,?,?)",
                      ("Demo Patient", "demo.patient@example.com", "9000000001", 25, "Other"))
            demo_patient = c.execute("SELECT id FROM patients WHERE email=?", ("demo.patient@example.com",)).fetchone()
        if not c.execute("SELECT 1 FROM doctors LIMIT 1").fetchone():
            c.execute("INSERT INTO doctors(name,specialization,experience,contact) VALUES(?,?,?,?)",
                      ("Dr. Demo", "General Physician", 5, "9000000002"))
        patient_id = demo_patient[0]
        doctor_id = c.execute("SELECT id FROM doctors ORDER BY id LIMIT 1").fetchone()[0]
        accounts = [
            ("admin", "Admin@123", "admin", None),
            ("doctor", "Doctor@123", "doctor", doctor_id),
            ("patient", "Patient@123", "patient", patient_id),
        ]
        for username, password, role, linked_id in accounts:
            if not c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                c.execute("INSERT INTO users(username,password_hash,role,linked_id) VALUES(?,?,?,?)",
                          (username, generate_password_hash(password), role, linked_id))
        c.commit()

init()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE username=?", (username,), True)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Login successful.")
            return redirect(url_for("home"))
        flash("Invalid username or password.")
    body = """<div class="card"><h2>Sign in</h2>
    <form method="post"><input name="username" placeholder="Username" required>
    <input name="password" type="password" placeholder="Password" required>
    <button type="submit">Login</button></form>
    <p class="muted">Demo accounts: admin / Admin@123, doctor / Doctor@123, patient / Patient@123</p></div>"""
    return page("Healthcare Login", body)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))

@app.route("/")
@role_required("admin", "doctor", "patient")
def home():
    user = current_user()
    role = user["role"]
    if role == "admin":
        body = f'<div class="card"><h2>Admin Dashboard</h2><p>Patients: {query("SELECT COUNT(*) AS n FROM patients", one=True)["n"]} | Doctors: {query("SELECT COUNT(*) AS n FROM doctors", one=True)["n"]} | Appointments: {query("SELECT COUNT(*) AS n FROM appointments", one=True)["n"]}</p><p>Manage patient records, doctors and all appointments.</p></div>'
    elif role == "doctor":
        body = '<div class="card"><h2>Doctor Dashboard</h2><p>View appointments assigned to your doctor account and update their status.</p></div>'
    else:
        body = '<div class="card"><h2>Patient Dashboard</h2><p>Search doctors, book appointments and view or cancel your own appointments.</p></div>'
    return page(role.title() + " Dashboard", body)

@app.route("/patients", methods=["GET", "POST"])
@role_required("admin")
def patients():
    if request.method == "POST":
        f = request.form
        try:
            age = int(f["age"])
            if not 0 < age < 125:
                raise ValueError
            query("INSERT INTO patients(name,email,phone,age,gender) VALUES(?,?,?,?,?)",
                  (f["name"].strip(), f["email"].strip(), f.get("phone",""), age, f.get("gender","")))
            flash("Patient registered.")
        except (sqlite3.IntegrityError, ValueError, KeyError):
            flash("Invalid data or duplicate email.")
        return redirect(url_for("patients"))
    body = '<div class="card"><h2>Register Patient</h2>' + form(["name", ("email","email"), ("phone","tel"), ("age","number"), "gender"], "/patients") + "</div>"
    return page("Patient Management", body + table(query("SELECT * FROM patients ORDER BY id DESC")))

@app.route("/doctors", methods=["GET", "POST"])
@role_required("admin", "patient")
def doctors():
    if request.method == "POST":
        if current_user()["role"] != "admin":
            flash("Only admin can add doctors.")
            return redirect(url_for("doctors"))
        f = request.form
        try:
            exp = int(f["experience"])
            if exp < 0: raise ValueError
            query("INSERT INTO doctors(name,specialization,experience,contact) VALUES(?,?,?,?)",
                  (f["name"].strip(), f["specialization"].strip(), exp, f["contact"].strip()))
            flash("Doctor added.")
        except (ValueError, KeyError):
            flash("Please enter valid doctor details.")
        return redirect(url_for("doctors"))
    s = request.args.get("q", "")
    rows = query("SELECT id,name,specialization,experience,contact FROM doctors WHERE name LIKE ? OR specialization LIKE ? ORDER BY id DESC",
                 (f"%{s}%", f"%{s}%"))
    body = ""
    if current_user()["role"] == "admin":
        body += '<div class="card"><h2>Add Doctor</h2>' + form(["name","specialization",("experience","number"),"contact"], "/doctors") + "</div>"
    body += '<div class="card"><h2>Search Doctors</h2><form method="get"><input name="q" placeholder="Search name or specialization" value="' + str(escape(s)) + '"><button>Search</button></form></div>'
    return page("Doctor Management", body + table(rows))

@app.route("/appointments", methods=["GET", "POST"])
@role_required("admin", "doctor", "patient")
def appointments():
    user = current_user()
    role = user["role"]
    if request.method == "POST":
        if role != "patient":
            flash("Only patients can book appointments.")
            return redirect(url_for("appointments"))
        try:
            did = int(request.form["doctor_id"])
            slot = request.form["slot"]
            if not slot or not query("SELECT id FROM doctors WHERE id=?", (did,), True):
                raise ValueError
            pid = user["linked_id"]
            conflict = query("SELECT id FROM appointments WHERE doctor_id=? AND slot=? AND status IN ('Scheduled','Rescheduled')", (did, slot), True)
            if conflict:
                raise ValueError
            query("INSERT INTO appointments(patient_id,doctor_id,slot) VALUES(?,?,?)", (pid, did, slot))
            flash("Appointment booked.")
        except (ValueError, KeyError, TypeError):
            flash("Invalid doctor or time slot already booked.")
        return redirect(url_for("appointments"))

    if role == "admin":
        rows = query("SELECT a.id,p.name AS patient,d.name AS doctor,a.slot,a.status FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN doctors d ON d.id=a.doctor_id ORDER BY a.slot DESC")
        body = '<div class="card"><h2>All Appointments</h2><p>Admin can update any appointment status.</p>' + table(rows) + """
        <h3>Update appointment status</h3><form method="post" action="/status">
        <input name="id" type="number" placeholder="Appointment ID" required>
        <select name="status"><option>Scheduled</option><option>Completed</option><option>Cancelled</option><option>Rescheduled</option></select>
        <input name="slot" type="datetime-local" title="New slot when rescheduling"><button>Update</button></form></div>"""
    elif role == "doctor":
        rows = query("SELECT a.id,p.name AS patient,d.name AS doctor,a.slot,a.status FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN doctors d ON d.id=a.doctor_id WHERE a.doctor_id=? ORDER BY a.slot DESC", (user["linked_id"],))
        body = '<div class="card"><h2>My Assigned Appointments</h2>' + table(rows) + """
        <h3>Update appointment status</h3><form method="post" action="/status">
        <input name="id" type="number" placeholder="Appointment ID" required>
        <select name="status"><option>Completed</option><option>Cancelled</option><option>Rescheduled</option></select>
        <input name="slot" type="datetime-local" title="New slot when rescheduling"><button>Update</button></form></div>"""
    else:
        rows = query("SELECT a.id,d.name AS doctor,d.specialization,a.slot,a.status FROM appointments a JOIN doctors d ON d.id=a.doctor_id WHERE a.patient_id=? ORDER BY a.slot DESC", (user["linked_id"],))
        docs = query("SELECT id,name,specialization FROM doctors ORDER BY name")
        options = "".join(f'<option value="{d["id"]}">{escape(d["name"])} — {escape(d["specialization"] or "")}</option>' for d in docs)
        body = '<div class="card"><h2>Book Appointment</h2><form method="post"><select name="doctor_id" required><option value="">Choose doctor</option>' + options + '</select><input name="slot" type="datetime-local" required><button>Book</button></form></div>'
        body += '<div class="card"><h2>My Appointments</h2>' + table(rows) + """
        <h3>Cancel an appointment</h3><form method="post" action="/cancel">
        <input name="id" type="number" placeholder="Appointment ID" required><button>Cancel</button></form></div>"""
    return page("Appointments", body)

@app.post("/status")
@role_required("admin", "doctor")
def status():
    user = current_user()
    try:
        aid = int(request.form["id"])
        new_status = request.form["status"]
        old = query("SELECT * FROM appointments WHERE id=?", (aid,), True)
        if not old or new_status not in ("Scheduled", "Completed", "Cancelled", "Rescheduled"):
            raise ValueError
        if user["role"] == "doctor" and old["doctor_id"] != user["linked_id"]:
            flash("You can only update appointments assigned to you.")
            return redirect(url_for("appointments"))
        slot = request.form.get("slot") or old["slot"]
        if new_status in ("Scheduled", "Rescheduled"):
            conflict = query("SELECT id FROM appointments WHERE doctor_id=? AND slot=? AND id<>? AND status IN ('Scheduled','Rescheduled')",
                             (old["doctor_id"], slot, aid), True)
            if conflict: raise ValueError
        query("UPDATE appointments SET status=?,slot=? WHERE id=?", (new_status, slot, aid))
        flash("Appointment status updated.")
    except (ValueError, KeyError):
        flash("Invalid update or conflicting time slot.")
    return redirect(url_for("appointments"))

@app.post("/cancel")
@role_required("patient")
def cancel():
    try:
        aid = int(request.form["id"])
        owned = query("SELECT id FROM appointments WHERE id=? AND patient_id=? AND status IN ('Scheduled','Rescheduled')",
                      (aid, current_user()["linked_id"]), True)
        if owned:
            query("UPDATE appointments SET status='Cancelled' WHERE id=?", (aid,))
            flash("Appointment cancelled.")
        else:
            flash("Appointment not found or cannot be cancelled.")
    except (ValueError, KeyError):
        flash("Invalid appointment ID.")
    return redirect(url_for("appointments"))

if __name__ == "__main__":
    app.run(debug=True)
