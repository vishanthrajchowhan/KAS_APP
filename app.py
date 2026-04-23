import os
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from psycopg import errors
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

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

# Estimate statuses
ESTIMATE_STATUSES = ("Draft", "Sent", "Viewed", "Approved", "Rejected", "Expired")

# Service types for estimates
SERVICE_TYPES = (
    "Waterproofing",
    "Roof Coating",
    "Exterior Painting",
    "Interior Painting",
    "Caulking / Sealants",
    "Concrete Repair",
    "Stucco Repair",
    "Balcony Waterproofing",
    "Garage / Deck Coating",
    "Pressure Cleaning",
    "Commercial Building Maintenance",
    "Custom Construction Services",
)

# Service types for leads/jobs
JOB_SERVICE_TYPES = (
    "Waterproofing",
    "Exterior Painting",
    "Interior Painting",
    "Drywall",
    "Caulking",
    "Roofing",
    "Tiles",
    "Other Related Services",
)

# Service templates - common line items by service type
SERVICE_TEMPLATES = {
    "Waterproofing": [
        {"name": "Surface Preparation", "description": "Clean and prep surface", "unit": "sqft"},
        {"name": "Waterproofing Coating", "description": "Apply waterproofing coating", "unit": "sqft"},
        {"name": "Labor - Waterproofing", "description": "Labor", "unit": "hour"},
    ],
    "Roof Coating": [
        {"name": "Surface Cleaning", "description": "Pressure clean roof surface", "unit": "sqft"},
        {"name": "Repair & Patching", "description": "Roof repair and patching", "unit": "sqft"},
        {"name": "Coating Application", "description": "Apply roof coating", "unit": "sqft"},
        {"name": "Labor - Roof Coating", "description": "Labor", "unit": "hour"},
    ],
    "Exterior Painting": [
        {"name": "Surface Prep", "description": "Pressure wash and prep", "unit": "sqft"},
        {"name": "Primer", "description": "Primer application", "unit": "sqft"},
        {"name": "Paint - Exterior", "description": "Paint application (2 coats)", "unit": "sqft"},
        {"name": "Labor - Painting", "description": "Labor", "unit": "hour"},
    ],
    "Interior Painting": [
        {"name": "Surface Prep", "description": "Prep and patch drywall", "unit": "sqft"},
        {"name": "Primer", "description": "Primer application", "unit": "sqft"},
        {"name": "Paint - Interior", "description": "Paint application (2 coats)", "unit": "sqft"},
        {"name": "Labor - Painting", "description": "Labor", "unit": "hour"},
    ],
    "Caulking / Sealants": [
        {"name": "Sealant Removal", "description": "Remove old sealant", "unit": "linear_ft"},
        {"name": "Joint Prep", "description": "Clean and prep joints", "unit": "linear_ft"},
        {"name": "Sealant Install", "description": "Install new sealant", "unit": "linear_ft"},
        {"name": "Labor - Caulking", "description": "Labor", "unit": "hour"},
    ],
    "Concrete Repair": [
        {"name": "Surface Prep", "description": "Clean and prepare concrete", "unit": "sqft"},
        {"name": "Concrete Patching", "description": "Patch and repair concrete", "unit": "sqft"},
        {"name": "Sealant", "description": "Seal repaired concrete", "unit": "sqft"},
        {"name": "Labor - Concrete", "description": "Labor", "unit": "hour"},
    ],
    "Stucco Repair": [
        {"name": "Surface Prep", "description": "Prepare stucco surface", "unit": "sqft"},
        {"name": "Stucco Patching", "description": "Patch damaged stucco", "unit": "sqft"},
        {"name": "Finishing", "description": "Match and finish stucco", "unit": "sqft"},
        {"name": "Labor - Stucco", "description": "Labor", "unit": "hour"},
    ],
    "Balcony Waterproofing": [
        {"name": "Surface Prep", "description": "Clean and prep balcony", "unit": "sqft"},
        {"name": "Waterproofing Membrane", "description": "Install waterproofing", "unit": "sqft"},
        {"name": "Labor - Balcony", "description": "Labor", "unit": "hour"},
    ],
    "Garage / Deck Coating": [
        {"name": "Surface Prep", "description": "Clean and degrease", "unit": "sqft"},
        {"name": "Primer", "description": "Primer application", "unit": "sqft"},
        {"name": "Coating Application", "description": "Epoxy/Polyurethane coating", "unit": "sqft"},
        {"name": "Labor - Coating", "description": "Labor", "unit": "hour"},
    ],
    "Pressure Cleaning": [
        {"name": "Pressure Cleaning Service", "description": "Professional pressure washing", "unit": "sqft"},
        {"name": "Labor - Cleaning", "description": "Labor", "unit": "hour"},
    ],
    "Commercial Building Maintenance": [
        {"name": "General Maintenance", "description": "Building maintenance service", "unit": "hour"},
        {"name": "Materials", "description": "Materials and supplies", "unit": "lump_sum"},
    ],
    "Custom Construction Services": [
        {"name": "Labor", "description": "Labor", "unit": "hour"},
        {"name": "Materials", "description": "Materials and supplies", "unit": "lump_sum"},
    ],
}



