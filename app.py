import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database.db"
UPLOAD_FOLDER = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_RECEIPT_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "doc", "docx", "xls", "xlsx"}
PRE_CONSTRUCTION_STATUSES = (
    "Lead",
    "Estimating",
    "Proposal Sent",
    "Negotiation",
    "Approved",
    "Rejected",
)
EXECUTION_STATUSES = ("Scheduled", "Started", "In Progress", "Completed")
FINANCIAL_STATUSES = ("Invoiced", "Paid")
STATUSES = PRE_CONSTRUCTION_STATUSES + EXECUTION_STATUSES + FINANCIAL_STATUSES
APPROVED_PIPELINE_STATUSES = (
    "Approved",
    "Scheduled",
    "Started",
    "In Progress",
    "Completed",
    "Invoiced",
    "Paid",
)
PROPOSAL_PIPELINE_STATUSES = (
    "Proposal Sent",
    "Negotiation",
    "Approved",
    "Rejected",
    "Scheduled",
    "Started",
    "In Progress",
    "Completed",
    "Invoiced",
    "Paid",
)
PAYMENT_STATUSES = ("Not Paid", "Paid")
ROLES = ("admin", "employee", "client")
PUBLIC_ENDPOINTS = {"login", "static"}


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-this-secret")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    UPLOAD_FOLDER.mkdir(exist_ok=True)
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'employee', 'client')),
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Lead',
                client_name TEXT,
                proposal_amount REAL,
                proposal_sent_date TEXT,
                decision_date TEXT,
                rejection_reason TEXT,
                invoice_amount REAL,
                payment_status TEXT NOT NULL DEFAULT 'Not Paid',
                assigned_to INTEGER,
                client_id INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )
        migrate_jobs_table(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                notes TEXT,
                image_path TEXT,
                receipt_path TEXT,
                update_group TEXT,
                user_id INTEGER,
                author_role TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
            )
            """
        )
        migrate_updates_table(conn)
        seed_default_users(conn)


def seed_default_users(conn):
    now = datetime.now().isoformat(timespec="seconds")
    default_password = os.environ.get("ADMIN_PASSWORD", os.environ.get("WORKER_PASSWORD", "password123"))
    default_users = (
        ("Admin", os.environ.get("ADMIN_EMAIL", "admin@example.com"), default_password, "admin"),
        ("Employee", os.environ.get("EMPLOYEE_EMAIL", "employee@example.com"), os.environ.get("EMPLOYEE_PASSWORD", "employee123"), "employee"),
        ("Client", os.environ.get("CLIENT_EMAIL", "client@example.com"), os.environ.get("CLIENT_PASSWORD", "client123"), "client"),
    )

    for name, email, password, role in default_users:
        existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing_user is None:
            conn.execute(
                """
                INSERT INTO users (name, email, password, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, email, generate_password_hash(password), role, now),
            )

    legacy_username = os.environ.get("WORKER_USERNAME", "worker")
    legacy_worker = conn.execute(
        "SELECT id FROM workers WHERE username = ?",
        (legacy_username,),
    ).fetchone()
    if legacy_worker is None:
        conn.execute(
            """
            INSERT INTO workers (username, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (legacy_username, generate_password_hash(default_password), now),
        )


def migrate_jobs_table(conn):
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    new_columns = {
        "client_name": "TEXT",
        "proposal_amount": "REAL",
        "proposal_sent_date": "TEXT",
        "decision_date": "TEXT",
        "rejection_reason": "TEXT",
        "invoice_amount": "REAL",
        "payment_status": "TEXT NOT NULL DEFAULT 'Not Paid'",
        "assigned_to": "INTEGER",
        "client_id": "INTEGER",
    }

    for column, definition in new_columns.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")

    conn.execute(
        """
        UPDATE jobs
        SET payment_status = 'Paid'
        WHERE payment_status IS NULL AND status = 'Paid'
        """
    )
    conn.execute(
        """
        UPDATE jobs
        SET payment_status = 'Not Paid'
        WHERE payment_status IS NULL
        """
    )


def migrate_updates_table(conn):
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(updates)").fetchall()
    }
    if "update_group" not in existing_columns:
        conn.execute("ALTER TABLE updates ADD COLUMN update_group TEXT")
    if "receipt_path" not in existing_columns:
        conn.execute("ALTER TABLE updates ADD COLUMN receipt_path TEXT")
    if "user_id" not in existing_columns:
        conn.execute("ALTER TABLE updates ADD COLUMN user_id INTEGER")
    if "author_role" not in existing_columns:
        conn.execute("ALTER TABLE updates ADD COLUMN author_role TEXT")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_receipt_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_RECEIPT_EXTENSIONS


def parse_money(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        amount = float(value)
    except ValueError:
        return None
    return amount if amount >= 0 else None


def parse_date(value):
    value = (value or "").strip()
    return value or None


def money(value):
    return f"${value:,.2f}" if value is not None else "-"


def group_updates(update_rows):
    grouped = []
    group_lookup = {}

    for row in update_rows:
        group_key = row["update_group"] or f"{row['timestamp']}|{row['notes'] or ''}"
        if group_key not in group_lookup:
            group_lookup[group_key] = {
                "timestamp": row["timestamp"],
                "notes": row["notes"],
                "author_role": row["author_role"],
                "photos": [],
                "receipts": [],
            }
            grouped.append(group_lookup[group_key])

        if row["image_path"]:
            group_lookup[group_key]["photos"].append(row["image_path"])
        if row["receipt_path"]:
            group_lookup[group_key]["receipts"].append(row["receipt_path"])

    return grouped


def get_job_or_404(job_id):
    with get_db_connection() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        flash("Job not found.", "error")
        return None
    return job


def is_admin():
    return g.user is not None and g.user["role"] == "admin"


def is_employee():
    return g.user is not None and g.user["role"] == "employee"


def is_client():
    return g.user is not None and g.user["role"] == "client"


def can_view_financials():
    return is_admin()


def can_manage_receipts():
    return is_admin() or is_employee()


def can_manage_jobs():
    return is_admin()


def can_update_job(job):
    return is_admin() or (is_employee() and job["assigned_to"] == g.user["id"])


def can_view_job(job):
    if is_admin():
        return True
    if is_employee():
        return job["assigned_to"] == g.user["id"]
    if is_client():
        return job["client_id"] == g.user["id"]
    return False


def visible_jobs_where():
    if is_admin():
        return "", []
    if is_employee():
        return "jobs.assigned_to = ?", [g.user["id"]]
    if is_client():
        return "jobs.client_id = ?", [g.user["id"]]
    return "1 = 0", []


def visible_jobs_where_for_role(dashboard_role):
    if dashboard_role == "admin":
        return "", []
    if dashboard_role == "employee":
        # Admin preview shows the employee workspace across assigned jobs.
        if is_admin():
            return "jobs.assigned_to IS NOT NULL", []
        return "jobs.assigned_to = ?", [g.user["id"]]
    if dashboard_role == "client":
        # Admin preview shows the client workspace across linked jobs.
        if is_admin():
            return "jobs.client_id IS NOT NULL", []
        return "jobs.client_id = ?", [g.user["id"]]
    return "1 = 0", []


def dashboard_role_from_request():
    if not is_admin():
        return g.user["role"]

    requested_role = request.args.get("view_as", "admin").strip().lower()
    if requested_role not in ROLES:
        return "admin"
    return requested_role


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login", next=request.path))
            if g.user["role"] not in roles:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


@app.before_request
def ensure_database():
    init_db()
    user_id = session.get("user_id")
    g.user = None
    if user_id:
        with get_db_connection() as conn:
            g.user = conn.execute(
                "SELECT id, name, email, role FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()


@app.route("/login", methods=("GET", "POST"))
def login():
    if g.user is not None:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            ).fetchone()

        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email)

        session.clear()
        session["user_id"] = user["id"]
        flash("Signed in.", "success")
        return redirect(request.args.get("next") or url_for("index"))

    return render_template("login.html")


@app.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    quick_filter = request.args.get("quick", "").strip()
    sort = request.args.get("sort", "newest").strip()
    dashboard_role = dashboard_role_from_request()
    where_clauses = []
    params = []
    role_clause, role_params = visible_jobs_where_for_role(dashboard_role)
    if role_clause:
        where_clauses.append(role_clause)
        params.extend(role_params)

    if status_filter in STATUSES:
        where_clauses.append("jobs.status = ?")
        params.append(status_filter)

    quick_filters = {
        "leads": ("jobs.status = ?", ["Lead"]),
        "proposals": (
            "jobs.status IN (?, ?, ?)",
            ["Estimating", "Proposal Sent", "Negotiation"],
        ),
        "assigned_work": (
            "jobs.status IN (?, ?, ?, ?)",
            ["Scheduled", "Started", "In Progress", "Completed"],
        ),
        "in_progress": ("jobs.status = ?", ["In Progress"]),
        "completed": ("jobs.status = ?", ["Completed"]),
        "approved": (
            f"jobs.status IN ({', '.join(['?'] * len(APPROVED_PIPELINE_STATUSES))})",
            list(APPROVED_PIPELINE_STATUSES),
        ),
        "lost": ("jobs.status = ?", ["Rejected"]),
        "payment_pending": (
            "COALESCE(jobs.invoice_amount, 0) > 0 AND jobs.payment_status != ?",
            ["Paid"],
        ),
    }
    if quick_filter in quick_filters:
        clause, quick_params = quick_filters[quick_filter]
        where_clauses.append(clause)
        params.extend(quick_params)

    if search:
        where_clauses.append(
            "(jobs.name LIKE ? OR jobs.client_name LIKE ? OR jobs.location LIKE ? OR jobs.description LIKE ?)"
        )
        like_search = f"%{search}%"
        params.extend([like_search, like_search, like_search, like_search])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    order_by = {
        "oldest": "jobs.created_at ASC",
        "status": "jobs.status ASC, jobs.created_at DESC",
        "updated": "last_update DESC, jobs.created_at DESC",
        }.get(sort, "jobs.created_at DESC")

    with get_db_connection() as conn:
        jobs = conn.execute(
            f"""
            SELECT jobs.*,
                   employee.name AS assigned_employee,
                   client.name AS client_user_name,
                   COUNT(updates.id) AS update_count,
                   MAX(updates.timestamp) AS last_update
            FROM jobs
            LEFT JOIN updates ON updates.job_id = jobs.id
            LEFT JOIN users employee ON employee.id = jobs.assigned_to
            LEFT JOIN users client ON client.id = jobs.client_id
            {where_sql}
            GROUP BY jobs.id
            ORDER BY {order_by}
            """,
            params,
        ).fetchall()
        status_counts = {
            row["status"]: row["count"]
            for row in conn.execute(
                f"""
                SELECT status, COUNT(*) AS count
                FROM jobs
                {where_sql}
                GROUP BY status
                """,
                params,
            ).fetchall()
        }
        placeholders = ", ".join(["?"] * len(APPROVED_PIPELINE_STATUSES))
        proposal_placeholders = ", ".join(["?"] * len(PROPOSAL_PIPELINE_STATUSES))
        metrics_where = f"WHERE {role_clause}" if role_clause else ""
        metrics = conn.execute(
            f"""
            SELECT
                SUM(CASE WHEN status = 'Lead' THEN 1 ELSE 0 END) AS total_leads,
                SUM(CASE WHEN status IN ({proposal_placeholders}) OR proposal_sent_date IS NOT NULL THEN 1 ELSE 0 END) AS proposals_sent,
                SUM(CASE WHEN status IN ({placeholders}) THEN 1 ELSE 0 END) AS approved_jobs,
                SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) AS rejected_jobs,
                SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress_jobs,
                COALESCE(SUM(CASE WHEN status != 'Rejected' THEN proposal_amount ELSE 0 END), 0) AS revenue_pipeline,
                COALESCE(SUM(CASE WHEN payment_status = 'Paid' THEN invoice_amount ELSE 0 END), 0) AS collected_revenue
            FROM jobs
            {metrics_where}
            """,
            list(PROPOSAL_PIPELINE_STATUSES) + list(APPROVED_PIPELINE_STATUSES) + role_params,
        ).fetchone()

    proposals_sent = metrics["proposals_sent"] or 0
    approved_jobs = metrics["approved_jobs"] or 0
    conversion_rate = round((approved_jobs / proposals_sent) * 100, 1) if proposals_sent else 0
    can_view_financials_flag = dashboard_role == "admin"
    can_manage_jobs_flag = dashboard_role == "admin"
    return render_template(
        "index.html",
        jobs=jobs,
        statuses=STATUSES,
        pre_construction_statuses=PRE_CONSTRUCTION_STATUSES,
        execution_statuses=EXECUTION_STATUSES,
        financial_statuses=FINANCIAL_STATUSES,
        status_counts=status_counts,
        metrics=metrics,
        conversion_rate=conversion_rate,
        money=money,
        can_view_financials=can_view_financials_flag,
        can_manage_jobs=can_manage_jobs_flag,
        dashboard_role=dashboard_role,
        show_view_switcher=is_admin(),
        filters={"q": search, "status": status_filter, "quick": quick_filter, "sort": sort, "view_as": dashboard_role},
    )


@app.route("/add", methods=("GET", "POST"))
@login_required
@role_required("admin")
def add_job():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        client_name = request.form.get("client_name", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "Lead").strip()
        proposal_amount = parse_money(request.form.get("proposal_amount"))
        proposal_sent_date = parse_date(request.form.get("proposal_sent_date"))
        assigned_to = request.form.get("assigned_to", type=int)
        client_id = request.form.get("client_id", type=int)

        if status not in STATUSES:
            status = "Lead"

        with get_db_connection() as conn:
            employees = conn.execute(
                "SELECT id, name, email FROM users WHERE role = 'employee' ORDER BY name"
            ).fetchall()
            clients = conn.execute(
                "SELECT id, name, email FROM users WHERE role = 'client' ORDER BY name"
            ).fetchall()

        if not name or not client_name or not location or not description:
            flash("Please fill out the job, client, location, and description.", "error")
            return render_template(
                "add_job.html",
                name=name,
                client_name=client_name,
                location=location,
                description=description,
                status=status,
                proposal_amount=proposal_amount,
                proposal_sent_date=proposal_sent_date,
                statuses=STATUSES,
                employees=employees,
                clients=clients,
                assigned_to=assigned_to,
                client_id=client_id,
            )

        now = datetime.now().isoformat(timespec="seconds")
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    name, client_name, location, description, status,
                    proposal_amount, proposal_sent_date, payment_status,
                    assigned_to, client_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    client_name,
                    location,
                    description,
                    status,
                    proposal_amount,
                    proposal_sent_date,
                    "Not Paid",
                    assigned_to,
                    client_id,
                    now,
                ),
            )
        flash("CRM job created.", "success")
        return redirect(url_for("index"))

    with get_db_connection() as conn:
        employees = conn.execute(
            "SELECT id, name, email FROM users WHERE role = 'employee' ORDER BY name"
        ).fetchall()
        clients = conn.execute(
            "SELECT id, name, email FROM users WHERE role = 'client' ORDER BY name"
        ).fetchall()
    return render_template("add_job.html", statuses=STATUSES, employees=employees, clients=clients)


@app.route("/users", methods=("GET", "POST"))
@login_required
@role_required("admin")
def users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()

        if not name or not email or not password or role not in ROLES:
            flash("Please enter a name, email, password, and valid role.", "error")
            return redirect(url_for("users"))

        try:
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO users (name, email, password, role, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        email,
                        generate_password_hash(password),
                        role,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
        except sqlite3.IntegrityError:
            flash("A user with that email already exists.", "error")
            return redirect(url_for("users"))

        flash("User created.", "success")
        return redirect(url_for("users"))

    with get_db_connection() as conn:
        users_list = conn.execute(
            "SELECT id, name, email, role, created_at FROM users ORDER BY role, name"
        ).fetchall()
    return render_template("users.html", users=users_list, roles=ROLES)


@app.route("/update/<int:job_id>")
@login_required
def update_job(job_id):
    job = get_job_or_404(job_id)
    if job is None:
        return redirect(url_for("index"))
    if not can_view_job(job):
        flash("You do not have permission to view that job.", "error")
        return redirect(url_for("index"))

    with get_db_connection() as conn:
        update_rows = conn.execute(
            """
            SELECT * FROM updates
            WHERE job_id = ?
            ORDER BY timestamp DESC, id DESC
            """,
            (job_id,),
        ).fetchall()
        employees = conn.execute(
            "SELECT id, name, email FROM users WHERE role = 'employee' ORDER BY name"
        ).fetchall()
        clients = conn.execute(
            "SELECT id, name, email FROM users WHERE role = 'client' ORDER BY name"
        ).fetchall()
    updates = group_updates(update_rows)

    return render_template(
        "update_job.html",
        job=job,
        updates=updates,
        statuses=STATUSES,
        pre_construction_statuses=PRE_CONSTRUCTION_STATUSES,
        execution_statuses=EXECUTION_STATUSES,
        financial_statuses=FINANCIAL_STATUSES,
        payment_statuses=PAYMENT_STATUSES,
        money=money,
        can_edit_job=can_update_job(job),
        can_manage_jobs=can_manage_jobs(),
        can_view_financials=can_view_financials(),
        can_manage_receipts=can_manage_receipts(),
        employees=employees,
        clients=clients,
    )


@app.route("/progress/<int:job_id>")
@login_required
def job_progress(job_id):
    job = get_job_or_404(job_id)
    if job is None:
        return redirect(url_for("index"))
    if not can_view_job(job):
        flash("You do not have permission to view that job.", "error")
        return redirect(url_for("index"))

    with get_db_connection() as conn:
        update_rows = conn.execute(
            """
            SELECT * FROM updates
            WHERE job_id = ?
            ORDER BY timestamp DESC, id DESC
            """,
            (job_id,),
        ).fetchall()
        progress = conn.execute(
            """
            SELECT
                COUNT(DISTINCT COALESCE(update_group, timestamp || '|' || COALESCE(notes, ''))) AS update_count,
                SUM(CASE WHEN image_path IS NOT NULL THEN 1 ELSE 0 END) AS photo_count,
                MIN(timestamp) AS first_update,
                MAX(timestamp) AS last_update
            FROM updates
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
    updates = group_updates(update_rows)

    return render_template(
        "job_progress.html",
        job=job,
        updates=updates,
        progress=progress,
        can_view_financials=can_view_financials(),
        can_manage_receipts=can_manage_receipts(),
    )


