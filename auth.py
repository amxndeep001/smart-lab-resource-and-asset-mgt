"""Login, password hashing and simple role-based access."""
import bcrypt
import streamlit as st

from db import log_action, now_str, query_one, transaction

# Access levels (ROLE.Access_Level)
LEVEL_ADMIN = 5     # users, roles, organisation, audit log
LEVEL_MANAGER = 3   # create / edit / delete asset records
# levels 1-2: read-only on assets; may book equipment for themselves

USER_SUBTYPE_TABLES = ["ADMINISTRATOR", "LAB_MANAGER", "LAB_TECHNICIAN", "RESEARCHER", "FACULTY"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def user_subtypes(user_id, conn=None):
    found = []
    for table in USER_SUBTYPE_TABLES:
        if query_one(f"SELECT 1 AS x FROM {table} WHERE User_ID = ?", (user_id,), conn):
            found.append(table)
    return found


def load_user(user_id, conn=None):
    user = query_one(
        "SELECT u.User_ID, u.Full_Name, u.Email, u.Department_ID, u.Role_ID, r.Role_Name, "
        "       COALESCE(r.Access_Level, 1) AS Access_Level, d.Department_Name "
        "FROM LAB_USER u JOIN ROLE r ON r.Role_ID = u.Role_ID "
        "JOIN DEPARTMENT d ON d.Department_ID = u.Department_ID WHERE u.User_ID = ?",
        (user_id,), conn)
    if user:
        user["Subtypes"] = user_subtypes(user_id, conn)
    return user


def attempt_login(email: str, password: str):
    """Return the user dict on success, None otherwise. Every attempt is audited."""
    row = query_one("SELECT u.User_ID, u.Password_Hash, r.Status AS Role_Status FROM LAB_USER u "
                    "JOIN ROLE r ON r.Role_ID = u.Role_ID WHERE lower(u.Email) = lower(?)", (email.strip(),))
    if not row or not check_password(password, row["Password_Hash"]):
        log_action("LOGIN_FAILED", f"Failed login for '{email.strip()}'",
                   user_id=row["User_ID"] if row else None)
        return None
    if row["Role_Status"] == "INACTIVE":
        log_action("LOGIN_FAILED", "Role is inactive", user_id=row["User_ID"])
        return None
    candidate = load_user(row["User_ID"])
    # Only administrators may sign in to this console.
    if candidate["Access_Level"] < LEVEL_ADMIN and "ADMINISTRATOR" not in candidate["Subtypes"]:
        log_action("LOGIN_DENIED", "Not an administrator account", user_id=row["User_ID"])
        return None
    with transaction() as conn:
        conn.execute("UPDATE ADMINISTRATOR SET Last_Login = ? WHERE User_ID = ?", (now_str(), row["User_ID"]))
        log_action("LOGIN", "User signed in", user_id=row["User_ID"], conn=conn)
    return load_user(row["User_ID"])


def logout():
    user = st.session_state.get("user")
    if user:
        log_action("LOGOUT", "User signed out", user_id=user["User_ID"])
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def current_user():
    return st.session_state.get("user")


def access_level():
    user = current_user()
    return user["Access_Level"] if user else 0


def is_admin():
    user = current_user()
    return bool(user) and (user["Access_Level"] >= LEVEL_ADMIN or "ADMINISTRATOR" in user["Subtypes"])


def can_manage():
    return is_admin() or access_level() >= LEVEL_MANAGER
