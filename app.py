import os
import uuid
from io import BytesIO
from datetime import datetime, timedelta
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
from supabase import create_client
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

UPLOAD_FOLDER = BASE_DIR / "uploads"
STATIC_UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
BRANDING_UPLOAD_FOLDER = STATIC_UPLOAD_FOLDER / "branding"
PUBLIC_LOGO_FILE = STATIC_UPLOAD_FOLDER / "company-logo.png"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_RECEIPT_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "doc", "docx", "xls", "xlsx"}
SUPABASE_STORAGE_BUCKETS = {
    "job_photos": "job-photos",
    "receipts": "receipts",
    "logos": "logos",
    "documents": "documents",
}
IMAGE_MIME_TYPES = {
    "gif": "image/gif",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
DOCUMENT_MIME_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
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
    "Caulking",
    "Drywall",
    "Roofing",
    "Tiles",
    "Other",
)

# Service types for leads/jobs
JOB_SERVICE_TYPES = (
    "Waterproofing",
    "Exterior Window Waterproofing",
    "Commercial Windows Waterproofing",
    "Roof Coating",
    "Wall Coating",
    "Exterior Painting",
    "Interior Painting",
    "Electrostatic Painting",
    "Limestone Sealant Joint Replacement",
    "Exterior Pressure Washing",
    "Metal Roof & Railing Painting",
    "Caulking",
    "Sealant Joint Replacement",
    "Drywall",
    "Roofing",
    "Tiles",
    "Concrete Repair",
    "Stucco Repair",
    "Balcony Waterproofing",
    "Parking Lot Connector Painting",
    "Other",
)
OTHER_SERVICE_LABEL = "Other"
LEGACY_OTHER_SERVICE_LABEL = "Other Related Services"
TASK_STATUSES = ("Not Started", "In Progress", "Done")
SERVICE_TASK_TEMPLATES = {
    "Waterproofing": ("Inspect substrate", "Prepare surface", "Apply waterproofing system", "Final water-tightness review"),
    "Exterior Window Waterproofing": ("Inspect window perimeters", "Remove failed sealant", "Prime joints", "Install waterproof sealant", "Water test windows"),
    "Commercial Windows Waterproofing": ("Map commercial window scope", "Clean frames and joints", "Seal window perimeters", "Quality check completed sections"),
    "Roof Coating": ("Pressure clean roof", "Repair roof penetrations", "Apply primer", "Apply roof coating", "Final roof inspection"),
    "Wall Coating": ("Clean wall surfaces", "Repair cracks and openings", "Apply primer", "Apply wall coating", "Inspect finish"),
    "Exterior Painting": ("Pressure wash exterior", "Mask and protect areas", "Prime surfaces", "Apply finish coats", "Touch-up and cleanup"),
    "Interior Painting": ("Protect interior areas", "Patch drywall", "Prime surfaces", "Apply finish coats", "Final walkthrough"),
    "Electrostatic Painting": ("Prepare metal surfaces", "Mask surrounding areas", "Apply electrostatic coating", "Inspect adhesion and finish"),
    "Limestone Sealant Joint Replacement": ("Inspect limestone joints", "Remove existing sealant", "Prepare and prime joints", "Install new sealant", "Tool and inspect joints"),
    "Exterior Pressure Washing": ("Stage pressure washing area", "Pretreat stains", "Pressure wash surfaces", "Rinse and inspect"),
    "Metal Roof & Railing Painting": ("Prepare metal roof and railings", "Prime metal surfaces", "Apply finish coating", "Inspect coverage"),
    "Caulking": ("Remove loose caulking", "Clean joints", "Install sealant", "Tool and inspect sealant"),
    "Sealant Joint Replacement": ("Cut out failed sealant", "Clean joint cavity", "Install backer rod as needed", "Apply replacement sealant"),
    "Drywall": ("Protect work area", "Repair drywall", "Sand and prep", "Prime repaired areas"),
    "Roofing": ("Inspect roofing scope", "Repair roofing areas", "Seal penetrations", "Final roof review"),
    "Tiles": ("Inspect tile scope", "Remove damaged material", "Install or repair tile", "Clean and inspect"),
    "Concrete Repair": ("Inspect damaged concrete", "Prepare repair area", "Patch concrete", "Seal repaired surface"),
    "Stucco Repair": ("Remove loose stucco", "Patch stucco", "Match texture", "Prime repaired area"),
    "Balcony Waterproofing": ("Inspect balcony substrate", "Prepare balcony surface", "Install waterproofing membrane", "Inspect drainage and finish"),
    "Parking Lot Connector Painting": ("Prepare connector surfaces", "Mask adjacent areas", "Apply coating", "Inspect completed connector"),
    "Other": ("Confirm custom scope", "Schedule required materials", "Complete custom work", "Final inspection"),
}

DEFAULT_WORKSPACE_SETTINGS = {
    "company_name": "KAS Waterproofing & Building Services",
    "company_city": "Fort Lauderdale, Florida",
    "company_address": "",
    "company_state": "FL",
    "company_zip": "",
    "company_phone": "",
    "company_email": "",
    "theme": "light",
    "logo_path": "",
    "dark_mode_default": False,
    "notify_new_lead": True,
    "notify_estimate_approved": True,
    "notify_payment_received": True,
    "notify_photo_upload": True,
}

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
SUPABASE_CLIENT = None
STORAGE_BUCKETS_READY = False
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


def get_supabase_client():
    global SUPABASE_CLIENT
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_KEY", "").strip()
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required for Supabase Storage uploads.")
    if SUPABASE_CLIENT is None:
        SUPABASE_CLIENT = create_client(supabase_url, supabase_key)
    return SUPABASE_CLIENT


def supabase_storage_configured():
    return bool(os.environ.get("SUPABASE_URL", "").strip() and os.environ.get("SUPABASE_KEY", "").strip())