@app.route("/submit_update", methods=("POST",))
@login_required
def submit_update():
    job_id = request.form.get("job_id", type=int)
    status_input = request.form.get("status", "").strip()
    notes = request.form.get("notes", "").strip()
    client_name = request.form.get("client_name", "").strip()
    proposal_amount = parse_money(request.form.get("proposal_amount"))
    proposal_sent_date = parse_date(request.form.get("proposal_sent_date"))
    decision_date = parse_date(request.form.get("decision_date"))
    rejection_reason = request.form.get("rejection_reason", "").strip()
    invoice_amount = parse_money(request.form.get("invoice_amount"))
    payment_status = request.form.get("payment_status", "Not Paid").strip()
    files = request.files.getlist("images")
    receipt_files = request.files.getlist("receipts")
    assigned_to = request.form.get("assigned_to", type=int)
    client_id = request.form.get("client_id", type=int)

    if not job_id:
        flash("Please choose a valid job.", "error")
        return redirect(url_for("index"))

    job = get_job_or_404(job_id)
    if job is None:
        return redirect(url_for("index"))
    if not can_update_job(job):
        flash("You do not have permission to update that job.", "error")
        return redirect(url_for("index"))

    if is_admin():
        status = status_input
        if status not in STATUSES:
            flash("Please choose a valid status.", "error")
            return redirect(url_for("update_job", job_id=job_id))
    else:
        status = job["status"]

    if payment_status not in PAYMENT_STATUSES:
        flash("Please choose a valid payment status.", "error")
        return redirect(url_for("update_job", job_id=job_id))

    if is_employee():
        client_name = job["client_name"] or ""
        proposal_amount = job["proposal_amount"]
        proposal_sent_date = job["proposal_sent_date"]
        decision_date = job["decision_date"]
        rejection_reason = job["rejection_reason"] or ""
        invoice_amount = job["invoice_amount"]
        payment_status = job["payment_status"] or "Not Paid"
        assigned_to = job["assigned_to"]
        client_id = job["client_id"]
    else:
        if not client_name:
            flash("Please enter a client name.", "error")
            return redirect(url_for("update_job", job_id=job_id))

    if status == "Rejected" and not rejection_reason:
        flash("Please add a rejection reason before marking a job rejected.", "error")
        return redirect(url_for("update_job", job_id=job_id))

    if payment_status == "Paid" and invoice_amount is None and job["invoice_amount"] is None:
        flash("Enter an invoice amount before marking the job paid.", "error")
        return redirect(url_for("update_job", job_id=job_id))

    today = datetime.now().date().isoformat()
    if status == "Proposal Sent" and proposal_sent_date is None:
        proposal_sent_date = today
    if status in ("Approved", "Rejected") and decision_date is None:
        decision_date = today
    if payment_status == "Paid":
        status = "Paid"
    elif invoice_amount is not None and status == "Completed":
        status = "Invoiced"

    valid_files = [file for file in files if file and file.filename]
    if can_manage_receipts():
        valid_receipt_files = [file for file in receipt_files if file and file.filename]
    else:
        valid_receipt_files = []
    job_fields_changed = any(
        [
            status != job["status"],
            client_name != (job["client_name"] or ""),
            proposal_amount != job["proposal_amount"],
            proposal_sent_date != job["proposal_sent_date"],
            decision_date != job["decision_date"],
            rejection_reason != (job["rejection_reason"] or ""),
            invoice_amount != job["invoice_amount"],
            payment_status != (job["payment_status"] or "Not Paid"),
            assigned_to != job["assigned_to"],
            client_id != job["client_id"],
        ]
    )
    if not notes and not valid_files and not valid_receipt_files and not job_fields_changed:
        flash("Add notes, photos, or change the status before submitting.", "error")
        return redirect(url_for("update_job", job_id=job_id))

    now = datetime.now().isoformat(timespec="seconds")
    update_group = uuid.uuid4().hex
    saved_paths = []
    saved_receipt_paths = []

    try:
        for file in valid_files:
            if not allowed_file(file.filename):
                flash(f"Skipped unsupported file: {file.filename}", "error")
                continue

            original_name = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            filename = f"job-{job_id}-{timestamp}-{original_name}"
            file_path = UPLOAD_FOLDER / filename
            file.save(file_path)
            saved_paths.append(f"uploads/{filename}")

        for file in valid_receipt_files:
            if not allowed_receipt_file(file.filename):
                flash(f"Skipped unsupported receipt/bill: {file.filename}", "error")
                continue

            original_name = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            filename = f"job-{job_id}-{timestamp}-receipt-{original_name}"
            file_path = UPLOAD_FOLDER / filename
            file.save(file_path)
            saved_receipt_paths.append(f"uploads/{filename}")

        if not saved_paths and not saved_receipt_paths and not notes and not job_fields_changed:
            flash("No update was saved. Please add notes, change status, or upload supported files.", "error")
            return redirect(url_for("update_job", job_id=job_id))

        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    client_name = ?,
                    proposal_amount = ?,
                    proposal_sent_date = ?,
                    decision_date = ?,
                    rejection_reason = ?,
                    invoice_amount = ?,
                    payment_status = ?,
                    assigned_to = ?,
                    client_id = ?
                WHERE id = ?
                """,
                (
                    status,
                    client_name,
                    proposal_amount,
                    proposal_sent_date,
                    decision_date,
                    rejection_reason,
                    invoice_amount,
                    payment_status,
                    assigned_to,
                    client_id,
                    job_id,
                ),
            )

            if saved_paths:
                for image_path in saved_paths:
                    conn.execute(
                        """
                        INSERT INTO updates (job_id, notes, image_path, receipt_path, update_group, user_id, author_role, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (job_id, notes, image_path, None, update_group, g.user["id"], g.user["role"], now),
                    )

            if saved_receipt_paths:
                for receipt_path in saved_receipt_paths:
                    conn.execute(
                        """
                        INSERT INTO updates (job_id, notes, image_path, receipt_path, update_group, user_id, author_role, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (job_id, notes, None, receipt_path, update_group, g.user["id"], g.user["role"], now),
                    )

            if not saved_paths and not saved_receipt_paths and (notes or job_fields_changed):
                conn.execute(
                    """
                    INSERT INTO updates (job_id, notes, image_path, receipt_path, update_group, user_id, author_role, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (job_id, notes, None, None, update_group, g.user["id"], g.user["role"], now),
                )

    except OSError:
        app.logger.exception("Failed to save job update")
        flash("Something went wrong while saving the update. Please try again.", "error")
        return redirect(url_for("update_job", job_id=job_id))

    flash("Job update saved.", "success")
    return redirect(url_for("update_job", job_id=job_id))


@app.route("/comment/<int:job_id>", methods=("POST",))
@login_required
@role_required("client")
def client_comment(job_id):
    job = get_job_or_404(job_id)
    if job is None:
        return redirect(url_for("index"))
    if not can_view_job(job):
        flash("You do not have permission to comment on that job.", "error")
        return redirect(url_for("index"))

    comment = request.form.get("comment", "").strip()
    if not comment:
        flash("Please write a comment before submitting.", "error")
        return redirect(url_for("update_job", job_id=job_id))

    now = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO updates (job_id, notes, image_path, receipt_path, update_group, user_id, author_role, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, comment, None, None, uuid.uuid4().hex, g.user["id"], g.user["role"], now),
        )
    flash("Comment added.", "success")
    return redirect(url_for("update_job", job_id=job_id))


