"""Database access layer: connections, queries, audit logging, error messages."""
import datetime as dt
import os
import re
import sqlite3
from contextlib import contextmanager

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("LAB_DB_PATH", os.path.join(BASE_DIR, "data", "smart_lab.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema_sqlite.sql")


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction():
    """Yield a connection; commit on success, roll back on any exception."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_df(sql, params=()):
    conn = get_conn()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def query_all(sql, params=(), conn=None):
    own = conn is None
    conn = conn or get_conn()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        if own:
            conn.close()


def query_one(sql, params=(), conn=None):
    rows = query_all(sql, params, conn)
    return rows[0] if rows else None


def scalar(sql, params=(), conn=None):
    row = query_one(sql, params, conn)
    return list(row.values())[0] if row else None


def schema_exists() -> bool:
    if not os.path.exists(DB_PATH):
        return False
    return scalar("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='LAB_USER'") == 1


def create_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        ddl = f.read()
    conn = get_conn()
    try:
        conn.executescript(ddl)
    finally:
        conn.close()


def _ddl_block(ddl, pattern):
    m = re.search(pattern, ddl, re.S)
    if not m:
        raise RuntimeError(f"Schema statement not found: {pattern}")
    return m.group(0)


def migrate():
    """Bring an existing database up to the current schema_sqlite.sql. Returns a list of applied steps."""
    applied = []
    if scalar("SELECT COUNT(*) FROM sqlite_master WHERE name = 'MEDICAL_EQUIPMENT'"):
        return applied
    # Adding MEDICAL changes EQUIPMENT's CHECK constraint, which SQLite can only do by rebuilding the table
    # (create new -> copy -> drop old -> rename), done with FK enforcement off and verified afterwards.
    import shutil

    backup = DB_PATH.replace(".db", f".backup-{dt.datetime.now():%Y%m%d-%H%M%S}.db")
    shutil.copy2(DB_PATH, backup)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        ddl = f.read()
    equipment = _ddl_block(ddl, r"CREATE TABLE EQUIPMENT \(.*?\n\);").replace(
        "CREATE TABLE EQUIPMENT (", "CREATE TABLE EQUIPMENT_NEW (", 1)
    medical = _ddl_block(ddl, r"CREATE TABLE MEDICAL_EQUIPMENT \(.*?\n\);")
    trigger = _ddl_block(ddl, r"CREATE TRIGGER trg_medical_disjoint .*?END;")
    views = re.findall(r"CREATE VIEW .*?;", ddl, re.S)

    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("PRAGMA legacy_alter_table = ON")  # don't rewrite references in other tables
        conn.execute("BEGIN")
        old_seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'EQUIPMENT'").fetchone()
        for name in re.findall(r"CREATE VIEW (\w+)", ddl):
            conn.execute(f"DROP VIEW IF EXISTS {name}")
        conn.execute(equipment)
        conn.execute("INSERT INTO EQUIPMENT_NEW SELECT * FROM EQUIPMENT")
        conn.execute("DROP TABLE EQUIPMENT")
        conn.execute("ALTER TABLE EQUIPMENT_NEW RENAME TO EQUIPMENT")
        if old_seq:  # keep AUTOINCREMENT from reusing IDs of previously deleted equipment
            conn.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'EQUIPMENT'", (old_seq[0],))
        conn.execute(medical)
        conn.execute(trigger)
        for view in views:
            conn.execute(view)
        problems = conn.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise RuntimeError(f"Foreign key check failed after migration: {problems[:5]}")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    applied.append(f"Added MEDICAL equipment type (backup: {os.path.basename(backup)})")
    return applied


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
def now_str():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return dt.date.today()


def today_str():
    return dt.date.today().isoformat()


def to_date(value):
    """Parse an ISO date string (or date) into a date; None if empty."""
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
def client_ip():
    """Best-effort client IP; falls back to a placeholder."""
    try:
        import streamlit as st

        return st.context.ip_address or "127.0.0.1"
    except Exception:
        return "127.0.0.1"


def current_user_id():
    try:
        import streamlit as st

        user = st.session_state.get("user")
        return user["User_ID"] if user else None
    except Exception:
        return None


def log_action(action, remarks="", user_id=None, maintenance_id=None, conn=None):
    """Write one AUDIT_LOG row. Pass `conn` to make it part of the caller's transaction."""
    if user_id is None:
        user_id = current_user_id()
    sql = ("INSERT INTO AUDIT_LOG (Action_Performed, Date_Time, IP_Address, Remarks, User_ID, Maintenance_ID) "
           "VALUES (?, ?, ?, ?, ?, ?)")
    params = (action, now_str(), client_ip(), (remarks or "")[:500], user_id, maintenance_id)
    if conn is not None:
        conn.execute(sql, params)
    else:
        with transaction() as c:
            c.execute(sql, params)


def notify(conn, user_id, ntype, message):
    """Insert a notification unless the user already has the identical message."""
    exists = conn.execute(
        "SELECT 1 FROM NOTIFICATION WHERE User_ID = ? AND Message = ?", (user_id, message)
    ).fetchone()
    if exists:
        return False
    conn.execute(
        "INSERT INTO NOTIFICATION (User_ID, Notification_Type, Message, Date_Time, Status) "
        "VALUES (?, ?, ?, ?, 'UNREAD')",
        (user_id, ntype, message, now_str()),
    )
    return True


# ---------------------------------------------------------------------------
# Friendly error messages
# ---------------------------------------------------------------------------
CHECK_MESSAGES = {
    "chk_department_status": "Department status must be ACTIVE or INACTIVE.",
    "chk_lab_capacity": "Laboratory capacity must be greater than 0.",
    "chk_role_access": "Access level must be between 1 and 5.",
    "chk_role_status": "Role status must be ACTIVE or INACTIVE.",
    "chk_manager_experience": "Experience cannot be negative.",
    "chk_category_status": "Category status must be ACTIVE or INACTIVE.",
    "chk_equipment_status": "Invalid equipment status.",
    "chk_equipment_type": "Invalid equipment type.",
    "chk_computing_ram": "RAM must be greater than 0.",
    "chk_consumable_qty": "Quantity cannot be negative.",
    "chk_consumable_reorder": "Reorder level cannot be negative.",
    "chk_booking_status": "Invalid booking status.",
    "chk_calibration_due": "Next due date must be after the calibration date.",
    "chk_calibration_status": "Invalid calibration status.",
    "chk_transfer_labs": "From-lab and To-lab must be different.",
    "chk_transfer_status": "Invalid transfer status.",
    "chk_maintenance_type": "Maintenance type must be Preventive, Repair or Inspection.",
    "chk_maintenance_cost": "Cost cannot be negative.",
    "chk_maintenance_status": "Invalid maintenance status.",
    "chk_warranty_dates": "Warranty end date must be on or after the start date.",
    "chk_warranty_status": "Warranty status must be ACTIVE or EXPIRED.",
    "chk_notification_status": "Notification status must be UNREAD or READ.",
}


def friendly_error(exc: Exception) -> str:
    msg = str(exc)
    m = re.search(r"UNIQUE constraint failed: (\w+)\.(\w+)", msg)
    if m:
        return f"A {m.group(1).replace('_', ' ').title()} with this {m.group(2).replace('_', ' ')} already exists."
    m = re.search(r"CHECK constraint failed: (\w+)", msg)
    if m:
        return CHECK_MESSAGES.get(m.group(1), f"Value rejected by rule '{m.group(1)}'.")
    m = re.search(r"NOT NULL constraint failed: (\w+)\.(\w+)", msg)
    if m:
        return f"{m.group(2).replace('_', ' ')} is required."
    if "FOREIGN KEY constraint failed" in msg:
        return ("This record is linked to other records (foreign key). Remove or reassign the dependent "
                "records first — for equipment, consider setting the status to RETIRED to keep its history.")
    return msg