def ensure_storage_buckets():
    global STORAGE_BUCKETS_READY
    if STORAGE_BUCKETS_READY:
        return
    if not supabase_storage_configured():
        return

    client = get_supabase_client()
    for bucket_name in SUPABASE_STORAGE_BUCKETS.values():
        try:
            try:
                client.storage.create_bucket(bucket_name, options={"public": True})
            except TypeError:
                client.storage.create_bucket(bucket_name, {"public": True})
        except Exception as exc:
            message = str(exc).lower()
            if "already" not in message and "exist" not in message and "duplicate" not in message:
                app.logger.warning("Could not create Supabase bucket %s: %s", bucket_name, exc)
    STORAGE_BUCKETS_READY = True


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
    STATIC_UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    BRANDING_UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    ensure_storage_buckets()
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
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
                due_date TEXT,
                service_type TEXT,
                other_service_details TEXT,
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
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")
        migrate_jobs_table(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS updates (
                id BIGSERIAL PRIMARY KEY,
                job_id BIGINT NOT NULL,
                notes TEXT,
                image_path TEXT,
                photo_url TEXT,
                receipt_path TEXT,
                receipt_url TEXT,
                client_visible BOOLEAN NOT NULL DEFAULT FALSE,
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
            CREATE TABLE IF NOT EXISTS job_tasks (
                id BIGSERIAL PRIMARY KEY,
                job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                service_type TEXT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Not Started',
                sort_order INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )
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
                other_service_details TEXT,
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
                approved_at TEXT,
                deleted_at TEXT
            )
            """
        )
        migrate_estimates_table(conn)
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
        migrate_workspace_settings_table(conn)
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
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS due_date TEXT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS client_name TEXT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS service_type TEXT")
    conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS other_service_details TEXT")
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
    conn.execute("ALTER TABLE updates ADD COLUMN IF NOT EXISTS photo_url TEXT")
    conn.execute("ALTER TABLE updates ADD COLUMN IF NOT EXISTS receipt_url TEXT")
    conn.execute("ALTER TABLE updates ADD COLUMN IF NOT EXISTS client_visible BOOLEAN DEFAULT FALSE")
    conn.execute("ALTER TABLE updates ADD COLUMN IF NOT EXISTS user_id BIGINT")
    conn.execute("ALTER TABLE updates ADD COLUMN IF NOT EXISTS author_role TEXT")
    conn.execute("UPDATE updates SET client_visible = FALSE WHERE client_visible IS NULL")


def migrate_estimates_table(conn):
    conn.execute("ALTER TABLE estimates ADD COLUMN IF NOT EXISTS other_service_details TEXT")
    conn.execute("ALTER TABLE estimates ADD COLUMN IF NOT EXISTS deleted_at TEXT")


def migrate_workspace_settings_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            company_name TEXT NOT NULL,
            company_city TEXT NOT NULL,
            company_address TEXT,
            company_state TEXT,
            company_zip TEXT,
            company_phone TEXT,
            company_email TEXT,
            theme TEXT NOT NULL DEFAULT 'light',
            logo_path TEXT,
            dark_mode_default BOOLEAN NOT NULL DEFAULT FALSE,
            notify_new_lead BOOLEAN NOT NULL DEFAULT TRUE,
            notify_estimate_approved BOOLEAN NOT NULL DEFAULT TRUE,
            notify_payment_received BOOLEAN NOT NULL DEFAULT TRUE,
            notify_photo_upload BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS company_name TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS company_city TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS company_address TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS company_state TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS company_zip TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS company_phone TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS company_email TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS theme TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS logo_path TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS logo_url TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS dark_mode_default BOOLEAN")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS notify_new_lead BOOLEAN")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS notify_estimate_approved BOOLEAN")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS notify_payment_received BOOLEAN")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS notify_photo_upload BOOLEAN")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS created_at TEXT")
    conn.execute("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS updated_at TEXT")

    existing_settings = conn.execute("SELECT id FROM workspace_settings WHERE id = 1").fetchone()
    if existing_settings is None:
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO workspace_settings (
                id, company_name, company_city, company_address, company_state, company_zip, company_phone, company_email,
                theme, logo_path, dark_mode_default, notify_new_lead,
                notify_estimate_approved, notify_payment_received, notify_photo_upload,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                DEFAULT_WORKSPACE_SETTINGS["company_name"],
                DEFAULT_WORKSPACE_SETTINGS["company_city"],
                DEFAULT_WORKSPACE_SETTINGS["company_address"],
                DEFAULT_WORKSPACE_SETTINGS["company_state"],
                DEFAULT_WORKSPACE_SETTINGS["company_zip"],
                DEFAULT_WORKSPACE_SETTINGS["company_phone"],
                DEFAULT_WORKSPACE_SETTINGS["company_email"],
                DEFAULT_WORKSPACE_SETTINGS["theme"],
                DEFAULT_WORKSPACE_SETTINGS["logo_path"],
                DEFAULT_WORKSPACE_SETTINGS["dark_mode_default"],
                DEFAULT_WORKSPACE_SETTINGS["notify_new_lead"],
                DEFAULT_WORKSPACE_SETTINGS["notify_estimate_approved"],
                DEFAULT_WORKSPACE_SETTINGS["notify_payment_received"],
                DEFAULT_WORKSPACE_SETTINGS["notify_photo_upload"],
                now,
                now,
            ),
        )


def load_workspace_settings(conn):
    settings = dict(DEFAULT_WORKSPACE_SETTINGS)
    row = conn.execute("SELECT * FROM workspace_settings WHERE id = 1").fetchone()
    if row is None:
        migrate_workspace_settings_table(conn)
        row = conn.execute("SELECT * FROM workspace_settings WHERE id = 1").fetchone()

    if row is not None:
        settings.update({key: row[key] for key in row.keys() if key in settings or key in {"logo_path", "logo_url"}})

    settings["dark_mode_default"] = normalize_bool(settings.get("dark_mode_default"))
    settings["notify_new_lead"] = normalize_bool(settings.get("notify_new_lead"))
    settings["notify_estimate_approved"] = normalize_bool(settings.get("notify_estimate_approved"))
    settings["notify_payment_received"] = normalize_bool(settings.get("notify_payment_received"))
    settings["notify_photo_upload"] = normalize_bool(settings.get("notify_photo_upload"))
    settings["theme"] = settings.get("theme") or "light"
    settings["company_state"] = (settings.get("company_state") or "FL").strip()[:20]
    settings["logo_url"] = ""
    settings["uploaded_logo_url"] = ""
    settings["favicon_url"] = url_for("static", filename="icons/favicon.svg")
    settings["favicon_mimetype"] = "image/svg+xml"

    def with_asset_version(asset_url, file_path):
        if not file_path.exists():
            return asset_url
        version = int(file_path.stat().st_mtime)
        separator = "&" if "?" in asset_url else "?"
        return f"{asset_url}{separator}v={version}"

    stored_logo_url = (settings.get("logo_url") or "").strip()
    logo_path = (settings.get("logo_path") or "").strip()
    if stored_logo_url:
        settings["logo_url"] = stored_logo_url
    elif PUBLIC_LOGO_FILE.exists():
        settings["logo_url"] = with_asset_version(url_for("static", filename="uploads/company-logo.png"), PUBLIC_LOGO_FILE)
    elif logo_path.startswith("static/"):
        static_filename = logo_path[len("static/") :].lstrip("/")
        logo_file_path = BASE_DIR / static_filename
        settings["logo_url"] = with_asset_version(url_for("static", filename=static_filename), logo_file_path)
    elif logo_path.startswith("uploads/branding/"):
        fallback_name = logo_path.replace("uploads/branding/", "")
        logo_file_path = BRANDING_UPLOAD_FOLDER / fallback_name
        settings["logo_url"] = with_asset_version(url_for("public_branding_file", filename=fallback_name), logo_file_path)
    else:
        legacy_logo = STATIC_UPLOAD_FOLDER / "branding" / "Logo.png"
        if legacy_logo.exists():
            settings["logo_url"] = with_asset_version(url_for("static", filename="uploads/branding/Logo.png"), legacy_logo)

    if settings["logo_url"]:
        settings["uploaded_logo_url"] = settings["logo_url"]
        settings["favicon_url"] = settings["logo_url"]
        settings["favicon_mimetype"] = "image/png" if settings["logo_url"].lower().endswith(".png") else "image/svg+xml"
    return settings


def save_workspace_settings(conn, data):
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        UPDATE workspace_settings
        SET company_name = ?, company_city = ?, company_address = ?, company_state = ?, company_zip = ?, company_phone = ?, company_email = ?,
            theme = ?, logo_path = ?, logo_url = ?, dark_mode_default = ?, notify_new_lead = ?,
            notify_estimate_approved = ?, notify_payment_received = ?, notify_photo_upload = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (
            data["company_name"],
            data["company_city"],
            data["company_address"],
            data["company_state"],
            data["company_zip"],
            data["company_phone"],
            data["company_email"],
            data["theme"],
            data["logo_path"],
            data.get("logo_url", ""),
            bool(data["dark_mode_default"]),
            bool(data["notify_new_lead"]),
            bool(data["notify_estimate_approved"]),
            bool(data["notify_payment_received"]),
            bool(data["notify_photo_upload"]),
            now,
        ),
    )


def build_notifications_for_user(user, settings):
    if user is None:
        return []

    items = []
    now = datetime.now()

    def append_item(title, message, timestamp, href, kind):
        items.append(
            {
                "title": title,
                "message": message,
                "timestamp": timestamp,
                "href": href,
                "kind": kind,
            }
        )

    with get_db_connection() as conn:
        if user["role"] == "admin":
            if settings["notify_new_lead"]:
                rows = conn.execute(
                    """
                    SELECT id, name, created_at
                    FROM jobs
                    WHERE status = 'Lead'
                    ORDER BY created_at DESC, id DESC
                    LIMIT 3
                    """
                ).fetchall()
                for row in rows:
                    append_item("New lead submitted", row["name"], row["created_at"], url_for("update_job", job_id=row["id"]), "lead")

            if settings["notify_estimate_approved"]:
                rows = conn.execute(
                    """
                    SELECT id, estimate_number, client_name, approved_at
                    FROM estimates
                    WHERE status = 'Approved' AND deleted_at IS NULL
                    ORDER BY approved_at DESC NULLS LAST, created_at DESC
                    LIMIT 3
                    """
                ).fetchall()
                for row in rows:
                    append_item("Estimate approved", f"{row['estimate_number']} · {row['client_name']}", row["approved_at"] or now.isoformat(timespec="seconds"), url_for("view_estimate", estimate_id=row["id"]), "estimate")

            if settings["notify_payment_received"]:
                rows = conn.execute(
                    """
                    SELECT id, name, invoice_amount, created_at
                    FROM jobs
                    WHERE payment_status = 'Paid'
                    ORDER BY created_at DESC, id DESC
                    LIMIT 3
                    """
                ).fetchall()
                for row in rows:
                    append_item("Payment received", f"{row['name']} · {money(row['invoice_amount'])}", row["created_at"], url_for("update_job", job_id=row["id"]), "payment")

            if settings["notify_photo_upload"]:
                rows = conn.execute(
                    """
                    SELECT jobs.id, jobs.name, updates.timestamp
                    FROM updates
                    JOIN jobs ON jobs.id = updates.job_id
                    WHERE updates.image_path IS NOT NULL
                    ORDER BY updates.timestamp DESC, updates.id DESC
                    LIMIT 3
                    """
                ).fetchall()
                for row in rows:
                    append_item("Crew photo uploaded", row["name"], row["timestamp"], url_for("job_progress", job_id=row["id"]), "upload")
        else:
            visible_clause, visible_params = visible_jobs_where()
            rows = conn.execute(
                f"""
                SELECT updates.timestamp, updates.notes, jobs.id, jobs.name
                FROM updates
                JOIN jobs ON jobs.id = updates.job_id
                WHERE {visible_clause}
                ORDER BY updates.timestamp DESC, updates.id DESC
                LIMIT 6
                """,
                visible_params,
            ).fetchall()
            for row in rows:
                append_item("Recent activity", row["name"], row["timestamp"], url_for("job_progress", job_id=row["id"]), "activity")

    items.sort(key=lambda item: item["timestamp"] or "", reverse=True)
    return items[:6]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_logo_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_LOGO_EXTENSIONS


def allowed_receipt_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_RECEIPT_EXTENSIONS


def extension_for_file(filename, default_extension="bin"):
    if "." not in (filename or ""):
        return default_extension
    return filename.rsplit(".", 1)[1].lower()


def content_type_for_extension(extension):
    return IMAGE_MIME_TYPES.get(extension) or DOCUMENT_MIME_TYPES.get(extension) or "application/octet-stream"


def clean_storage_stem(filename):
    original_name = secure_filename(filename or "")
    if not original_name:
        return "upload"
    stem = original_name.rsplit(".", 1)[0]
    cleaned = "-".join(part for part in stem.lower().replace("_", "-").split("-") if part)
    return cleaned[:70] or "upload"


def compress_image_upload(uploaded_file, max_size=(1800, 1800), quality=82):
    try:
        from PIL import Image, ImageOps
    except ModuleNotFoundError as exc:
        raise ValueError("Image processing dependency is missing. Install Pillow in the active environment.") from exc

    extension = extension_for_file(uploaded_file.filename, "jpg")
    uploaded_file.stream.seek(0)
    with Image.open(uploaded_file.stream) as raw_image:
        image = ImageOps.exif_transpose(raw_image)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        output = BytesIO()

        if extension == "png":
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")
            image.save(output, format="PNG", optimize=True)
            stored_extension = "png"
            content_type = "image/png"
        elif extension == "webp":
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            image.save(output, format="WEBP", quality=quality, method=6)
            stored_extension = "webp"
            content_type = "image/webp"
        else:
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
            stored_extension = "jpg"
            content_type = "image/jpeg"

    output.seek(0)
    return output.getvalue(), stored_extension, content_type


def raw_upload_bytes(uploaded_file):
    extension = extension_for_file(uploaded_file.filename)
    uploaded_file.stream.seek(0)
    return uploaded_file.read(), extension, content_type_for_extension(extension)


def storage_path_for_upload(kind, source_filename, job_id=None, extension=None):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique = uuid.uuid4().hex[:8]
    extension = extension or extension_for_file(source_filename)
    clean_stem = clean_storage_stem(source_filename)
    if kind == "job_photo":
        return f"job-{job_id}-photo-{timestamp}-{unique}-{clean_stem}.{extension}"
    if kind == "receipt":
        return f"receipt-job{job_id}-{timestamp}-{unique}-{clean_stem}.{extension}"
    if kind == "logo":
        return f"logo-company-{timestamp}-{unique}.{extension}"
    return f"document-{timestamp}-{unique}-{clean_stem}.{extension}"


def upload_to_supabase_storage(bucket_name, storage_path, content, content_type):
    client = get_supabase_client()
    file_options = {"content-type": content_type, "upsert": "true"}
    client.storage.from_(bucket_name).upload(storage_path, content, file_options=file_options)
    public_url = client.storage.from_(bucket_name).get_public_url(storage_path)
    if isinstance(public_url, dict):
        return public_url.get("publicUrl") or public_url.get("public_url") or public_url.get("data", {}).get("publicUrl")
    return str(public_url)


def save_upload_to_storage(uploaded_file, bucket_key, kind, job_id=None, compress_images=True):
    if not supabase_storage_configured():
        raise RuntimeError("Supabase Storage is not configured. Add SUPABASE_URL and SUPABASE_KEY.")

    source_extension = extension_for_file(uploaded_file.filename)
    if compress_images and source_extension in IMAGE_MIME_TYPES:
        content, extension, content_type = compress_image_upload(uploaded_file)
    else:
        content, extension, content_type = raw_upload_bytes(uploaded_file)

    storage_path = storage_path_for_upload(kind, uploaded_file.filename, job_id=job_id, extension=extension)
    public_url = upload_to_supabase_storage(SUPABASE_STORAGE_BUCKETS[bucket_key], storage_path, content, content_type)
    return {"path": storage_path, "url": public_url}


def upload_local_file_to_storage(local_path, bucket_key, kind, job_id=None):
    extension = extension_for_file(local_path.name)
    content = local_path.read_bytes()
    storage_path = storage_path_for_upload(kind, local_path.name, job_id=job_id, extension=extension)
    public_url = upload_to_supabase_storage(
        SUPABASE_STORAGE_BUCKETS[bucket_key],
        storage_path,
        content,
        content_type_for_extension(extension),
    )
    return {"path": storage_path, "url": public_url}


def is_public_url(value):
    return str(value or "").startswith(("http://", "https://"))


def storage_public_url(bucket_key, storage_path):
    if not storage_path or not bucket_key or not supabase_storage_configured():
        return ""
    public_url = get_supabase_client().storage.from_(SUPABASE_STORAGE_BUCKETS[bucket_key]).get_public_url(storage_path)
    if isinstance(public_url, dict):
        return public_url.get("publicUrl") or public_url.get("public_url") or public_url.get("data", {}).get("publicUrl") or ""
    return str(public_url)


def media_url(stored_value, bucket_key=None):
    stored_value = stored_value or ""
    if not stored_value:
        return ""
    if is_public_url(stored_value):
        return stored_value
    if stored_value.startswith("uploads/"):
        return url_for("uploaded_file", filename=stored_value.replace("uploads/", "", 1))
    if bucket_key:
        return storage_public_url(bucket_key, stored_value)
    return stored_value


def display_file_name(stored_value):
    stored_value = stored_value or ""
    if "/" in stored_value:
        return stored_value.rsplit("/", 1)[-1]
    return stored_value


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


def parse_checkbox(value):
    return str(value or "").strip().lower() in {"1", "on", "true", "yes"}


def normalize_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if cleaned in {"0", "false", "f", "no", "n", "off", ""}:
            return False
    return bool(value)


def split_services(value):
    if not value:
        return []
    if isinstance(value, str):
        raw_items = [part.strip() for part in value.split(",")]
    else:
        raw_items = [str(part).strip() for part in value]

    deduped = []
    seen = set()
    for item in raw_items:
        if not item:
            continue
        normalized_item = OTHER_SERVICE_LABEL if item == LEGACY_OTHER_SERVICE_LABEL else item
        if normalized_item in seen:
            continue
        seen.add(normalized_item)
        deduped.append(normalized_item)
    return deduped


def sanitize_selected_services(values, allowed_services):
    allowed = set(allowed_services)
    selected = []
    seen = set()
    for value in values:
        item = (value or "").strip()
        if item == LEGACY_OTHER_SERVICE_LABEL:
            item = OTHER_SERVICE_LABEL
        if not item or item not in allowed or item in seen:
            continue
        seen.add(item)
        selected.append(item)
    return selected


def compose_service_text(values):
    return ", ".join(values)


def build_service_chips(service_type, other_details=""):
    chips = split_services(service_type)
    if OTHER_SERVICE_LABEL in chips and (other_details or "").strip():
        chips = [chip for chip in chips if chip != OTHER_SERVICE_LABEL]
        chips.append((other_details or "").strip())
    return chips


def default_tasks_for_service(service_type):
    return SERVICE_TASK_TEMPLATES.get(service_type, SERVICE_TASK_TEMPLATES[OTHER_SERVICE_LABEL])


def sync_job_tasks(conn, job_id, selected_services):
    existing = conn.execute(
        "SELECT service_type, title FROM job_tasks WHERE job_id = ?",
        (job_id,),
    ).fetchall()
    existing_keys = {(row["service_type"] or "", row["title"]) for row in existing}
    now = datetime.now().isoformat(timespec="seconds")
    sort_order = len(existing_keys)

    for service in selected_services:
        for title in default_tasks_for_service(service):
            key = (service, title)
            if key in existing_keys:
                continue
            sort_order += 1
            conn.execute(
                """
                INSERT INTO job_tasks (job_id, service_type, title, status, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, service, title, "Not Started", sort_order, now),
            )