app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-this-secret")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
app.config["VAPID_PUBLIC_KEY"] = os.environ.get("VAPID_PUBLIC_KEY", "").strip()


def build_postgres_conninfo():
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        return None

    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://") :]

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    return database_url


POSTGRES_CONNINFO = build_postgres_conninfo()
POSTGRES_POOL = None
if POSTGRES_CONNINFO:
    POSTGRES_POOL = ConnectionPool(
        conninfo=POSTGRES_CONNINFO,
        min_size=int(os.environ.get("DB_POOL_MIN_SIZE", "1")),
        max_size=int(os.environ.get("DB_POOL_MAX_SIZE", "5")),
        open=False,
        kwargs={
            "row_factory": dict_row,
            "autocommit": True,
            "prepare_threshold": None,
        },
    )


def get_postgres_pool():
    if POSTGRES_POOL is None:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it in environment or .env file."
        )
    if POSTGRES_POOL.closed:
        POSTGRES_POOL.open(wait=True)
    return POSTGRES_POOL


def postgres_now():
    pool = get_postgres_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT NOW() AS now")
            row = cur.fetchone()
            return row["now"]


def test_postgres_connection():
    try:
        now_value = postgres_now()
        return True, str(now_value)
    except Exception as exc:
        return False, str(exc)


class PgConnection:
    def __init__(self, pool):
        self.pool = pool
        self._pool_ctx = None
        self.conn = None

    def __enter__(self):
        self._pool_ctx = self.pool.connection()
        self.conn = self._pool_ctx.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.conn:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        return self._pool_ctx.__exit__(exc_type, exc, tb)

    @staticmethod
    def _to_postgres_placeholders(query):
        return query.replace("?", "%s")

    def execute(self, query, params=None):
        cursor = self.conn.cursor()
        cursor.execute(self._to_postgres_placeholders(query), tuple(params or ()))
        return cursor


def get_db_connection():
    return PgConnection(get_postgres_pool())


