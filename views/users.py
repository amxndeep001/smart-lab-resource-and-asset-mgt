"""Users with the Total + Overlapping specialization, plus the personal profile page."""
import streamlit as st

from auth import USER_SUBTYPE_TABLES, check_password, current_user, hash_password, is_admin, load_user, user_subtypes
from crud import Col, TableSpec, flash, render_crud, render_fields, render_table, show_flash
from db import log_action, query_df, query_one, transaction
from views.common import DEPT_FK, ROLE_FK, contact_errors, header

# subtype table -> (label, columns).  Last_Login is maintained by the login process.
USER_SUBTYPES = {
    "ADMINISTRATOR": ("Administrator", [
        Col("Admin_Level", kind="select", options=["Super Admin", "System Admin", "Department Admin"]),
        Col("Permissions", help="e.g. ALL or USERS,ROLES,AUDIT")]),
    "LAB_MANAGER": ("Lab Manager", [
        Col("Office_Room"), Col("Experience", "Experience (years)", kind="int", min_value=0),
        Col("Managed_Labs", help="Comma-separated lab names")]),
    "LAB_TECHNICIAN": ("Lab Technician", [
        Col("Skill_Type"), Col("Shift_Time", kind="select", options=["Morning", "Afternoon", "Evening", "Night"]),
        Col("Certification")]),
    "RESEARCHER": ("Researcher", [
        Col("Research_Area"), Col("Qualification", kind="select", options=["BSc", "MSc", "MTech", "PhD", "PostDoc"]),
        Col("Research_Interest")]),
    "FACULTY": ("Faculty", [
        Col("Department_Affiliation"),
        Col("Designation", kind="select", options=["Professor", "Associate Professor", "Assistant Professor",
                                                   "Lecturer", "Visiting Faculty"]),
        Col("Date_of_Joining", kind="date")]),
}

SUBTYPE_LIST_SQL = " UNION ALL ".join(
    f"SELECT '{label}' AS t FROM {table} x WHERE x.User_ID = u.User_ID"
    for table, (label, _) in USER_SUBTYPES.items())

VIEW_SQL = f"""
SELECT u.User_ID, u.Full_Name, u.Email, u.Phone_Number, d.Department_Name, r.Role_Name, r.Access_Level,
       (SELECT group_concat(t, ', ') FROM ({SUBTYPE_LIST_SQL})) AS Subtypes
FROM LAB_USER u JOIN DEPARTMENT d ON d.Department_ID = u.Department_ID JOIN ROLE r ON r.Role_ID = u.Role_ID
ORDER BY u.User_ID"""


def _extra_form(mode, record, values, key):
    st.markdown("**Password**")
    if mode == "add":
        password = st.text_input("Password *", type="password", key=f"{key}_pw", help="At least 6 characters")
    else:
        password = st.text_input("New password (leave blank to keep the current one)", type="password",
                                 key=f"{key}_pw")
    st.markdown("**EER subtypes** · Total + Overlapping: pick at least one, several are allowed")
    current = user_subtypes(record["User_ID"]) if record else []
    chosen = st.multiselect("Subtypes *", list(USER_SUBTYPES), default=current, key=f"{key}_subtypes",
                            format_func=lambda t: USER_SUBTYPES[t][0])
    data = {}
    for table in chosen:
        label, cols = USER_SUBTYPES[table]
        with st.container(border=True):
            st.markdown(f"**{label}** · `{table}`")
            existing = query_one(f"SELECT * FROM {table} WHERE User_ID = ?", (record["User_ID"],)) if record else None
            data[table] = render_fields(cols, existing, f"{key}_{table}", ncols=3)
    return {"password": password, "subtypes": data}


def _validate_extra(extra, mode):
    errors = []
    pw = extra.get("password") or ""
    if mode == "add" and not pw:
        errors.append("Password is required.")
    if pw and len(pw) < 6:
        errors.append("Password must be at least 6 characters.")
    if not extra.get("subtypes"):
        errors.append("Select at least one subtype — every user must belong to a subtype (total specialization).")
    return errors


def _prepare(values, extra, mode, old):
    if extra.get("password"):
        values["Password_Hash"] = hash_password(extra["password"])


def _after_save(conn, user_id, values, extra, mode, old):
    chosen = extra["subtypes"]
    for table in USER_SUBTYPE_TABLES:
        if table not in chosen:
            conn.execute(f"DELETE FROM {table} WHERE User_ID = ?", (user_id,))
    for table, data in chosen.items():
        cols = list(data)
        conn.execute(
            f"INSERT INTO {table} (User_ID, {', '.join(cols)}) VALUES (?, {', '.join('?' * len(cols))}) "
            f"ON CONFLICT(User_ID) DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in cols)}",
            [user_id] + [data[c] for c in cols])