def fetch_job_tasks(conn, job_id):
    return conn.execute(
        """
        SELECT *
        FROM job_tasks
        WHERE job_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (job_id,),
    ).fetchall()


def task_progress_summary(tasks):
    total = len(tasks)
    done = sum(1 for task in tasks if task["status"] == "Done")
    in_progress = sum(1 for task in tasks if task["status"] == "In Progress")
    percent = round((done / total) * 100) if total else 0
    return {"total": total, "done": done, "in_progress": in_progress, "percent": percent}


def process_logo_upload(uploaded_file):
    original_name = secure_filename(uploaded_file.filename)
    if not original_name or not allowed_logo_file(original_name):
        raise ValueError("Logo must be PNG, JPG, JPEG, or WEBP.")

    try:
        stored_logo = save_upload_to_storage(
            uploaded_file,
            "logos",
            "logo",
            compress_images=True,
        )
    except Exception as exc:
        raise ValueError("Unable to upload logo to Supabase Storage. Please try again.") from exc

    return stored_logo["path"], stored_logo["url"]


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
            "SELECT * FROM estimates WHERE id = ? AND deleted_at IS NULL", (estimate_id,)
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
            if not is_client() or normalize_bool(row.get("client_visible")):
                group_lookup[group_key]["photos"].append(
                    {
                        "id": row["id"],
                        "path": row["image_path"],
                        "url": row.get("photo_url") or media_url(row["image_path"], "job_photos"),
                        "client_visible": normalize_bool(row.get("client_visible")),
                    }
                )
        if row["receipt_path"]:
            group_lookup[group_key]["receipts"].append(
                {
                    "path": row["receipt_path"],
                    "url": row.get("receipt_url") or media_url(row["receipt_path"], "receipts"),
                    "name": display_file_name(row["receipt_path"]),
                }
            )

    if is_client():
        grouped = [entry for entry in grouped if entry["notes"] or entry["photos"]]
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


@app.context_processor
def inject_workspace_context():
    with get_db_connection() as conn:
        workspace_settings = load_workspace_settings(conn)

    notifications = build_notifications_for_user(g.user, workspace_settings) if g.user is not None else []
    return {
        "workspace_settings": workspace_settings,
        "notifications": notifications,
        "notification_count": len(notifications),
    }


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


@app.route("/brand/logo/<path:filename>")
def public_branding_file(filename):
    if not allowed_logo_file(filename):
        return "", 404
    return send_from_directory(BRANDING_UPLOAD_FOLDER, filename)


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
        metrics_where = f"WHERE {role_clause}" if role_clause else ""

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

        today = datetime.now().date()
        today_str = today.isoformat()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        date_scope_sql = f"WHERE {role_clause} AND " if role_clause else "WHERE "

        scheduled_this_week_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM jobs
            {date_scope_sql}jobs.status = 'Scheduled'
              AND COALESCE(jobs.due_date, SUBSTRING(jobs.created_at, 1, 10)) BETWEEN ? AND ?
            """,
            role_params + [week_start.isoformat(), week_end.isoformat()],
        ).fetchone()

        jobs_waiting_approval_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM jobs
            {date_scope_sql}jobs.status IN ('Estimating', 'Proposal Sent', 'Negotiation')
            """,
            role_params,
        ).fetchone()

        field_updates_today_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM updates
            JOIN jobs ON jobs.id = updates.job_id
            {date_scope_sql}SUBSTRING(updates.timestamp, 1, 10) = ?
            """,
            role_params + [today_str],
        ).fetchone()

        overdue_jobs_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM jobs
            {date_scope_sql}COALESCE(jobs.due_date, jobs.proposal_sent_date, jobs.decision_date) IS NOT NULL
              AND COALESCE(jobs.due_date, jobs.proposal_sent_date, jobs.decision_date) < ?
              AND jobs.status NOT IN ('Completed', 'Paid', 'Rejected')
            """,
            role_params + [today_str],
        ).fetchone()

        team_assigned_today_row = conn.execute(
            f"""
            SELECT COUNT(DISTINCT jobs.assigned_to) AS count
            FROM jobs
            {date_scope_sql}jobs.assigned_to IS NOT NULL
              AND jobs.status IN ('Scheduled', 'Started', 'In Progress')
              AND COALESCE(jobs.due_date, SUBSTRING(jobs.created_at, 1, 10)) = ?
            """,
            role_params + [today_str],
        ).fetchone()

    open_jobs = sum(
        1
        for row in jobs
        if row["status"] in {"Scheduled", "Started", "In Progress", "Approved", "Estimating", "Proposal Sent", "Negotiation"}
    )
    ops_metrics = {
        "open_jobs": open_jobs,
        "pending_estimates": pending_estimates,
        "scheduled_this_week": (scheduled_this_week_row["count"] if scheduled_this_week_row else 0) or 0,
        "jobs_waiting_approval": (jobs_waiting_approval_row["count"] if jobs_waiting_approval_row else 0) or 0,
        "field_updates_today": (field_updates_today_row["count"] if field_updates_today_row else 0) or 0,
        "overdue_jobs": (overdue_jobs_row["count"] if overdue_jobs_row else 0) or 0,
        "team_assigned_today": (team_assigned_today_row["count"] if team_assigned_today_row else 0) or 0,
    }

    can_view_financials_flag = dashboard_role == "admin"
    can_manage_jobs_flag = dashboard_role == "admin"

    latest_job_id = jobs[0]["id"] if jobs else None

    return render_template(
        "index.html",
        jobs=jobs,
        statuses=STATUSES,
        pre_construction_statuses=PRE_CONSTRUCTION_STATUSES,
        execution_statuses=EXECUTION_STATUSES,
        financial_statuses=FINANCIAL_STATUSES,
        status_counts=status_counts,
        can_view_financials=can_view_financials_flag,
        can_manage_jobs=can_manage_jobs_flag,
        dashboard_role=dashboard_role,
        show_view_switcher=is_admin(),
        filters={"q": search, "status": status_filter, "quick": quick_filter, "sort": sort, "view_as": dashboard_role},
        latest_job_id=latest_job_id,
        ops_metrics=ops_metrics,
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
            WHERE status = 'Approved' AND deleted_at IS NULL
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
    with get_db_connection() as conn:
        workspace_settings = load_workspace_settings(conn)
        users_summary = conn.execute(
            """
            SELECT
                COUNT(*) AS total_users,
                SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) AS admin_count,
                SUM(CASE WHEN role = 'employee' THEN 1 ELSE 0 END) AS employee_count,
                SUM(CASE WHEN role = 'client' THEN 1 ELSE 0 END) AS client_count
            FROM users
            """
        ).fetchone()
        recent_users = conn.execute(
            "SELECT name, email, role, created_at FROM users ORDER BY created_at DESC, id DESC LIMIT 5"
        ).fetchall()

    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip() or DEFAULT_WORKSPACE_SETTINGS["company_name"]
        company_city = request.form.get("company_city", "").strip() or DEFAULT_WORKSPACE_SETTINGS["company_city"]
        company_address = request.form.get("company_address", "").strip()
        company_state = request.form.get("company_state", "").strip() or DEFAULT_WORKSPACE_SETTINGS["company_state"]
        company_zip = request.form.get("company_zip", "").strip()
        company_phone = request.form.get("company_phone", "").strip()
        company_email = request.form.get("company_email", "").strip()
        theme = request.form.get("theme", "light").strip().lower()
        if theme not in {"light", "dark"}:
            theme = "light"

        dark_mode_default = parse_checkbox(request.form.get("dark_mode_default"))
        notify_new_lead = parse_checkbox(request.form.get("notify_new_lead"))
        notify_estimate_approved = parse_checkbox(request.form.get("notify_estimate_approved"))
        notify_payment_received = parse_checkbox(request.form.get("notify_payment_received"))
        notify_photo_upload = parse_checkbox(request.form.get("notify_photo_upload"))

        logo_path = workspace_settings.get("logo_path", "")
        logo_url = workspace_settings.get("logo_url", "")
        logo_file = request.files.get("logo")
        if logo_file and logo_file.filename:
            if not allowed_logo_file(logo_file.filename):
                flash("Logo must be a PNG, JPG, JPEG, or WEBP image.", "error")
                return render_template(
                    "settings.html",
                    workspace_settings={
                        **workspace_settings,
                        "company_name": company_name,
                        "company_city": company_city,
                        "company_address": company_address,
                        "company_state": company_state,
                        "company_zip": company_zip,
                        "company_phone": company_phone,
                        "company_email": company_email,
                        "theme": theme,
                        "dark_mode_default": dark_mode_default,
                        "notify_new_lead": notify_new_lead,
                        "notify_estimate_approved": notify_estimate_approved,
                        "notify_payment_received": notify_payment_received,
                        "notify_photo_upload": notify_photo_upload,
                    },
                    users_summary=users_summary,
                    recent_users=recent_users,
                )
            try:
                logo_path, logo_url = process_logo_upload(logo_file)
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template(
                    "settings.html",
                    workspace_settings={
                        **workspace_settings,
                        "company_name": company_name,
                        "company_city": company_city,
                        "company_address": company_address,
                        "company_state": company_state,
                        "company_zip": company_zip,
                        "company_phone": company_phone,
                        "company_email": company_email,
                        "theme": theme,
                        "logo_path": logo_path,
                        "logo_url": logo_url,
                        "dark_mode_default": dark_mode_default,
                        "notify_new_lead": notify_new_lead,
                        "notify_estimate_approved": notify_estimate_approved,
                        "notify_payment_received": notify_payment_received,
                        "notify_photo_upload": notify_photo_upload,
                    },
                    users_summary=users_summary,
                    recent_users=recent_users,
                )

        with get_db_connection() as conn:
            save_workspace_settings(
                conn,
                {
                    "company_name": company_name,
                    "company_city": company_city,
                    "company_address": company_address,
                    "company_state": company_state,
                    "company_zip": company_zip,
                    "company_phone": company_phone,
                    "company_email": company_email,
                    "theme": theme,
                    "logo_path": logo_path,
                    "logo_url": logo_url,
                    "dark_mode_default": dark_mode_default,
                    "notify_new_lead": notify_new_lead,
                    "notify_estimate_approved": notify_estimate_approved,
                    "notify_payment_received": notify_payment_received,
                    "notify_photo_upload": notify_photo_upload,
                },
            )
            workspace_settings = load_workspace_settings(conn)
            users_summary = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_users,
                    SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) AS admin_count,
                    SUM(CASE WHEN role = 'employee' THEN 1 ELSE 0 END) AS employee_count,
                    SUM(CASE WHEN role = 'client' THEN 1 ELSE 0 END) AS client_count
                FROM users
                """
            ).fetchone()
            recent_users = conn.execute(
                "SELECT name, email, role, created_at FROM users ORDER BY created_at DESC, id DESC LIMIT 5"
            ).fetchall()

        flash("Settings saved. Company preferences updated.", "success")
        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        workspace_settings=workspace_settings,
        users_summary=users_summary,
        recent_users=recent_users,
    )