def init_db():
    UPLOAD_FOLDER.mkdir(exist_ok=True)
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
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
                id BIGSERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                service_type TEXT,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Lead',
                client_name TEXT,
                proposal_amount REAL,
                proposal_sent_date TEXT,
                decision_date TEXT,
                rejection_reason TEXT,
                invoice_amount REAL,
                payment_status TEXT NOT NULL DEFAULT 'Not Paid',
                assigned_to BIGINT REFERENCES users(id) ON DELETE SET NULL,
                client_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        migrate_jobs_table(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS updates (
                id BIGSERIAL PRIMARY KEY,
                job_id BIGINT NOT NULL,
                notes TEXT,
                image_path TEXT,
                receipt_path TEXT,
                update_group TEXT,
                user_id BIGINT,
                author_role TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
            """
        )
        migrate_updates_table(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS estimates (
                id BIGSERIAL PRIMARY KEY,
                estimate_number TEXT NOT NULL UNIQUE,
                client_name TEXT NOT NULL,
                company_name TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                service_type TEXT NOT NULL,
                project_description TEXT,
                status TEXT NOT NULL DEFAULT 'Draft',
                subtotal DOUBLE PRECISION NOT NULL DEFAULT 0,
                tax DOUBLE PRECISION DEFAULT 0,
                total DOUBLE PRECISION NOT NULL DEFAULT 0,
                notes TEXT,
                created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                sent_at TEXT,
                approved_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS estimate_items (
                id BIGSERIAL PRIMARY KEY,
                estimate_id BIGINT NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
                item_name TEXT NOT NULL,
                description TEXT,
                quantity DOUBLE PRECISION NOT NULL,
                unit TEXT NOT NULL,
                unit_price DOUBLE PRECISION NOT NULL,
                line_total DOUBLE PRECISION NOT NULL,
                sort_order INTEGER DEFAULT 0
            )
            """
        )
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
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS client_name TEXT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS service_type TEXT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS proposal_amount DOUBLE PRECISION")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS proposal_sent_date TEXT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS decision_date TEXT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS rejection_reason TEXT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS invoice_amount DOUBLE PRECISION")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS payment_status TEXT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS assigned_to BIGINT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS client_id BIGINT")

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
    conn.execute("ALTER TABLE updates ADD COLUMN IF NOT EXISTS update_group TEXT")
    conn.execute("ALTER TABLE updates ADD COLUMN IF NOT EXISTS receipt_path TEXT")
    conn.execute("ALTER TABLE updates ADD COLUMN IF NOT EXISTS user_id BIGINT")
    conn.execute("ALTER TABLE updates ADD COLUMN IF NOT EXISTS author_role TEXT")


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


def generate_estimate_number(conn):
    """Generate next estimate number like KAS-1001, KAS-1002, etc."""
    result = conn.execute(
        "SELECT COUNT(*) AS total FROM estimates"
    ).fetchone()
    next_num = 1001 + (result["total"] or 0)
    return f"KAS-{next_num}"


def get_estimate_or_404(estimate_id):
    with get_db_connection() as conn:
        estimate = conn.execute(
            "SELECT * FROM estimates WHERE id = ?", (estimate_id,)
        ).fetchone()
    if estimate is None:
        flash("Estimate not found.", "error")
        return None
    return estimate


def get_estimate_items(conn, estimate_id):
    """Get all line items for an estimate."""
    items = conn.execute(
        """
        SELECT * FROM estimate_items
        WHERE estimate_id = ?
        ORDER BY sort_order, id
        """,
        (estimate_id,),
    ).fetchall()
    return items


def calculate_estimate_totals(items):
    """Calculate subtotal, tax, and total from items."""
    subtotal = sum(item.get("line_total", 0) for item in items)
    tax = subtotal * 0.065  # Florida 6.5% tax (can be made configurable)
    total = subtotal + tax
    return {
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
    }



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


@app.route("/manifest.json")
def pwa_manifest():
    return send_from_directory(
        BASE_DIR / "static",
        "manifest.json",
        mimetype="application/manifest+json",
    )


@app.route("/sw.js")
def pwa_service_worker():
    response = send_from_directory(BASE_DIR / "static", "sw.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/api/push/vapid-public-key", methods=("GET",))
def vapid_public_key():
    return jsonify({"publicKey": app.config.get("VAPID_PUBLIC_KEY", "")})


