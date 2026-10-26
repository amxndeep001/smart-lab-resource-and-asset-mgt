"""Smart Laboratory Resource and Asset Management System — Streamlit entry point.

Run with:  streamlit run app.py
"""
import base64
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Smart Lab Asset Manager", page_icon="🧪", layout="wide")

import alerts  # noqa: E402
from auth import attempt_login, can_manage, current_user, is_admin, logout  # noqa: E402
from db import scalar  # noqa: E402
from seed import ensure_database  # noqa: E402
from views import activity, bookings, dashboard, equipment, master, operations, users  # noqa: E402


@st.cache_resource
def _bootstrap():
    """Create and seed the SQLite database on first run."""
    return ensure_database()


HERO_SVG = Path(__file__).parent / "assets" / "lab_hero.svg"

LOGIN_CSS = """
<style>
.stApp { background: linear-gradient(135deg, #eaf2fd 0%, #f6f8fc 48%, #e6f6ef 100%); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 3.5rem; max-width: 1180px; }
.hero-chip { display: inline-block; padding: 4px 12px; border-radius: 999px; background: #ffffff;
             color: #1c5cab; font-size: 0.8rem; font-weight: 600; letter-spacing: .02em;
             box-shadow: 0 2px 8px rgba(13, 54, 107, .08); }
.hero-title { font-size: 2.35rem; line-height: 1.15; font-weight: 800; color: #0d366b; margin: 14px 0 8px; }
.hero-title span { color: #2a78d6; }
.hero-sub { color: #52514e; font-size: 1.02rem; max-width: 520px; margin-bottom: 4px; }
.hero-img { width: 100%; max-width: 560px; display: block; margin: 6px 0 4px; }
.hero-features { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.hero-features div { background: rgba(255, 255, 255, .8); border: 1px solid #dbe7f7; border-radius: 10px;
                     padding: 6px 12px; font-size: .86rem; color: #184f95; }
[data-testid="stForm"] { background: #ffffff; border: none; border-radius: 20px; padding: 2.2rem 2rem 1.6rem;
                         box-shadow: 0 18px 50px rgba(13, 54, 107, .14); }
.login-head { font-size: 1.5rem; font-weight: 700; color: #0d366b; margin-bottom: 0; }
.login-sub { color: #6b6a65; font-size: .92rem; margin-bottom: .6rem; }
.login-foot { text-align: center; color: #8a897f; font-size: .8rem; margin-top: 14px; }
</style>
"""


def login_page():
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    hero, _, form_col = st.columns([1.25, 0.08, 0.9], vertical_alignment="center")
    with hero:
        svg = base64.b64encode(HERO_SVG.read_bytes()).decode()
        st.markdown(
            f"""<span class="hero-chip">🧪 MACSE518 · Smart Lab</span>
            <div class="hero-title">Smart Laboratory <span>Resource &amp; Asset</span> Management</div>
            <div class="hero-sub">Track equipment, prevent double bookings, stay ahead of maintenance and
            calibration, and keep a complete audit trail — all in one place.</div>
            <img class="hero-img" src="data:image/svg+xml;base64,{svg}" alt="Laboratory illustration"/>
            <div class="hero-features"><div>📅 Conflict-free booking</div><div>🛠 Maintenance alerts</div>
            <div>📦 Low-stock tracking</div><div>🧾 Full audit trail</div></div>""",
            unsafe_allow_html=True)
    with form_col:
        with st.form("login"):
            st.markdown('<div class="login-head">Administrator sign in</div>'
                        '<div class="login-sub">Only administrator accounts can access this console.</div>',
                        unsafe_allow_html=True)
            email = st.text_input("Email", placeholder="admin@smartlab.edu")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            user = attempt_login(email, password)
            if user:
                st.session_state["user"] = user
                try:
                    alerts.generate_notifications()
                except Exception as exc:  # alerts must never block a sign-in
                    st.session_state["_flash"] = [("warning", f"Could not refresh alerts: {exc}")]
                st.rerun()
            st.error("Invalid credentials, or this account is not an administrator.")
        st.markdown('<div class="login-foot">Demo: <code>admin@smartlab.edu</code> / <code>lab12345</code></div>',
                    unsafe_allow_html=True)


def sidebar(user):
    with st.sidebar:
        st.markdown(f"**{user['Full_Name']}**")
        st.caption(f"{user['Role_Name']} · {user['Department_Name']}")
        st.caption("Subtypes: " + ", ".join(t.replace("_", " ").title() for t in user["Subtypes"]))
        unread = scalar("SELECT COUNT(*) FROM NOTIFICATION WHERE User_ID = ? AND Status = 'UNREAD'",
                        (user["User_ID"],))
        if unread:
            st.markdown(f"🔔 **{unread}** unread notification(s)")
        if st.button("Sign out", icon=":material/logout:", width="stretch"):
            logout()
            st.rerun()


def main():
    _bootstrap()
    user = current_user()
    if not user:
        st.navigation([st.Page(login_page, title="Sign in", icon="🔐", url_path="login")],
                      position="hidden").run()
        return

    sidebar(user)
    pages = {
        "Overview": [
            st.Page(dashboard.page, title="Dashboard", icon="📊", url_path="dashboard", default=True),
            st.Page(activity.notifications, title="Notifications", icon="🔔", url_path="notifications"),
        ],
        "Assets & operations": [
            st.Page(equipment.page, title="Equipment", icon="🔬", url_path="equipment"),
            st.Page(bookings.page, title="Bookings", icon="📅", url_path="bookings"),
            st.Page(operations.maintenance, title="Maintenance", icon="🛠", url_path="maintenance"),
            st.Page(operations.calibration, title="Calibration", icon="📏", url_path="calibration"),
            st.Page(operations.transfers, title="Asset transfers", icon="🔁", url_path="transfers"),
            st.Page(operations.warranty, title="Warranty", icon="🛡", url_path="warranty"),
            st.Page(operations.consumables, title="Consumables", icon="📦", url_path="consumables"),
        ],
        "Setup": [
            st.Page(master.laboratories, title="Laboratories", icon="🧪", url_path="laboratories"),
            st.Page(master.departments, title="Departments", icon="🏢", url_path="departments"),
            st.Page(master.categories, title="Equipment categories", icon="🗂", url_path="categories"),
            st.Page(master.vendors, title="Vendors", icon="🚚", url_path="vendors"),
        ],
        "Account": [st.Page(users.profile, title="My profile", icon="🙍", url_path="profile")],
    }
    if is_admin():
        pages["Setup"].insert(0, st.Page(master.organizations, title="Organizations", icon="🏛",
                                         url_path="organizations"))
        pages["Administration"] = [
            st.Page(users.page, title="Users", icon="👥", url_path="users"),
            st.Page(master.roles, title="Roles", icon="🎭", url_path="roles"),
            st.Page(activity.audit_log, title="Audit log", icon="🧾", url_path="audit-log"),
        ]
    elif can_manage():
        pages["Administration"] = [st.Page(activity.audit_log, title="Audit log", icon="🧾", url_path="audit-log")]
    st.navigation(pages, expanded=True).run()


main()