@app.route("/add", methods=("GET", "POST"))
@login_required
@role_required("admin")
def add_job():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        client_name = request.form.get("client_name", "").strip()
        location = request.form.get("location", "").strip()
        due_date = request.form.get("due_date", "").strip() or None
        selected_service_types = sanitize_selected_services(request.form.getlist("service_type"), JOB_SERVICE_TYPES)
        service_type = compose_service_text(selected_service_types)
        other_service_details = request.form.get("other_service_details", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "Lead").strip()
        proposal_amount = parse_money(request.form.get("proposal_amount"))
        proposal_sent_date = parse_date(request.form.get("proposal_sent_date"))
        assigned_to = request.form.get("assigned_to", type=int)
        client_id = request.form.get("client_id", type=int)

        if status not in STATUSES:
            status = "Lead"
        if OTHER_SERVICE_LABEL not in selected_service_types:
            other_service_details = ""

        with get_db_connection() as conn:
            employees = conn.execute(
                "SELECT id, name, email FROM users WHERE role = 'employee' ORDER BY name"
            ).fetchall()
            clients = conn.execute(
                "SELECT id, name, email FROM users WHERE role = 'client' ORDER BY name"
            ).fetchall()

        if not name:
            flash("Job name is required to create a lead.", "error")
            return render_template(
                "add_job.html",
                name=name,
                client_name=client_name,
                location=location,
                due_date=due_date,
                selected_service_types=selected_service_types,
                other_service_details=other_service_details,
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

        location = location or "TBD"
        description = description or other_service_details or "No description provided."

        now = datetime.now().isoformat(timespec="seconds")
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    name, client_name, location, due_date, service_type, other_service_details, description, status,
                    proposal_amount, proposal_sent_date, payment_status,
                    assigned_to, client_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    client_name,
                    location,
                    due_date,
                    service_type,
                    other_service_details,
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
            job_row = conn.execute(
                "SELECT id FROM jobs WHERE created_at = ? AND name = ? ORDER BY id DESC LIMIT 1",
                (now, name),
            ).fetchone()
            if job_row:
                sync_job_tasks(conn, job_row["id"], selected_service_types)
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
        selected_service_types=[],
        due_date="",
        employees=employees,
        clients=clients,
    )