@app.route("/api/push/subscribe", methods=("POST",))
@login_required
def save_push_subscription():
    payload = request.get_json(silent=True) or {}
    subscription = payload.get("subscription")
    if not subscription:
        return jsonify({"ok": False, "error": "Missing subscription payload."}), 400

    # Push persistence can later be migrated to a table keyed by user id.
    session["push_subscription"] = subscription
    return jsonify(
        {
            "ok": True,
            "message": "Subscription received. Server push dispatch can be enabled with VAPID keys.",
            "events_ready": [
                "new_job_assigned",
                "estimate_approved",
                "new_update_uploaded",
            ],
        }
    )


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
                 MAX(employee.name) AS assigned_employee,
                 MAX(client.name) AS client_user_name,
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

        monthly_revenue_rows = conn.execute(
            f"""
            SELECT
                SUBSTRING(created_at, 1, 7) AS month,
                COALESCE(SUM(CASE WHEN payment_status = 'Paid' THEN invoice_amount ELSE 0 END), 0) AS value
            FROM jobs
            {metrics_where}
            GROUP BY SUBSTRING(created_at, 1, 7)
            ORDER BY month DESC
            LIMIT 6
            """,
            role_params,
        ).fetchall()

        recent_activity = conn.execute(
            f"""
            SELECT
                updates.timestamp,
                updates.notes,
                updates.author_role,
                jobs.name AS job_name,
                jobs.status AS job_status
            FROM updates
            JOIN jobs ON jobs.id = updates.job_id
            {metrics_where}
            ORDER BY updates.timestamp DESC
            LIMIT 8
            """,
            role_params,
        ).fetchall()

        pending_estimates = 0
        if dashboard_role == "admin":
            pending_estimate_row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM estimates
                WHERE status IN ('Draft', 'Sent', 'Viewed')
                """
            ).fetchone()
            pending_estimates = pending_estimate_row["count"] if pending_estimate_row else 0

        month_prefix = datetime.now().strftime("%Y-%m")
        new_leads_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM jobs
            {f'WHERE {role_clause} AND ' if role_clause else 'WHERE '}status = 'Lead' AND SUBSTRING(created_at, 1, 7) = ?
            """,
            role_params + [month_prefix],
        ).fetchone()
        new_leads = new_leads_row["count"] if new_leads_row else 0

    proposals_sent = metrics["proposals_sent"] or 0
    approved_jobs = metrics["approved_jobs"] or 0
    conversion_rate = round((approved_jobs / proposals_sent) * 100, 1) if proposals_sent else 0
    can_view_financials_flag = dashboard_role == "admin"
    can_manage_jobs_flag = dashboard_role == "admin"

    monthly_revenue = list(reversed(monthly_revenue_rows))
    monthly_peak = max((row["value"] or 0) for row in monthly_revenue) if monthly_revenue else 0

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
        pending_estimates=pending_estimates,
        new_leads=new_leads,
        monthly_revenue=monthly_revenue,
        monthly_peak=monthly_peak,
        recent_activity=recent_activity,
    )