def _before_delete(conn, record):
    if record["User_ID"] == current_user()["User_ID"]:
        return "You cannot delete the account you are signed in with."
    return None


def _subtype_tab():
    st.caption("Each subtype is its own table whose primary key is also a foreign key to LAB_USER "
               "(ON DELETE CASCADE). A user may appear in several subtype tables.")
    table = st.selectbox("Subtype table", list(USER_SUBTYPES), format_func=lambda t: f"{USER_SUBTYPES[t][0]} ({t})",
                         key="subtype_table")
    df = query_df(f"SELECT s.*, u.Full_Name, u.Email FROM {table} s JOIN LAB_USER u ON u.User_ID = s.User_ID "
                  "ORDER BY s.User_ID")
    render_table(df, f"subtype_{table}", file_name=f"{table.lower()}.csv")
    orphans = query_df(f"SELECT u.User_ID, u.Full_Name, u.Email FROM LAB_USER u WHERE NOT EXISTS "
                       f"(SELECT 1 FROM ({SUBTYPE_LIST_SQL}))")
    overlap = query_df(f"SELECT u.User_ID, u.Full_Name, (SELECT group_concat(t, ', ') FROM ({SUBTYPE_LIST_SQL})) "
                       f"AS Subtypes FROM LAB_USER u WHERE (SELECT COUNT(*) FROM ({SUBTYPE_LIST_SQL})) > 1")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Total participation check**")
        if orphans.empty:
            st.success("Every user belongs to at least one subtype.")
        else:
            st.error(f"{len(orphans)} user(s) have no subtype.")
            st.dataframe(orphans, hide_index=True)
    with c2:
        st.markdown("**Overlapping memberships**")
        st.dataframe(overlap, hide_index=True)


def page():
    header("👥 Users", "Department contains User · Role is assigned to User · USER specialization is "
                      "Total + Overlapping.")
    admin = is_admin()
    spec = TableSpec(
        table="LAB_USER", pk="User_ID", title="User", label_sql="Full_Name || ' <' || Email || '>'",
        columns=[
            Col("Full_Name", required=True, rule="person"),
            Col("Email", required=True),
            Col("Phone_Number"),
            Col("Department_ID", "Department", kind="fk", fk_sql=DEPT_FK, required=True),
            Col("Role_ID", "Role", kind="fk", fk_sql=ROLE_FK, required=True),
        ],
        view_sql=VIEW_SQL,
        filters=["Department_Name", "Role_Name"],
        validate=lambda v, m, o, c: contact_errors(v, ["Email"], ["Phone_Number"]),
        extra_form=_extra_form,
        validate_extra=_validate_extra,
        prepare=_prepare,
        after_save=_after_save,
        before_delete=_before_delete,
        extra_tabs=[("🧬 Subtype tables", _subtype_tab)],
        can_add=admin, can_edit=admin, can_delete=admin,
    )
    render_crud(spec)


def profile():
    show_flash()
    user = current_user()
    header("🙍 My Profile")
    info = query_df(VIEW_SQL.replace("ORDER BY u.User_ID", "WHERE u.User_ID = ?"), (user["User_ID"],))
    st.dataframe(info.drop(columns=["User_ID"]), hide_index=True)
    for table in user_subtypes(user["User_ID"]):
        row = query_one(f"SELECT * FROM {table} WHERE User_ID = ?", (user["User_ID"],))
        st.markdown(f"**{USER_SUBTYPES[table][0]}** — " +
                    " · ".join(f"{k.replace('_', ' ')}: {v}" for k, v in row.items() if k != "User_ID" and v))
    st.subheader("Change password")
    with st.form("change_pw", clear_on_submit=True):
        current = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Update password", type="primary"):
            stored = query_one("SELECT Password_Hash FROM LAB_USER WHERE User_ID = ?", (user["User_ID"],))
            if not check_password(current, stored["Password_Hash"]):
                st.error("Current password is incorrect.")
            elif len(new) < 6:
                st.error("New password must be at least 6 characters.")
            elif new != confirm:
                st.error("The new passwords do not match.")
            else:
                with transaction() as conn:
                    conn.execute("UPDATE LAB_USER SET Password_Hash = ? WHERE User_ID = ?",
                                 (hash_password(new), user["User_ID"]))
                    log_action("UPDATE LAB_USER", f"User_ID={user['User_ID']}: password changed", conn=conn)
                st.session_state["user"] = load_user(user["User_ID"])
                flash("success", "Password updated.")
                st.rerun()