@app.route("/users", methods=("GET", "POST"))
@login_required
@role_required("admin")
def users():
    default_role = request.args.get("role", "").strip().lower()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()

        if not name or not email or not password or role not in ROLES:
            flash("Please enter a name, email, password, and valid role.", "error")
            return redirect(url_for("users"))

        try:
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO users (name, email, phone, password, role, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        email,
                        phone or None,
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
            "SELECT id, name, email, phone, role, created_at FROM users ORDER BY role, name"
        ).fetchall()
    return render_template("users.html", users=users_list, roles=ROLES, default_role=default_role)


@app.route("/jobs")
@login_required
def jobs():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    employee_filter = request.args.get("employee", "").strip()
    sort = request.args.get("sort", "priority").strip()
    where_clauses = []
    params = []
    visible_clause, visible_params = visible_jobs_where()
    if visible_clause:
        where_clauses.append(visible_clause)
        params.extend(visible_params)

    if status_filter in STATUSES:
        where_clauses.append("jobs.status = ?")
        params.append(status_filter)

    if is_admin() and employee_filter.isdigit():
        where_clauses.append("jobs.assigned_to = ?")
        params.append(int(employee_filter))
    elif not is_admin():
        employee_filter = ""

    if search:
        where_clauses.append(
            "(jobs.name LIKE ? OR jobs.client_name LIKE ? OR jobs.location LIKE ? OR jobs.service_type LIKE ? OR employee.name LIKE ? OR client.name LIKE ? OR client.email LIKE ? OR employee.email LIKE ?)"
        )
        like_search = f"%{search}%"
        params.extend([like_search] * 8)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    order_by = {
        "oldest": "jobs.created_at ASC",
        "status": "jobs.status ASC, jobs.created_at DESC",
        "employee": "COALESCE(employee.name, jobs.client_name, jobs.name) ASC, jobs.created_at DESC",
        "due": "COALESCE(jobs.due_date, jobs.decision_date, jobs.proposal_sent_date) ASC NULLS LAST, jobs.created_at DESC",
    }.get(
        sort,
        "CASE jobs.status WHEN 'Lead' THEN 1 WHEN 'Estimating' THEN 2 WHEN 'Proposal Sent' THEN 3 WHEN 'Negotiation' THEN 4 WHEN 'Approved' THEN 5 WHEN 'Scheduled' THEN 6 WHEN 'Started' THEN 7 WHEN 'In Progress' THEN 8 WHEN 'Completed' THEN 9 WHEN 'Invoiced' THEN 10 WHEN 'Paid' THEN 11 ELSE 99 END, jobs.created_at DESC",
    )

    today = datetime.now().date().isoformat()
    with get_db_connection() as conn:
        jobs_list = conn.execute(
            f"""
            SELECT
                jobs.*,
                employee.name AS assigned_employee_name,
                employee.email AS assigned_employee_email,
                client.name AS client_user_name,
                client.email AS client_user_email,
                COALESCE(jobs.due_date, jobs.decision_date, jobs.proposal_sent_date) AS effective_due_date,
                CASE
                    WHEN COALESCE(jobs.due_date, jobs.decision_date, jobs.proposal_sent_date) IS NOT NULL
                         AND COALESCE(jobs.due_date, jobs.decision_date, jobs.proposal_sent_date) < ?
                         AND jobs.status NOT IN ('Completed', 'Paid')
                    THEN 1 ELSE 0
                END AS is_overdue,
                CASE jobs.status
                    WHEN 'Lead' THEN 12
                    WHEN 'Estimating' THEN 22
                    WHEN 'Proposal Sent' THEN 34
                    WHEN 'Negotiation' THEN 42
                    WHEN 'Approved' THEN 54
                    WHEN 'Scheduled' THEN 68
                    WHEN 'Started' THEN 74
                    WHEN 'In Progress' THEN 84
                    WHEN 'Completed' THEN 94
                    WHEN 'Invoiced' THEN 98
                    WHEN 'Paid' THEN 100
                    ELSE 40
                END AS progress_percent
            FROM jobs
            LEFT JOIN users employee ON employee.id = jobs.assigned_to
            LEFT JOIN users client ON client.id = jobs.client_id
            {where_sql}
            ORDER BY {order_by}
            """,
            [today] + params,
        ).fetchall()
        employees = []
        if is_admin():
            employees = conn.execute(
                "SELECT id, name, email FROM users WHERE role = 'employee' ORDER BY name"
            ).fetchall()

    active_jobs = sum(1 for row in jobs_list if row["status"] in {"Scheduled", "Started", "In Progress"})
    scheduled_jobs = sum(1 for row in jobs_list if row["status"] == "Scheduled")
    in_progress_jobs = sum(1 for row in jobs_list if row["status"] == "In Progress")
    completed_jobs = sum(1 for row in jobs_list if row["status"] in {"Completed", "Paid"})
    overdue_jobs = sum(1 for row in jobs_list if row["is_overdue"])

    return render_template(
        "jobs.html",
        jobs=jobs_list,
        employees=employees,
        filters={"q": search, "status": status_filter, "employee": employee_filter, "sort": sort},
        status_options=STATUSES,
        active_jobs=active_jobs,
        scheduled_jobs=scheduled_jobs,
        in_progress_jobs=in_progress_jobs,
        completed_jobs=completed_jobs,
        overdue_jobs=overdue_jobs,
        can_manage_jobs=can_manage_jobs(),
        money=money,
    )