@app.route("/analytics")
@login_required
@role_required("admin")
def analytics():
    """Admin analytics dashboard for business performance."""
    with get_db_connection() as conn:
        jobs_by_status = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM jobs
            GROUP BY status
            ORDER BY count DESC, status ASC
            """
        ).fetchall()

        monthly_revenue = conn.execute(
            """
            SELECT
                SUBSTRING(created_at, 1, 7) AS month,
                COALESCE(SUM(CASE WHEN payment_status = 'Paid' THEN invoice_amount ELSE 0 END), 0) AS paid_revenue,
                COALESCE(SUM(CASE WHEN status != 'Rejected' THEN proposal_amount ELSE 0 END), 0) AS pipeline_revenue
            FROM jobs
            GROUP BY SUBSTRING(created_at, 1, 7)
            ORDER BY month DESC
            LIMIT 12
            """
        ).fetchall()

        recent_approvals = conn.execute(
            """
            SELECT estimate_number, client_name, total, approved_at
            FROM estimates
            WHERE status = 'Approved'
            ORDER BY approved_at DESC NULLS LAST, created_at DESC
            LIMIT 8
            """
        ).fetchall()

    monthly_revenue = list(reversed(monthly_revenue))
    revenue_peak = max((row["paid_revenue"] or 0) for row in monthly_revenue) if monthly_revenue else 0

    return render_template(
        "analytics.html",
        jobs_by_status=jobs_by_status,
        monthly_revenue=monthly_revenue,
        revenue_peak=revenue_peak,
        recent_approvals=recent_approvals,
        money=money,
    )


@app.route("/settings", methods=("GET", "POST"))
@login_required
@role_required("admin")
def settings():
    """Company and workspace settings panel."""
    if request.method == "POST":
        flash("Settings saved. Company preferences updated.", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html")


@app.route("/add", methods=("GET", "POST"))
@login_required
@role_required("admin")
def add_job():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        client_name = request.form.get("client_name", "").strip()
        location = request.form.get("location", "").strip()
        service_type = request.form.get("service_type", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "Lead").strip()
        proposal_amount = parse_money(request.form.get("proposal_amount"))
        proposal_sent_date = parse_date(request.form.get("proposal_sent_date"))
        assigned_to = request.form.get("assigned_to", type=int)
        client_id = request.form.get("client_id", type=int)

        if status not in STATUSES:
            status = "Lead"
        if service_type not in JOB_SERVICE_TYPES:
            service_type = "Other Related Services"

        with get_db_connection() as conn:
            employees = conn.execute(
                "SELECT id, name, email FROM users WHERE role = 'employee' ORDER BY name"
            ).fetchall()
            clients = conn.execute(
                "SELECT id, name, email FROM users WHERE role = 'client' ORDER BY name"
            ).fetchall()

        if not name or not client_name or not location or not description or not service_type:
            flash("Please fill out the job, client, location, service type, and description.", "error")
            return render_template(
                "add_job.html",
                name=name,
                client_name=client_name,
                location=location,
                service_type=service_type,
                description=description,
                status=status,
                proposal_amount=proposal_amount,
                proposal_sent_date=proposal_sent_date,
                service_types=JOB_SERVICE_TYPES,
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
                    name, client_name, location, service_type, description, status,
                    proposal_amount, proposal_sent_date, payment_status,
                    assigned_to, client_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    client_name,
                    location,
                    service_type,
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
    return render_template(
        "add_job.html",
        statuses=STATUSES,
        service_types=JOB_SERVICE_TYPES,
        employees=employees,
        clients=clients,
    )


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
        except errors.UniqueViolation:
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


@app.route("/estimates")
@login_required
@role_required("admin")
def estimates():
    """List all estimates with filters."""
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    sort = request.args.get("sort", "newest").strip()
    
    where_clauses = []
    params = []
    
    if status_filter in ESTIMATE_STATUSES:
        where_clauses.append("status = ?")
        params.append(status_filter)
    
    if search:
        where_clauses.append(
            "(client_name LIKE ? OR company_name LIKE ? OR estimate_number LIKE ?)"
        )
        like_search = f"%{search}%"
        params.extend([like_search, like_search, like_search])
    
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    order_by = "created_at DESC"
    if sort == "oldest":
        order_by = "created_at ASC"
    elif sort == "name":
        order_by = "client_name ASC"
    elif sort == "value":
        order_by = "total DESC"
    
    with get_db_connection() as conn:
        estimate_list = conn.execute(
            f"""
            SELECT e.*, u.name as created_by_name
            FROM estimates e
            LEFT JOIN users u ON u.id = e.created_by
            {where_sql}
            ORDER BY {order_by}
            """,
            params,
        ).fetchall()
        
        status_counts = {
            row["status"]: row["count"]
            for row in conn.execute(
                f"""
                SELECT status, COUNT(*) AS count
                FROM estimates
                {where_sql}
                GROUP BY status
                """,
                params,
            ).fetchall()
        }
        
        metrics = conn.execute(
            """
            SELECT
                COUNT(*) AS total_estimates,
                SUM(CASE WHEN status = 'Draft' THEN 1 ELSE 0 END) AS draft_count,
                SUM(CASE WHEN status IN ('Sent', 'Viewed') THEN 1 ELSE 0 END) AS pending_count,
                SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) AS approved_count,
                COALESCE(SUM(CASE WHEN status = 'Approved' THEN total ELSE 0 END), 0) AS approved_value,
                COALESCE(SUM(total), 0) AS total_value
            FROM estimates
            """
        ).fetchone()
    
    return render_template(
        "estimates.html",
        estimates=estimate_list,
        statuses=ESTIMATE_STATUSES,
        status_counts=status_counts,
        metrics=metrics,
        money=money,
        filters={"q": search, "status": status_filter, "sort": sort},
    )


@app.route("/estimate/create", methods=("GET", "POST"))
@login_required
@role_required("admin")
def create_estimate():
    """Create a new estimate."""
    if request.method == "POST":
        client_name = request.form.get("client_name", "").strip()
        company_name = request.form.get("company_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        zip_code = request.form.get("zip", "").strip()
        service_type = request.form.get("service_type", "").strip()
        project_description = request.form.get("project_description", "").strip()
        notes = request.form.get("notes", "").strip()
        
        if not client_name or not service_type:
            flash("Client name and service type are required.", "error")
            return render_template(
                "create_estimate.html",
                service_types=SERVICE_TYPES,
                service_templates=SERVICE_TEMPLATES,
                client_name=client_name,
                company_name=company_name,
                phone=phone,
                email=email,
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                service_type=service_type,
                project_description=project_description,
                notes=notes,
            )
        
        now = datetime.now().isoformat(timespec="seconds")
        with get_db_connection() as conn:
            estimate_number = generate_estimate_number(conn)
            conn.execute(
                """
                INSERT INTO estimates (
                    estimate_number, client_name, company_name, phone, email,
                    address, city, state, zip, service_type, project_description,
                    status, notes, created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    estimate_number,
                    client_name,
                    company_name,
                    phone,
                    email,
                    address,
                    city,
                    state,
                    zip_code,
                    service_type,
                    project_description,
                    "Draft",
                    notes,
                    g.user["id"],
                    now,
                    now,
                ),
            )
            # Get the ID of the newly created estimate
            estimate = conn.execute(
                "SELECT id FROM estimates WHERE estimate_number = ?",
                (estimate_number,),
            ).fetchone()
        
        flash(f"Estimate {estimate_number} created.", "success")
        return redirect(url_for("edit_estimate", estimate_id=estimate["id"]))
    
    return render_template(
        "create_estimate.html",
        service_types=SERVICE_TYPES,
        service_templates=SERVICE_TEMPLATES,
    )