@app.route("/delete/<int:job_id>", methods=("POST",))
@login_required
@role_required("admin")
def delete_job(job_id):
    job = get_job_or_404(job_id)
    if job is None:
        return redirect(url_for("index"))

    with get_db_connection() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    flash("Job deleted.", "success")
    return redirect(url_for("index"))


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    stored_path = f"uploads/{filename}"
    with get_db_connection() as conn:
        update = conn.execute(
            """
            SELECT updates.job_id, updates.image_path, updates.receipt_path, jobs.assigned_to, jobs.client_id
            FROM updates
            JOIN jobs ON jobs.id = updates.job_id
            WHERE updates.image_path = ? OR updates.receipt_path = ?
            LIMIT 1
            """,
            (stored_path, stored_path),
        ).fetchone()

    if update is None:
        flash("File not found.", "error")
        return redirect(url_for("index"))

    if update["receipt_path"] == stored_path and not can_manage_receipts():
        flash("You do not have permission to view financial documents.", "error")
        return redirect(url_for("index"))

    fake_job = {
        "assigned_to": update["assigned_to"],
        "client_id": update["client_id"],
    }
    if not can_view_job(fake_job):
        flash("You do not have permission to view that file.", "error")
        return redirect(url_for("index"))

    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.errorhandler(413)
def file_too_large(_error):
    flash("Upload is too large. Please upload fewer or smaller photos.", "error")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):
    return render_template("500.html"), 500


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