@app.route("/clients")
@login_required
@role_required("admin")
def clients():
    with get_db_connection() as conn:
        client_rows = conn.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                users.phone,
                COUNT(DISTINCT jobs.id) AS total_projects,
                COUNT(DISTINCT CASE WHEN jobs.status IN ('Completed', 'Paid') THEN jobs.id END) AS completed_projects,
                COUNT(DISTINCT CASE WHEN jobs.status IN ('Scheduled', 'Started', 'In Progress') THEN jobs.id END) AS active_projects,
                MAX(jobs.created_at) AS last_job_date,
                COALESCE(SUM(CASE WHEN jobs.payment_status = 'Paid' THEN COALESCE(jobs.invoice_amount, 0) ELSE 0 END), 0) AS total_spent,
                COALESCE(SUM(CASE WHEN jobs.payment_status != 'Paid' AND COALESCE(jobs.invoice_amount, 0) > 0 THEN COALESCE(jobs.invoice_amount, 0) ELSE 0 END), 0) AS outstanding_balance
            FROM users
            LEFT JOIN jobs ON jobs.client_id = users.id
            WHERE users.role = 'client'
            GROUP BY users.id
            ORDER BY users.name
            """
        ).fetchall()

    total_clients = len(client_rows)
    active_clients = sum(1 for row in client_rows if row["total_projects"])
    repeat_clients = sum(1 for row in client_rows if (row["total_projects"] or 0) > 1)
    outstanding_balance = sum(row["outstanding_balance"] or 0 for row in client_rows)
    total_spent = sum(row["total_spent"] or 0 for row in client_rows)

    return render_template(
        "clients.html",
        clients=client_rows,
        total_clients=total_clients,
        active_clients=active_clients,
        repeat_clients=repeat_clients,
        outstanding_balance=outstanding_balance,
        total_spent=total_spent,
        money=money,
    )


@app.route("/employees")
@login_required
@role_required("admin")
def employees():
    today_prefix = datetime.now().date().isoformat() + "%"
    with get_db_connection() as conn:
        employee_rows = conn.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                users.phone,
                COUNT(DISTINCT jobs.id) AS assigned_jobs,
                COUNT(DISTINCT CASE WHEN jobs.status IN ('Scheduled', 'Started', 'In Progress') THEN jobs.id END) AS active_jobs,
                COUNT(DISTINCT CASE WHEN jobs.created_at LIKE ? THEN jobs.id END) AS active_today_jobs,
                MAX(jobs.created_at) AS last_assigned_job
            FROM users
            LEFT JOIN jobs ON jobs.assigned_to = users.id
            WHERE users.role = 'employee'
            GROUP BY users.id
            ORDER BY users.name
            """,
            (today_prefix,),
        ).fetchall()

    total_employees = len(employee_rows)
    active_today = sum(1 for row in employee_rows if row["active_today_jobs"])
    field_crew = sum(1 for row in employee_rows if row["assigned_jobs"])
    office_staff = max(total_employees - field_crew, 0)

    employee_cards = []
    for row in employee_rows:
        active_jobs = row["active_jobs"] or 0
        assigned_jobs = row["assigned_jobs"] or 0
        if active_jobs:
            status = "Busy"
        elif assigned_jobs:
            status = "Available"
        else:
            status = "Off Duty"
        employee_cards.append({**row, "status": status})

    return render_template(
        "employees.html",
        employees=employee_cards,
        total_employees=total_employees,
        active_today=active_today,
        field_crew=field_crew,
        office_staff=office_staff,
    )


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
        tasks = fetch_job_tasks(conn, job_id)
        if not tasks and job.get("service_type"):
            sync_job_tasks(conn, job_id, split_services(job.get("service_type")))
            tasks = fetch_job_tasks(conn, job_id)
    updates = group_updates(update_rows)

    return render_template(
        "update_job.html",
        job=job,
        selected_service_types=split_services(job.get("service_type")),
        updates=updates,
        statuses=STATUSES,
        service_types=JOB_SERVICE_TYPES,
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
        tasks=tasks,
        task_statuses=TASK_STATUSES,
        task_summary=task_progress_summary(tasks),
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
        photo_count_sql = (
            "SUM(CASE WHEN image_path IS NOT NULL AND client_visible THEN 1 ELSE 0 END) AS photo_count"
            if is_client()
            else "SUM(CASE WHEN image_path IS NOT NULL THEN 1 ELSE 0 END) AS photo_count"
        )
        progress = conn.execute(
            f"""
            SELECT
                COUNT(DISTINCT COALESCE(update_group, timestamp || '|' || COALESCE(notes, ''))) AS update_count,
                {photo_count_sql},
                MIN(timestamp) AS first_update,
                MAX(timestamp) AS last_update
            FROM updates
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
        tasks = fetch_job_tasks(conn, job_id)
        if not tasks and job.get("service_type"):
            sync_job_tasks(conn, job_id, split_services(job.get("service_type")))
            tasks = fetch_job_tasks(conn, job_id)
    updates = group_updates(update_rows)

    return render_template(
        "job_progress.html",
        job=job,
        updates=updates,
        progress=progress,
        can_view_financials=can_view_financials(),
        can_manage_receipts=can_manage_receipts(),
        can_manage_jobs=can_manage_jobs(),
        tasks=tasks,
        task_summary=task_progress_summary(tasks),
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
    photos_client_visible = is_admin() and parse_checkbox(request.form.get("photos_client_visible"))
    assigned_to = request.form.get("assigned_to", type=int)
    client_id = request.form.get("client_id", type=int)
    selected_service_types = sanitize_selected_services(request.form.getlist("service_type"), JOB_SERVICE_TYPES)
    service_type = compose_service_text(selected_service_types)
    other_service_details = request.form.get("other_service_details", "").strip()
    due_date = request.form.get("due_date", "").strip() or None
    task_status_updates = {}
    if is_admin():
        for key, value in request.form.items():
            if not key.startswith("task_status_"):
                continue
            task_id_text = key.removeprefix("task_status_")
            if task_id_text.isdigit() and value in TASK_STATUSES:
                task_status_updates[int(task_id_text)] = value

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
        service_type = job["service_type"] or ""
        other_service_details = job["other_service_details"] or ""
        due_date = job["due_date"] or None
    else:
        if OTHER_SERVICE_LABEL not in selected_service_types:
            other_service_details = ""

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
    task_fields_changed = False
    if task_status_updates:
        with get_db_connection() as conn:
            current_task_rows = conn.execute(
                "SELECT id, status FROM job_tasks WHERE job_id = ?",
                (job_id,),
            ).fetchall()
        current_task_statuses = {row["id"]: row["status"] for row in current_task_rows}
        task_fields_changed = any(
            current_task_statuses.get(task_id) != task_status
            for task_id, task_status in task_status_updates.items()
        )
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
            service_type != (job["service_type"] or ""),
            other_service_details != (job["other_service_details"] or ""),
            due_date != (job["due_date"] or None),
        ]
    )
    if not notes and not valid_files and not valid_receipt_files and not job_fields_changed and not task_fields_changed:
        flash("Add notes, photos, or change the status before submitting.", "error")
        return redirect(url_for("update_job", job_id=job_id))

    now = datetime.now().isoformat(timespec="seconds")
    update_group = uuid.uuid4().hex
    saved_photos = []
    saved_receipts = []

    try:
        for file in valid_files:
            if not allowed_file(file.filename):
                flash(f"Skipped unsupported file: {file.filename}", "error")
                continue

            saved_photos.append(
                save_upload_to_storage(
                    file,
                    "job_photos",
                    "job_photo",
                    job_id=job_id,
                    compress_images=True,
                )
            )

        for file in valid_receipt_files:
            if not allowed_receipt_file(file.filename):
                flash(f"Skipped unsupported receipt/bill: {file.filename}", "error")
                continue

            saved_receipts.append(
                save_upload_to_storage(
                    file,
                    "receipts",
                    "receipt",
                    job_id=job_id,
                    compress_images=True,
                )
            )

        if not saved_photos and not saved_receipts and not notes and not job_fields_changed and not task_fields_changed:
            flash("No update was saved. Please add notes, change status, or upload supported files.", "error")
            return redirect(url_for("update_job", job_id=job_id))

        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    client_name = ?,
                    due_date = ?,
                    service_type = ?,
                    other_service_details = ?,
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
                    due_date,
                    service_type,
                    other_service_details,
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

            if saved_photos:
                for photo in saved_photos:
                    conn.execute(
                        """
                        INSERT INTO updates (job_id, notes, image_path, photo_url, receipt_path, receipt_url, client_visible, update_group, user_id, author_role, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (job_id, notes, photo["path"], photo["url"], None, None, photos_client_visible, update_group, g.user["id"], g.user["role"], now),
                    )

            if saved_receipts:
                for receipt in saved_receipts:
                    conn.execute(
                        """
                        INSERT INTO updates (job_id, notes, image_path, photo_url, receipt_path, receipt_url, client_visible, update_group, user_id, author_role, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (job_id, notes, None, None, receipt["path"], receipt["url"], False, update_group, g.user["id"], g.user["role"], now),
                    )

            if not saved_photos and not saved_receipts and (notes or job_fields_changed or task_fields_changed):
                conn.execute(
                    """
                    INSERT INTO updates (job_id, notes, image_path, photo_url, receipt_path, receipt_url, client_visible, update_group, user_id, author_role, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (job_id, notes, None, None, None, None, False, update_group, g.user["id"], g.user["role"], now),
                )

            if is_admin():
                sync_job_tasks(conn, job_id, selected_service_types)
                for task_id, task_status in task_status_updates.items():
                    conn.execute(
                        """
                        UPDATE job_tasks
                        SET status = ?, updated_at = ?
                        WHERE id = ? AND job_id = ?
                        """,
                        (task_status, now, task_id, job_id),
                    )

    except (OSError, RuntimeError, ValueError) as exc:
        app.logger.exception("Failed to save job update")
        flash(f"Upload failed: {exc}", "error")
        return redirect(url_for("update_job", job_id=job_id))

    flash("Upload complete. Job update saved.", "success")
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
            INSERT INTO updates (job_id, notes, image_path, receipt_path, client_visible, update_group, user_id, author_role, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, comment, None, None, False, uuid.uuid4().hex, g.user["id"], g.user["role"], now),
        )
    flash("Comment added.", "success")
    return redirect(url_for("update_job", job_id=job_id))


@app.route("/photo/<int:update_id>/visibility", methods=("POST",))
@login_required
@role_required("admin")
def update_photo_visibility(update_id):
    client_visible = parse_checkbox(request.form.get("client_visible"))
    next_url = request.form.get("next") or ""
    with get_db_connection() as conn:
        photo = conn.execute(
            "SELECT job_id FROM updates WHERE id = ? AND image_path IS NOT NULL",
            (update_id,),
        ).fetchone()
        if photo is None:
            flash("Photo not found.", "error")
            return redirect(url_for("index"))
        conn.execute(
            """
            UPDATE updates
            SET client_visible = ?
            WHERE id = ? AND image_path IS NOT NULL
            """,
            (client_visible, update_id),
        )

    flash("Photo visibility updated.", "success")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("update_job", job_id=photo["job_id"]))


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
            SELECT updates.job_id, updates.image_path, updates.receipt_path, updates.client_visible, jobs.assigned_to, jobs.client_id
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

    if is_client() and update["image_path"] == stored_path and not normalize_bool(update["client_visible"]):
        flash("That photo has not been shared with your client portal.", "error")
        return redirect(url_for("index"))

    fake_job = {
        "assigned_to": update["assigned_to"],
        "client_id": update["client_id"],
    }
    if not can_view_job(fake_job):
        flash("You do not have permission to view that file.", "error")
        return redirect(url_for("index"))

    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.cli.command("migrate-local-uploads")
def migrate_local_uploads_command():
    """Upload existing local files to Supabase Storage and save public URLs."""
    if not supabase_storage_configured():
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_KEY before running this migration.")

    ensure_storage_buckets()
    migrated = 0
    skipped = 0

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, job_id, image_path, photo_url, receipt_path, receipt_url
            FROM updates
            WHERE (image_path IS NOT NULL AND (photo_url IS NULL OR photo_url = ''))
               OR (receipt_path IS NOT NULL AND (receipt_url IS NULL OR receipt_url = ''))
            ORDER BY id ASC
            """
        ).fetchall()

        for row in rows:
            if row["image_path"] and not row["photo_url"] and not is_public_url(row["image_path"]):
                local_name = row["image_path"].replace("uploads/", "", 1)
                local_path = UPLOAD_FOLDER / local_name
                if local_path.exists():
                    uploaded = upload_local_file_to_storage(local_path, "job_photos", "job_photo", job_id=row["job_id"])
                    conn.execute(
                        "UPDATE updates SET image_path = ?, photo_url = ? WHERE id = ?",
                        (uploaded["path"], uploaded["url"], row["id"]),
                    )
                    migrated += 1
                else:
                    skipped += 1

            if row["receipt_path"] and not row["receipt_url"] and not is_public_url(row["receipt_path"]):
                local_name = row["receipt_path"].replace("uploads/", "", 1)
                local_path = UPLOAD_FOLDER / local_name
                if local_path.exists():
                    uploaded = upload_local_file_to_storage(local_path, "receipts", "receipt", job_id=row["job_id"])
                    conn.execute(
                        "UPDATE updates SET receipt_path = ?, receipt_url = ? WHERE id = ?",
                        (uploaded["path"], uploaded["url"], row["id"]),
                    )
                    migrated += 1
                else:
                    skipped += 1

        settings_row = conn.execute("SELECT logo_path, logo_url FROM workspace_settings WHERE id = 1").fetchone()
        if settings_row and settings_row["logo_path"] and not settings_row["logo_url"] and not is_public_url(settings_row["logo_path"]):
            logo_candidates = []
            if settings_row["logo_path"].startswith("static/"):
                logo_candidates.append(BASE_DIR / settings_row["logo_path"])
            if settings_row["logo_path"].startswith("uploads/branding/"):
                logo_candidates.append(STATIC_UPLOAD_FOLDER / settings_row["logo_path"].replace("uploads/", "", 1))
            logo_candidates.extend([PUBLIC_LOGO_FILE, STATIC_UPLOAD_FOLDER / "branding" / "Logo.png"])
            for logo_path in logo_candidates:
                if logo_path.exists():
                    uploaded = upload_local_file_to_storage(logo_path, "logos", "logo")
                    conn.execute(
                        "UPDATE workspace_settings SET logo_path = ?, logo_url = ? WHERE id = 1",
                        (uploaded["path"], uploaded["url"]),
                    )
                    migrated += 1
                    break

    print(f"Migration complete. Uploaded {migrated} file(s). Skipped {skipped} missing local file(s).")


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
    
    where_clauses.insert(0, "e.deleted_at IS NULL")
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    status_where_sql = where_sql.replace("e.", "")
    order_by = "created_at DESC"
    if sort == "oldest":
        order_by = "created_at ASC"
    elif sort == "name":
        order_by = "client_name ASC"
    elif sort == "value":
        order_by = "total DESC"
    
    with get_db_connection() as conn:
        estimate_rows = conn.execute(
            f"""
            SELECT e.*, u.name as created_by_name
            FROM estimates e
            LEFT JOIN users u ON u.id = e.created_by
            {where_sql}
            ORDER BY {order_by}
            """,
            params,
        ).fetchall()
        estimate_list = []
        for row in estimate_rows:
            record = dict(row)
            record["service_chips"] = build_service_chips(row["service_type"], row.get("other_service_details"))
            estimate_list.append(record)
        
        status_counts = {
            row["status"]: row["count"]
            for row in conn.execute(
                f"""
                SELECT status, COUNT(*) AS count
                FROM estimates
                {status_where_sql}
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
            WHERE deleted_at IS NULL
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
        selected_service_types = sanitize_selected_services(request.form.getlist("service_type"), SERVICE_TYPES)
        service_type = compose_service_text(selected_service_types)
        other_service_details = request.form.get("other_service_details", "").strip()
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
                selected_service_types=selected_service_types,
                other_service_details=other_service_details,
                project_description=project_description,
                notes=notes,
            )
        if OTHER_SERVICE_LABEL in selected_service_types and not other_service_details:
            flash("Please provide custom service details when Other is selected.", "error")
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
                selected_service_types=selected_service_types,
                other_service_details=other_service_details,
                project_description=project_description,
                notes=notes,
            )
        if OTHER_SERVICE_LABEL not in selected_service_types:
            other_service_details = ""
        
        now = datetime.now().isoformat(timespec="seconds")
        with get_db_connection() as conn:
            estimate_number = generate_estimate_number(conn)
            conn.execute(
                """
                INSERT INTO estimates (
                    estimate_number, client_name, company_name, phone, email,
                    address, city, state, zip, service_type, other_service_details, project_description,
                    status, notes, created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    other_service_details,
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
        selected_service_types=[],
        other_service_details="",
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
    service_chips = build_service_chips(estimate["service_type"], estimate.get("other_service_details"))
    
    return render_template(
        "view_estimate.html",
        estimate=estimate,
        service_chips=service_chips,
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
    selected_service_types_for_form = split_services(estimate.get("service_type"))
    
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
        selected_service_types = sanitize_selected_services(request.form.getlist("service_type"), SERVICE_TYPES)
        service_type = compose_service_text(selected_service_types)
        other_service_details = request.form.get("other_service_details", "").strip()
        project_description = request.form.get("project_description", "").strip()
        notes = request.form.get("notes", "").strip()
        
        if not client_name:
            flash("Client name is required.", "error")
        elif not service_type:
            flash("Please choose at least one service type.", "error")
        elif OTHER_SERVICE_LABEL in selected_service_types and not other_service_details:
            flash("Please provide custom service details when Other is selected.", "error")
        else:
            if OTHER_SERVICE_LABEL not in selected_service_types:
                other_service_details = ""
            now = datetime.now().isoformat(timespec="seconds")
            with get_db_connection() as conn:
                conn.execute(
                    """
                    UPDATE estimates
                    SET client_name = ?, company_name = ?, phone = ?, email = ?,
                        address = ?, city = ?, state = ?, zip = ?,
                        service_type = ?, other_service_details = ?, project_description = ?, notes = ?, updated_at = ?
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
                        service_type,
                        other_service_details,
                        project_description,
                        notes,
                        now,
                        estimate_id,
                    ),
                )
            flash("Estimate updated.", "success")
            return redirect(url_for("view_estimate", estimate_id=estimate_id))

        selected_service_types_for_form = selected_service_types
        estimate = {
            **dict(estimate),
            "client_name": client_name,
            "company_name": company_name,
            "phone": phone,
            "email": email,
            "address": address,
            "city": city,
            "state": state,
            "zip": zip_code,
            "service_type": service_type,
            "other_service_details": other_service_details,
            "project_description": project_description,
            "notes": notes,
        }
    
    with get_db_connection() as conn:
        items = get_estimate_items(conn, estimate_id)
    
    totals = calculate_estimate_totals(items)
    
    return render_template(
        "edit_estimate.html",
        estimate=estimate,
        selected_service_types=selected_service_types_for_form,
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
                name, client_name, location, service_type, other_service_details, description, status,
                proposal_amount, proposal_sent_date, payment_status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_name,
                estimate["client_name"],
                estimate["address"] or "See estimate",
                estimate["service_type"],
                estimate["other_service_details"],
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
                address, city, state, zip, service_type, other_service_details, project_description,
                status, notes, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                estimate["other_service_details"],
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


@app.route("/estimate/<int:estimate_id>/delete", methods=("POST",))
@login_required
@role_required("admin")
def delete_estimate(estimate_id):
    estimate = get_estimate_or_404(estimate_id)
    if estimate is None:
        return redirect(url_for("estimates"))

    now = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE estimates
            SET deleted_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, estimate_id),
        )

    flash("Estimate moved to archive.", "success")
    return redirect(url_for("estimates"))



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