@app.route("/estimate/<int:estimate_id>")
@login_required
@role_required("admin")
def view_estimate(estimate_id):
    """View an estimate."""
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))
    
    with get_db_connection() as conn:
        items = get_estimate_items(conn, estimate_id)
    
    totals = calculate_estimate_totals(items)
    
    return render_template(
        "view_estimate.html",
        estimate=estimate,
        items=items,
        totals=totals,
        money=money,
        statuses=ESTIMATE_STATUSES,
    )


@app.route("/estimate/<int:estimate_id>/edit", methods=("GET", "POST"))
@login_required
@role_required("admin")
def edit_estimate(estimate_id):
    """Edit an estimate."""
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))
    
    if request.method == "POST":
        # Handle estimate header updates
        client_name = request.form.get("client_name", "").strip()
        company_name = request.form.get("company_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        zip_code = request.form.get("zip", "").strip()
        project_description = request.form.get("project_description", "").strip()
        notes = request.form.get("notes", "").strip()
        
        if not client_name:
            flash("Client name is required.", "error")
        else:
            now = datetime.now().isoformat(timespec="seconds")
            with get_db_connection() as conn:
                conn.execute(
                    """
                    UPDATE estimates
                    SET client_name = ?, company_name = ?, phone = ?, email = ?,
                        address = ?, city = ?, state = ?, zip = ?,
                        project_description = ?, notes = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        client_name,
                        company_name,
                        phone,
                        email,
                        address,
                        city,
                        state,
                        zip_code,
                        project_description,
                        notes,
                        now,
                        estimate_id,
                    ),
                )
            flash("Estimate updated.", "success")
            return redirect(url_for("view_estimate", estimate_id=estimate_id))
    
    with get_db_connection() as conn:
        items = get_estimate_items(conn, estimate_id)
    
    totals = calculate_estimate_totals(items)
    
    return render_template(
        "edit_estimate.html",
        estimate=estimate,
        items=items,
        totals=totals,
        money=money,
        service_types=SERVICE_TYPES,
        service_templates=SERVICE_TEMPLATES,
    )


@app.route("/estimate/<int:estimate_id>/item/add", methods=("POST",))
@login_required
@role_required("admin")
def add_estimate_item(estimate_id):
    """Add a line item to an estimate."""
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))
    
    item_name = request.form.get("item_name", "").strip()
    description = request.form.get("description", "").strip()
    quantity = request.form.get("quantity", type=float)
    unit = request.form.get("unit", "").strip()
    unit_price = request.form.get("unit_price", type=float)
    
    if not item_name or quantity is None or unit_price is None or not unit:
        flash("All fields are required for line items.", "error")
        return redirect(url_for("edit_estimate", estimate_id=estimate_id))
    
    line_total = quantity * unit_price
    
    with get_db_connection() as conn:
        # Get max sort order
        max_sort = conn.execute(
            "SELECT MAX(sort_order) AS max_sort FROM estimate_items WHERE estimate_id = ?",
            (estimate_id,),
        ).fetchone()
        next_sort = (max_sort["max_sort"] or 0) + 1
        
        conn.execute(
            """
            INSERT INTO estimate_items (
                estimate_id, item_name, description, quantity, unit,
                unit_price, line_total, sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                estimate_id,
                item_name,
                description,
                quantity,
                unit,
                unit_price,
                line_total,
                next_sort,
            ),
        )
        
        # Update estimate totals
        items = get_estimate_items(conn, estimate_id)
        totals = calculate_estimate_totals(items)
        now = datetime.now().isoformat(timespec="seconds")
        
        conn.execute(
            """
            UPDATE estimates
            SET subtotal = ?, tax = ?, total = ?, updated_at = ?
            WHERE id = ?
            """,
            (totals["subtotal"], totals["tax"], totals["total"], now, estimate_id),
        )
    
    flash("Line item added.", "success")
    return redirect(url_for("edit_estimate", estimate_id=estimate_id))


@app.route("/estimate/<int:estimate_id>/item/<int:item_id>/delete", methods=("POST",))
@login_required
@role_required("admin")
def delete_estimate_item(estimate_id, item_id):
    """Delete a line item from an estimate."""
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))
    
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM estimate_items WHERE id = ? AND estimate_id = ?",
            (item_id, estimate_id),
        )
        
        # Update estimate totals
        items = get_estimate_items(conn, estimate_id)
        totals = calculate_estimate_totals(items)
        now = datetime.now().isoformat(timespec="seconds")
        
        conn.execute(
            """
            UPDATE estimates
            SET subtotal = ?, tax = ?, total = ?, updated_at = ?
            WHERE id = ?
            """,
            (totals["subtotal"], totals["tax"], totals["total"], now, estimate_id),
        )
    
    flash("Line item deleted.", "success")
    return redirect(url_for("edit_estimate", estimate_id=estimate_id))


