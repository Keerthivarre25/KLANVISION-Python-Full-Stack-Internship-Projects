from flask import (
    Flask, request, redirect, render_template_string, flash, send_from_directory,
    session, url_for
)
import sqlite3
import os
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from markupsafe import escape, Markup

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-demo-secret-key")
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data.db")
UPLOAD = os.path.join(BASE, "uploads")
os.makedirs(UPLOAD, exist_ok=True)
MAX_RESUME_SIZE = 2 * 1024 * 1024

# Demo admin credentials. Change these before any public deployment.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")

HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>
body{font-family:system-ui;background:#f4f7fb;color:#15253a;margin:0}
header{background:#163e75;color:white;padding:24px}
nav a{color:white;margin-right:18px}
main{max-width:1100px;margin:28px auto;padding:0 18px}
.card{background:white;border-radius:12px;padding:22px;margin:16px 0;box-shadow:0 3px 14px #0001}
input,select,textarea{padding:10px;margin:6px 5px 6px 0;border:1px solid #bbc6d3;border-radius:6px;max-width:100%}
button,.button{background:#1769aa;color:white;border:0;padding:10px 15px;border-radius:6px;cursor:pointer;text-decoration:none;display:inline-block}
button.danger,.button.danger{background:#a83232}
table{border-collapse:collapse;width:100%;background:white}
td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}
th{background:#e7eef7}.alert{background:#fff0c8;padding:12px;border-radius:6px;margin:10px 0}
.scroll{overflow-x:auto}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}
.stat{background:#eaf1fa;border-radius:10px;padding:18px}.stat strong{font-size:26px;display:block}
.inline{display:inline-block;margin:2px}
</style></head><body>
<header><h1>{{ title }}</h1><nav>{{ nav|safe }}</nav></header>
<main>{% with msgs=get_flashed_messages() %}{% for m in msgs %}
<div class="alert">{{ m }}</div>{% endfor %}{% endwith %}{{ body|safe }}</main>
</body></html>"""


def query(sql, args=(), one=False):
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, args)
        if sql.lstrip().upper().startswith("SELECT"):
            return cur.fetchone() if one else cur.fetchall()
        conn.commit()
        return cur.lastrowid


def init():
    with sqlite3.connect(DB) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS candidates(
            id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, phone TEXT,
            skills TEXT, education TEXT, experience TEXT
        );
        CREATE TABLE IF NOT EXISTS companies(
            id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE,
            location TEXT, industry TEXT
        );
        CREATE TABLE IF NOT EXISTS jobs(
            id INTEGER PRIMARY KEY, company_id INTEGER, title TEXT,
            description TEXT, skills TEXT, salary TEXT, location TEXT,
            status TEXT DEFAULT 'Open'
        );
        CREATE TABLE IF NOT EXISTS applications(
            id INTEGER PRIMARY KEY, candidate_id INTEGER, job_id INTEGER,
            resume TEXT, status TEXT DEFAULT 'Applied',
            UNIQUE(candidate_id, job_id)
        );
        """)
        conn.commit()


init()


def is_admin():
    return session.get("role") == "admin"


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin():
            flash("Please log in as Admin to access that operation.")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def nav_links():
    links = [
        ("/", "Dashboard"), ("/candidates", "Candidates"),
        ("/companies", "Companies"), ("/jobs", "Jobs"),
        ("/applications", "Applications")
    ]
    if is_admin():
        links += [("/admin", "Admin Panel"), ("/admin/logout", "Logout")]
    else:
        links += [("/admin/login", "Admin Login")]
    return " ".join(
        f'<a href="{path}">{label}</a>' for path, label in links
    )


def page(title, body):
    return render_template_string(
        HTML, title=title, body=Markup(str(body)), nav=Markup(nav_links())
    )


def table(rows):
    if not rows:
        return "<p>No records found.</p>"
    heads = rows[0].keys()
    html = '<div class="scroll"><table><tr>'
    for heading in heads:
        html += f"<th>{escape(str(heading))}</th>"
    html += "</tr>"
    for row in rows:
        html += "<tr>"
        for heading in heads:
            value = row[heading] if row[heading] is not None else ""
            html += f"<td>{escape(str(value))}</td>"
        html += "</tr>"
    html += "</table></div>"
    return html


def field(name, typ="text", required=True):
    safe_name = escape(name)
    placeholder = escape(name.replace("_", " ").title())
    req = "required" if required else ""
    return f'<input name="{safe_name}" type="{typ}" placeholder="{placeholder}" {req}>'


def form(fields, action, button="Save", extra=""):
    inputs = "".join(
        field(*item) if isinstance(item, tuple) else field(item)
        for item in fields
    )
    return (
        f'<form method="post" action="{action}" enctype="multipart/form-data">'
        + inputs + extra + f"<button>{button}</button></form>"
    )


@app.route("/")
def home():
    counts = {
        "Candidates": query("SELECT COUNT(*) AS n FROM candidates", one=True)["n"],
        "Companies": query("SELECT COUNT(*) AS n FROM companies", one=True)["n"],
        "Open Jobs": query("SELECT COUNT(*) AS n FROM jobs WHERE status='Open'", one=True)["n"],
        "Applications": query("SELECT COUNT(*) AS n FROM applications", one=True)["n"],
    }
    stats = '<div class="stats">' + "".join(
        f'<div class="stat"><strong>{value}</strong>{label}</div>'
        for label, value in counts.items()
    ) + "</div>"
    intro = (
        '<div class="card"><h2>Job Portal & Recruitment Manager</h2>'
        '<p>Register candidates and companies, publish and search jobs, '
        'submit PDF resumes and track applications.</p>'
        '<p>Administrative actions require Admin login.</p></div>'
    )
    return page("Job Portal Dashboard", intro + stats)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        # Compare against a hash generated at runtime; do not store a plain password in the DB.
        if username == ADMIN_USERNAME and check_password_hash(
            generate_password_hash(ADMIN_PASSWORD), password
        ):
            session.clear()
            session["role"] = "admin"
            session["username"] = username
            flash("Admin login successful.")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin username or password.")
    body = (
        '<div class="card"><h2>Admin Login</h2>'
        '<form method="post"><input name="username" placeholder="Username" required>'
        '<input name="password" type="password" placeholder="Password" required>'
        '<button type="submit">Login</button></form></div>'
    )
    return page("Admin Login", body)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    metrics = [
        ("Candidates", "SELECT COUNT(*) AS n FROM candidates"),
        ("Companies", "SELECT COUNT(*) AS n FROM companies"),
        ("Jobs", "SELECT COUNT(*) AS n FROM jobs"),
        ("Applications", "SELECT COUNT(*) AS n FROM applications"),
        ("Shortlisted", "SELECT COUNT(*) AS n FROM applications WHERE status='Shortlisted'"),
        ("Rejected", "SELECT COUNT(*) AS n FROM applications WHERE status='Rejected'"),
    ]
    cards = '<div class="stats">'
    for label, sql in metrics:
        value = query(sql, one=True)["n"]
        cards += f'<div class="stat"><strong>{value}</strong>{label}</div>'
    cards += "</div>"
    links = (
        '<div class="card"><h2>Administration</h2>'
        '<p><a href="/admin/candidates">Manage candidates</a></p>'
        '<p><a href="/admin/companies">Manage companies</a></p>'
        '<p><a href="/admin/jobs">Manage jobs</a></p>'
        '<p><a href="/admin/applications">Manage applications</a></p></div>'
    )
    return page("Admin Dashboard", cards + links)


@app.route("/candidates", methods=["GET", "POST"])
def candidates():
    if request.method == "POST":
        f = request.form
        try:
            query(
                "INSERT INTO candidates(name,email,phone,skills,education,experience) "
                "VALUES(?,?,?,?,?,?)",
                tuple(f[k] for k in ("name", "email", "phone", "skills", "education", "experience"))
            )
            flash("Candidate registered.")
        except sqlite3.IntegrityError:
            flash("That candidate email is already registered.")
        return redirect(url_for("candidates"))
    body = (
        '<div class="card"><h2>Register Candidate</h2>'
        + form(["name", ("email", "email"), "phone", "skills", "education", "experience"], "/candidates")
        + "</div>" + table(query("SELECT * FROM candidates ORDER BY id DESC"))
    )
    return page("Candidates", body)


@app.route("/companies", methods=["GET", "POST"])
def companies():
    if request.method == "POST":
        f = request.form
        try:
            query(
                "INSERT INTO companies(name,email,location,industry) VALUES(?,?,?,?)",
                tuple(f[k] for k in ("name", "email", "location", "industry"))
            )
            flash("Company added.")
        except sqlite3.IntegrityError:
            flash("That company email is already registered.")
        return redirect(url_for("companies"))
    body = (
        '<div class="card"><h2>Register Company</h2>'
        + form(["name", ("email", "email"), "location", "industry"], "/companies")
        + "</div>" + table(query("SELECT * FROM companies ORDER BY id DESC"))
    )
    return page("Companies", body)


@app.route("/jobs", methods=["GET", "POST"])
def jobs():
    if request.method == "POST":
        if not is_admin():
            flash("Only Admin can post jobs. Please log in.")
            return redirect(url_for("admin_login"))
        f = request.form
        try:
            company_id = int(f["company_id"])
            if not query("SELECT id FROM companies WHERE id=?", (company_id,), one=True):
                raise ValueError
            query(
                "INSERT INTO jobs(company_id,title,description,skills,salary,location) "
                "VALUES(?,?,?,?,?,?)",
                (company_id, *[f[k] for k in ("title", "description", "skills", "salary", "location")])
            )
            flash("Job posted.")
        except (ValueError, KeyError):
            flash("Invalid company ID or missing job details.")
        return redirect(url_for("jobs"))

    search = request.args.get("q", "")
    rows = query(
        """SELECT j.id,c.name AS company,j.title,j.description,j.skills,
        j.salary,j.location,j.status FROM jobs j
        JOIN companies c ON j.company_id=c.id
        WHERE j.title LIKE ? OR j.skills LIKE ? OR c.name LIKE ? OR j.location LIKE ?
        ORDER BY j.id DESC""",
        (f"%{search}%",) * 4
    )
    body = (
        '<div class="card"><h2>Search Jobs</h2><form method="get">'
        '<input name="q" placeholder="Search title, skills, company, location">'
        '<button>Search</button></form></div>'
    )
    if is_admin():
        body += (
            '<div class="card"><h2>Post Job (Admin)</h2>'
            '<p>Use a company ID from the Companies section.</p>'
            + form([("company_id", "number"), "title", "description", "skills", "salary", "location"], "/jobs")
            + "</div>"
        )
    body += table(rows)
    return page("Job Listings", body)


@app.route("/applications", methods=["GET", "POST"])
def applications():
    if request.method == "POST":
        try:
            candidate_id = int(request.form["candidate_id"])
            job_id = int(request.form["job_id"])
            uploaded = request.files.get("resume")
            if not uploaded or not uploaded.filename.lower().endswith(".pdf"):
                raise ValueError
            if not query("SELECT id FROM candidates WHERE id=?", (candidate_id,), one=True):
                raise ValueError
            if not query("SELECT id FROM jobs WHERE id=? AND status='Open'", (job_id,), one=True):
                raise ValueError
            if query(
                "SELECT id FROM applications WHERE candidate_id=? AND job_id=?",
                (candidate_id, job_id), one=True
            ):
                raise ValueError
            uploaded.seek(0, os.SEEK_END)
            size = uploaded.tell()
            uploaded.seek(0)
            if size > MAX_RESUME_SIZE or uploaded.read(4) != b"%PDF":
                raise ValueError
            uploaded.seek(0)
            filename = f"{candidate_id}_{job_id}_{secure_filename(uploaded.filename)}"
            uploaded.save(os.path.join(UPLOAD, filename))
            query(
                "INSERT INTO applications(candidate_id,job_id,resume) VALUES(?,?,?)",
                (candidate_id, job_id, filename)
            )
            flash("Application submitted.")
        except (ValueError, KeyError, sqlite3.IntegrityError):
            flash("Invalid application, duplicate application, or resume is not a PDF under 2 MB.")
        return redirect(url_for("applications"))

    rows = query(
        """SELECT a.id,c.name AS candidate,j.title AS job,a.resume,a.status
        FROM applications a JOIN candidates c ON c.id=a.candidate_id
        JOIN jobs j ON j.id=a.job_id ORDER BY a.id DESC"""
    )
    body = (
        '<div class="card"><h2>Apply for Job</h2>'
        '<p>Enter your candidate ID and an open job ID. Resume must be PDF (max 2 MB).</p>'
        + form([("candidate_id", "number"), ("job_id", "number"), ("resume", "file")], "/applications", "Apply")
        + "</div>"
    )
    if is_admin():
        body += (
            '<div class="card"><h2>Update Application Status</h2>'
            '<form method="post" action="/application-status">'
            '<input name="id" type="number" placeholder="Application ID" required>'
            '<select name="status">'
            + "".join(f"<option>{status}</option>" for status in
                      ["Applied", "Shortlisted", "Interview", "Selected", "Rejected"])
            + '</select><button>Update</button></form></div>'
        )
    body += table(rows)
    return page("Applications", body)


@app.post("/application-status")
@admin_required
def application_status():
    try:
        application_id = int(request.form["id"])
        status = request.form["status"]
        if status not in ("Applied", "Shortlisted", "Interview", "Selected", "Rejected"):
            raise ValueError
        query("UPDATE applications SET status=? WHERE id=?", (status, application_id))
        flash("Application status updated.")
    except (ValueError, KeyError):
        flash("Invalid application status update.")
    return redirect(url_for("applications"))


@app.route("/admin/candidates", methods=["GET", "POST"])
@admin_required
def admin_candidates():
    if request.method == "POST":
        try:
            candidate_id = int(request.form["id"])
            action = request.form["action"]
            if action == "delete":
                query("DELETE FROM applications WHERE candidate_id=?", (candidate_id,))
                query("DELETE FROM candidates WHERE id=?", (candidate_id,))
                flash("Candidate and related applications deleted.")
            elif action == "update":
                query(
                    "UPDATE candidates SET name=?,email=?,phone=?,skills=?,education=?,experience=? WHERE id=?",
                    tuple(request.form[k] for k in ("name", "email", "phone", "skills", "education", "experience"))
                    + (candidate_id,)
                )
                flash("Candidate updated.")
        except (ValueError, KeyError, sqlite3.IntegrityError):
            flash("Unable to update candidate. Check the ID and email.")
        return redirect(url_for("admin_candidates"))
    rows = query("SELECT * FROM candidates ORDER BY id DESC")
    body = '<div class="card"><h2>Candidate Records</h2>' + table(rows) + "</div>"
    body += (
        '<div class="card"><h2>Update Candidate</h2><form method="post">'
        '<input name="id" type="number" placeholder="Candidate ID" required>'
        + "".join(field(k) for k in ("name", "email", "phone", "skills", "education", "experience"))
        + '<input type="hidden" name="action" value="update"><button>Save Changes</button></form>'
        '<h2>Delete Candidate</h2><form method="post">'
        '<input name="id" type="number" placeholder="Candidate ID" required>'
        '<input type="hidden" name="action" value="delete">'
        '<button class="danger">Delete Candidate</button></form></div>'
    )
    return page("Admin – Manage Candidates", body)


@app.route("/admin/companies", methods=["GET", "POST"])
@admin_required
def admin_companies():
    if request.method == "POST":
        try:
            company_id = int(request.form["id"])
            action = request.form["action"]
            if action == "delete":
                linked = query("SELECT id FROM jobs WHERE company_id=?", (company_id,))
                for job in linked:
                    query("DELETE FROM applications WHERE job_id=?", (job["id"],))
                query("DELETE FROM jobs WHERE company_id=?", (company_id,))
                query("DELETE FROM companies WHERE id=?", (company_id,))
                flash("Company and its jobs/applications deleted.")
            elif action == "update":
                query(
                    "UPDATE companies SET name=?,email=?,location=?,industry=? WHERE id=?",
                    tuple(request.form[k] for k in ("name", "email", "location", "industry"))
                    + (company_id,)
                )
                flash("Company updated.")
        except (ValueError, KeyError, sqlite3.IntegrityError):
            flash("Unable to update company. Check the ID and email.")
        return redirect(url_for("admin_companies"))
    body = '<div class="card"><h2>Company Records</h2>' + table(query("SELECT * FROM companies ORDER BY id DESC")) + "</div>"
    body += (
        '<div class="card"><h2>Update Company</h2><form method="post">'
        '<input name="id" type="number" placeholder="Company ID" required>'
        + "".join(field(k) for k in ("name", "email", "location", "industry"))
        + '<input type="hidden" name="action" value="update"><button>Save Changes</button></form>'
        '<h2>Delete Company</h2><form method="post">'
        '<input name="id" type="number" placeholder="Company ID" required>'
        '<input type="hidden" name="action" value="delete">'
        '<button class="danger">Delete Company</button></form></div>'
    )
    return page("Admin – Manage Companies", body)


@app.route("/admin/jobs", methods=["GET", "POST"])
@admin_required
def admin_jobs():
    if request.method == "POST":
        try:
            job_id = int(request.form["id"])
            action = request.form["action"]
            if action == "delete":
                query("DELETE FROM applications WHERE job_id=?", (job_id,))
                query("DELETE FROM jobs WHERE id=?", (job_id,))
                flash("Job and related applications deleted.")
            elif action == "update":
                status = request.form["status"]
                if status not in ("Open", "Closed"):
                    raise ValueError
                query(
                    "UPDATE jobs SET title=?,description=?,skills=?,salary=?,location=?,status=? WHERE id=?",
                    tuple(request.form[k] for k in ("title", "description", "skills", "salary", "location"))
                    + (status, job_id)
                )
                flash("Job updated.")
        except (ValueError, KeyError):
            flash("Unable to update job. Check the ID and status.")
        return redirect(url_for("admin_jobs"))
    rows = query(
        """SELECT j.id,c.name AS company,j.title,j.description,j.skills,j.salary,
        j.location,j.status FROM jobs j JOIN companies c ON c.id=j.company_id
        ORDER BY j.id DESC"""
    )
    body = '<div class="card"><h2>Job Records</h2>' + table(rows) + "</div>"
    body += (
        '<div class="card"><h2>Update Job</h2><form method="post">'
        '<input name="id" type="number" placeholder="Job ID" required>'
        + "".join(field(k) for k in ("title", "description", "skills", "salary", "location"))
        + '<select name="status"><option>Open</option><option>Closed</option></select>'
        '<input type="hidden" name="action" value="update"><button>Save Changes</button></form>'
        '<h2>Delete Job</h2><form method="post">'
        '<input name="id" type="number" placeholder="Job ID" required>'
        '<input type="hidden" name="action" value="delete">'
        '<button class="danger">Delete Job</button></form></div>'
    )
    return page("Admin – Manage Jobs", body)


@app.route("/admin/applications")
@admin_required
def admin_applications():
    rows = query(
        """SELECT a.id,c.name AS candidate,c.email,j.title AS job,
        co.name AS company,a.resume,a.status FROM applications a
        JOIN candidates c ON c.id=a.candidate_id
        JOIN jobs j ON j.id=a.job_id
        JOIN companies co ON co.id=j.company_id ORDER BY a.id DESC"""
    )
    body = '<div class="card"><h2>All Applications</h2>' + table(rows) + "</div>"
    body += '<p><a href="/applications">Go to application status controls</a></p>'
    return page("Admin – Manage Applications", body)


@app.route("/uploads/<path:filename>")
@admin_required
def download_resume(filename):
    return send_from_directory(UPLOAD, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
