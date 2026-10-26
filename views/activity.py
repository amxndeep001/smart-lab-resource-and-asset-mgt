"""Notifications and the read-only audit log."""
import datetime as dt

import streamlit as st

import alerts
from auth import current_user, is_admin
from crud import Col, TableSpec, flash, render_crud, render_table, show_flash
from db import query_df, transaction
from views.common import USER_FK, header

NOTIFICATION_TYPES = ["MAINTENANCE_OVERDUE", "MAINTENANCE_DUE", "CALIBRATION_OVERDUE", "CALIBRATION_DUE",
                      "LOW_STOCK", "WARRANTY_EXPIRING", "BOOKING", "GENERAL"]


def _mark(ids, status):
    with transaction() as conn:
        conn.executemany("UPDATE NOTIFICATION SET Status = ? WHERE Notification_ID = ?", [(status, i) for i in ids])


def _inbox():
    user = current_user()
    df = query_df("SELECT Notification_ID, Date_Time, Notification_Type, Message, Status FROM NOTIFICATION "
                  "WHERE User_ID = ? ORDER BY Status = 'READ', Date_Time DESC", (user["User_ID"],))
    unread = df[df.Status == "UNREAD"]
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.metric("Unread", len(unread))
    if c2.button("Mark all as read", disabled=unread.empty, width="stretch"):
        _mark(unread.Notification_ID.tolist(), "READ")
        st.rerun()
    if c3.button("🔄 Check for new alerts", width="stretch"):
        n = alerts.generate_notifications()
        flash("info", f"{n} new notification(s) generated.")
        st.rerun()
    show = st.radio("Show", ["Unread", "All"], horizontal=True, key="inbox_show")
    rows = unread if show == "Unread" else df
    if rows.empty:
        st.success("You're all caught up.")
        return
    for r in rows.head(100).itertuples():
        with st.container(border=True):
            a, b = st.columns([8, 1])
            badge = "🔵" if r.Status == "UNREAD" else "⚪"
            a.markdown(f"{badge} **{r.Notification_Type.replace('_', ' ').title()}** · "
                       f"<span style='opacity:.7'>{r.Date_Time}</span><br>{r.Message}", unsafe_allow_html=True)
            if r.Status == "UNREAD" and b.button("Read", key=f"read_{r.Notification_ID}"):
                _mark([r.Notification_ID], "READ")
                st.rerun()
    if len(rows) > 100:
        st.caption(f"Showing 100 of {len(rows)}.")


def notifications():
    header("🔔 Notifications", "User receives Notification. Alerts for overdue/due maintenance and calibration, "
                              "low stock and expiring warranties are generated automatically at sign-in.")
    if not is_admin():
        show_flash()
        _inbox()
        return
    spec = TableSpec(
        table="NOTIFICATION", pk="Notification_ID", title="Notification",
        label_sql="Date_Time || ' · ' || Notification_Type || ' · ' || "
                  "(SELECT Full_Name FROM LAB_USER u WHERE u.User_ID = NOTIFICATION.User_ID)",
        columns=[
            Col("User_ID", "Recipient", kind="fk", fk_sql=USER_FK, required=True),
            Col("Notification_Type", kind="select", options=NOTIFICATION_TYPES, required=True, default="GENERAL"),
            Col("Status", kind="select", options=["UNREAD", "READ"], required=True, default="UNREAD"),
            Col("Date_Time", help="YYYY-MM-DD HH:MM:SS",
                default=lambda: dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            Col("Message", kind="textarea", required=True),
        ],
        view_sql="""SELECT n.Notification_ID, n.Date_Time, u.Full_Name AS Recipient, n.Notification_Type,
                    n.Message, n.Status FROM NOTIFICATION n JOIN LAB_USER u ON u.User_ID = n.User_ID
                    ORDER BY n.Date_Time DESC""",
        filters=["Notification_Type", "Status", "Recipient"],
        extra_tabs=[("📥 My inbox", _inbox)],
        tabs_first=True,
        add_label="Send",
    )
    render_crud(spec)


def audit_log():
    header("🧾 Audit Log", "User performs Audit Log. Every login and every create / update / delete is recorded "
                          "automatically. This view is read-only.")
    df = query_df("""SELECT a.Log_ID, a.Date_Time, COALESCE(u.Full_Name, '(unknown / deleted)') AS User,
                     a.Action_Performed, a.Remarks, a.IP_Address, a.Maintenance_ID
                     FROM AUDIT_LOG a LEFT JOIN LAB_USER u ON u.User_ID = a.User_ID
                     ORDER BY a.Date_Time DESC, a.Log_ID DESC""")
    if df.empty:
        st.info("No audit entries yet.")
        return
    df["Action_Type"] = df.Action_Performed.str.split(" ").str[0]
    df["Entity"] = df.Action_Performed.str.split(" ").str[1].fillna("")
    dates = df.Date_Time.str[:10]
    c1, c2 = st.columns(2)
    start = c1.date_input("From", dt.date.fromisoformat(dates.min()), key="audit_from", format="YYYY-MM-DD")
    end = c2.date_input("To", dt.date.today(), key="audit_to", format="YYYY-MM-DD")
    df = df[(dates >= start.isoformat()) & (dates <= end.isoformat())]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Entries", len(df))
    k2.metric("Logins", int((df.Action_Type == "LOGIN").sum()))
    k3.metric("Failed logins", int((df.Action_Type == "LOGIN_FAILED").sum()))
    k4.metric("Data changes", int(df.Action_Type.isin(["CREATE", "UPDATE", "DELETE"]).sum()))
    render_table(df[["Log_ID", "Date_Time", "User", "Action_Type", "Entity", "Action_Performed", "Remarks",
                     "IP_Address", "Maintenance_ID"]],
                 "audit", ["User", "Action_Type", "Entity"], "audit_log.csv")