@app.route("/estimate/<int:estimate_id>/send", methods=("POST",))
@login_required
@role_required("admin")
def send_estimate(estimate_id):
    """Mark estimate as sent and optionally email it."""
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))
    
    send_email = request.form.get("send_email") == "on"
    
    now = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE estimates
            SET status = ?, sent_at = ?, updated_at = ?
            WHERE id = ?
            """,
            ("Sent", now, now, estimate_id),
        )
    
    if send_email and estimate["email"]:
        flash(f"Estimate sent to {estimate['email']}. (Email integration coming soon)", "success")
    else:
        flash("Estimate marked as sent.", "success")
    
    return redirect(url_for("view_estimate", estimate_id=estimate_id))


@app.route("/estimate/<int:estimate_id>/approve", methods=("POST",))
@login_required
@role_required("admin")
def approve_estimate(estimate_id):
    """Mark estimate as approved."""
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))
    
    now = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE estimates
            SET status = ?, approved_at = ?, updated_at = ?
            WHERE id = ?
            """,
            ("Approved", now, now, estimate_id),
        )
    
    flash("Estimate approved.", "success")
    return redirect(url_for("view_estimate", estimate_id=estimate_id))


@app.route("/estimate/<int:estimate_id>/reject", methods=("POST",))
@login_required
@role_required("admin")
def reject_estimate(estimate_id):
    """Mark estimate as rejected."""
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))
    
    now = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE estimates
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            ("Rejected", now, estimate_id),
        )
    
    flash("Estimate rejected.", "success")
    return redirect(url_for("view_estimate", estimate_id=estimate_id))


@app.route("/estimate/<int:estimate_id>/convert", methods=("POST",))
@login_required
@role_required("admin")
def convert_estimate_to_job(estimate_id):
    """Convert an approved estimate to a job in the pipeline."""
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))
    
    if estimate["status"] != "Approved":
        flash("Only approved estimates can be converted to jobs.", "error")
        return redirect(url_for("view_estimate", estimate_id=estimate_id))
    
    # Create a job from the estimate
    now = datetime.now().isoformat(timespec="seconds")
    job_name = f"{estimate['service_type']} - {estimate['client_name']}"
    
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                name, client_name, location, description, status,
                proposal_amount, proposal_sent_date, payment_status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_name,
                estimate["client_name"],
                estimate["address"] or "See estimate",
                estimate["project_description"] or f"{estimate['service_type']} project",
                "Scheduled",
                estimate["total"],
                now[:10],  # Extract date from datetime
                "Not Paid",
                now,
            ),
        )
        
        # Get the newly created job ID
        job = conn.execute(
            "SELECT id FROM jobs WHERE client_name = ? AND created_at = ? ORDER BY id DESC LIMIT 1",
            (estimate["client_name"], now),
        ).fetchone()
    
    flash(f"Estimate converted to job. You can now track it in the Pipeline.", "success")
    return redirect(url_for("update_job", job_id=job["id"]))


@app.route("/estimate/<int:estimate_id>/duplicate", methods=("POST",))
@login_required
@role_required("admin")
def duplicate_estimate(estimate_id):
    """Duplicate an estimate."""
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))
    
    now = datetime.now().isoformat(timespec="seconds")
    
    with get_db_connection() as conn:
        # Generate new estimate number
        estimate_number = generate_estimate_number(conn)
        
        # Create new estimate
        conn.execute(
            """
            INSERT INTO estimates (
                estimate_number, client_name, company_name, phone, email,
                address, city, state, zip, service_type, project_description,
                status, notes, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                estimate_number,
                estimate["client_name"],
                estimate["company_name"],
                estimate["phone"],
                estimate["email"],
                estimate["address"],
                estimate["city"],
                estimate["state"],
                estimate["zip"],
                estimate["service_type"],
                estimate["project_description"],
                "Draft",
                estimate["notes"],
                g.user["id"],
                now,
                now,
            ),
        )
        
        # Get the new estimate ID
        new_estimate = conn.execute(
            "SELECT id FROM estimates WHERE estimate_number = ?",
            (estimate_number,),
        ).fetchone()
        
        # Copy line items
        items = get_estimate_items(conn, estimate_id)
        for idx, item in enumerate(items):
            conn.execute(
                """
                INSERT INTO estimate_items (
                    estimate_id, item_name, description, quantity, unit,
                    unit_price, line_total, sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_estimate["id"],
                    item["item_name"],
                    item["description"],
                    item["quantity"],
                    item["unit"],
                    item["unit_price"],
                    item["line_total"],
                    idx,
                ),
            )
        
        # Update totals
        new_items = get_estimate_items(conn, new_estimate["id"])
        totals = calculate_estimate_totals(new_items)
        
        conn.execute(
            """
            UPDATE estimates
            SET subtotal = ?, tax = ?, total = ?
            WHERE id = ?
            """,
            (totals["subtotal"], totals["tax"], totals["total"], new_estimate["id"]),
        )
    
    flash(f"Estimate duplicated as {estimate_number}.", "success")
    return redirect(url_for("edit_estimate", estimate_id=new_estimate["id"]))



    ok, result = test_postgres_connection()
    return (
        jsonify(
            {
                "ok": ok,
                "database": "postgres",
                "query": "SELECT NOW()",
                "now": result if ok else None,
                "error": None if ok else result,
            }
        ),
        200 if ok else 500,
    )


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
    if not POSTGRES_CONNINFO:
        raise RuntimeError(
            "DATABASE_URL is required for PostgreSQL mode. Add DATABASE_URL in .env or environment variables."
        )

    if POSTGRES_CONNINFO:
        ok, result = test_postgres_connection()
        if ok:
            app.logger.info("PostgreSQL connected. SELECT NOW() => %s", result)
        else:
            app.logger.warning("PostgreSQL connection failed: %s", result)
    else:
        app.logger.info("DATABASE_URL not set. PostgreSQL checks skipped.")

    init_db()
    port = int(os.environ.get("PORT", "5000"))
    is_production = os.environ.get("RENDER") == "true" or os.environ.get("FLASK_ENV") == "production"
    app.run(host="0.0.0.0", port=port, debug=not is_production)
