"""Equipment booking with double-booking prevention."""
import datetime as dt
import re

import streamlit as st

from auth import can_manage, current_user
from crud import Col, TableSpec, flash, render_crud, render_table
from db import friendly_error, log_action, notify, query_all, query_df, today_str, transaction
from views.common import EQUIPMENT_FK, USER_FK, header

BOOKING_STATUS = ["PENDING", "APPROVED", "REJECTED", "CANCELLED", "COMPLETED"]
ACTIVE_STATUS = ("PENDING", "APPROVED")
TIME_SLOTS = ([f"{h:02d}:00-{h + 1:02d}:00" for h in range(8, 18)] +
              [f"{h:02d}:00-{h + 2:02d}:00" for h in range(8, 18, 2)])
SLOT_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")

VIEW_SQL = """
SELECT b.Booking_ID, b.Booking_Date, b.Time_Slot, b.Booking_Status, e.Equipment_Name, e.Serial_Number,
       l.Lab_Name, u.Full_Name AS Booked_By, u.Email
FROM EQUIPMENT_BOOKING b
JOIN EQUIPMENT e ON e.Equipment_ID = b.Equipment_ID
LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID
JOIN LAB_USER u ON u.User_ID = b.User_ID
{where}
ORDER BY b.Booking_Date DESC, b.Time_Slot"""


def parse_slot(slot):
    """'09:00-11:00' -> (540, 660) minutes; None if malformed or start >= end."""
    m = SLOT_RE.match(slot or "")
    if not m:
        return None
    start = int(m.group(1)) * 60 + int(m.group(2))
    end = int(m.group(3)) * 60 + int(m.group(4))
    return (start, end) if start < end else None


def find_conflicts(conn, equipment_id, booking_date, slot, exclude_id=None):
    """Active (PENDING/APPROVED) bookings of the same equipment on the same date whose slot overlaps."""
    span = parse_slot(slot)
    rows = query_all(
        "SELECT b.Booking_ID, b.Time_Slot, b.Booking_Status, u.Full_Name FROM EQUIPMENT_BOOKING b "
        "JOIN LAB_USER u ON u.User_ID = b.User_ID WHERE b.Equipment_ID = ? AND b.Booking_Date = ? "
        "AND b.Booking_Status IN ('PENDING', 'APPROVED') AND b.Booking_ID <> ?",
        (equipment_id, booking_date, exclude_id or -1), conn)
    conflicts = []
    for r in rows:
        other = parse_slot(r["Time_Slot"])
        if span and other and span[0] < other[1] and other[0] < span[1]:
            conflicts.append(r)
    return conflicts


def _validate(values, mode, old, conn):
    errors = []
    if parse_slot(values.get("Time_Slot")) is None:
        return ["Time slot must look like HH:MM-HH:MM with the start before the end."]
    if mode == "add" and not can_manage() and values.get("Booking_Date", "") < today_str():
        errors.append("Bookings cannot be made for a past date.")
    if values.get("Booking_Status") in ACTIVE_STATUS:
        eq = conn.execute("SELECT Equipment_Name, Equipment_Status FROM EQUIPMENT WHERE Equipment_ID = ?",
                          (values["Equipment_ID"],)).fetchone()
        if eq and eq["Equipment_Status"] == "RETIRED":
            errors.append(f"{eq['Equipment_Name']} is RETIRED and cannot be booked.")
        for c in find_conflicts(conn, values["Equipment_ID"], values["Booking_Date"], values["Time_Slot"],
                                old["Booking_ID"] if old else None):
            errors.append(f"Double booking rejected: booking #{c['Booking_ID']} ({c['Time_Slot']}, "
                          f"{c['Booking_Status']}, {c['Full_Name']}) already holds this equipment.")
    return errors


def _after_save(conn, booking_id, values, extra, mode, old):
    eq = conn.execute("SELECT Equipment_Name FROM EQUIPMENT WHERE Equipment_ID = ?",
                      (values["Equipment_ID"],)).fetchone()["Equipment_Name"]
    when = f"{values['Booking_Date']} {values['Time_Slot']}"
    if mode == "add":
        notify(conn, values["User_ID"], "BOOKING", f"Booking #{booking_id} for {eq} on {when} created "
                                                   f"with status {values['Booking_Status']}.")
    elif old["Booking_Status"] != values["Booking_Status"]:
        notify(conn, values["User_ID"], "BOOKING", f"Booking #{booking_id} for {eq} on {when} is now "
                                                   f"{values['Booking_Status']}.")


def set_status(booking_id, status):
    try:
        with transaction() as conn:
            row = conn.execute("SELECT * FROM EQUIPMENT_BOOKING WHERE Booking_ID = ?", (booking_id,)).fetchone()
            conn.execute("UPDATE EQUIPMENT_BOOKING SET Booking_Status = ? WHERE Booking_ID = ?", (status, booking_id))
            values = dict(row)
            old = dict(row)
            values["Booking_Status"] = status
            _after_save(conn, booking_id, values, {}, "edit", old)
            log_action("UPDATE EQUIPMENT_BOOKING", f"Booking_ID={booking_id}: Booking_Status: "
                                                   f"{old['Booking_Status']} → {status}", conn=conn)
        flash("success", f"Booking #{booking_id} {status.lower()}.")
    except Exception as exc:
        flash("error", friendly_error(exc))


def _approvals_tab():
    pending = query_df(VIEW_SQL.format(where="WHERE b.Booking_Status = 'PENDING'"))
    if pending.empty:
        st.success("No bookings are waiting for approval.")
        return
    st.caption(f"{len(pending)} booking request(s) waiting for a decision.")
    for r in pending.itertuples():
        c1, c2, c3 = st.columns([6, 1, 1])
        c1.markdown(f"**#{r.Booking_ID}** · {r.Equipment_Name} · {r.Booking_Date} {r.Time_Slot} · "
                    f"{r.Booked_By} ({r.Lab_Name or '—'})")
        if c2.button("Approve", key=f"appr_{r.Booking_ID}", type="primary"):
            set_status(r.Booking_ID, "APPROVED")
            st.rerun()
        if c3.button("Reject", key=f"rej_{r.Booking_ID}"):
            set_status(r.Booking_ID, "REJECTED")
            st.rerun()


def _availability_tab():
    st.subheader("Find free equipment")
    c1, c2 = st.columns(2)
    day = c1.date_input("Date", dt.date.today(), key="avail_date", format="YYYY-MM-DD").isoformat()
    slot = c2.selectbox("Time slot", TIME_SLOTS, key="avail_slot")
    span = parse_slot(slot)
    equipment = query_df("""SELECT e.Equipment_ID, e.Equipment_Name, e.Serial_Number, e.Equipment_Type,
                            e.Equipment_Status, l.Lab_Name FROM EQUIPMENT e
                            LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID
                            WHERE e.Equipment_Status <> 'RETIRED' ORDER BY e.Equipment_Name""")
    booked = query_df("SELECT Equipment_ID, Time_Slot FROM EQUIPMENT_BOOKING WHERE Booking_Date = ? "
                      "AND Booking_Status IN ('PENDING', 'APPROVED')", (day,))
    busy = {r.Equipment_ID for r in booked.itertuples()
            if parse_slot(r.Time_Slot) and span[0] < parse_slot(r.Time_Slot)[1] and parse_slot(r.Time_Slot)[0] < span[1]}
    free = equipment[~equipment.Equipment_ID.isin(busy)]
    st.caption(f"{len(free)} of {len(equipment)} active items are free on {day}, {slot}. Items under maintenance "
               "or calibration are listed with their status so you can judge whether they will be ready.")
    render_table(free, "avail_free", ["Lab_Name", "Equipment_Type", "Equipment_Status"], f"free_{day}.csv")
    st.subheader(f"Bookings on {day}")
    render_table(query_df(VIEW_SQL.format(where="WHERE b.Booking_Date = ?"), (day,)), "avail_day",
                 ["Booking_Status"], f"bookings_{day}.csv", search=False)


def page():
    header("📅 Equipment Booking", "User makes Equipment Booking · overlapping PENDING/APPROVED bookings for the "
                                  "same equipment and date are rejected.")
    user = current_user()
    manage = can_manage()
    columns = [
        Col("Equipment_ID", "Equipment", kind="fk", fk_sql=EQUIPMENT_FK, required=True),
        Col("User_ID", "Booked by", kind="fk", required=True,
            fk_sql=USER_FK if manage else
            f"SELECT User_ID AS id, Full_Name AS label FROM LAB_USER WHERE User_ID = {int(user['User_ID'])}",
            default=user["User_ID"]),
        Col("Booking_Date", kind="date", required=True),
        Col("Time_Slot", kind="select", options=TIME_SLOTS, required=True,
            help="Two-hour blocks overlap the hourly slots they contain."),
        Col("Booking_Status", "Status", kind="select", required=True, default="PENDING",
            options=BOOKING_STATUS if manage else ["PENDING", "CANCELLED"]),
    ]
    spec = TableSpec(
        table="EQUIPMENT_BOOKING", pk="Booking_ID", title="Booking",
        label_sql="Booking_Date || ' ' || Time_Slot || ' · ' || Booking_Status || ' · ' || "
                  "(SELECT Equipment_Name FROM EQUIPMENT e WHERE e.Equipment_ID = EQUIPMENT_BOOKING.Equipment_ID)",
        columns=columns,
        view_sql=VIEW_SQL.format(where=""),
        filters=["Booking_Status", "Lab_Name"],
        validate=_validate,
        after_save=_after_save,
        extra_tabs=[("🔎 Check availability", _availability_tab)],
        can_delete=manage,
        add_label="New booking",
    )
    if manage:
        spec.extra_tabs.insert(0, ("✅ Pending approvals", _approvals_tab))
    else:
        spec.edit_where, spec.edit_params = "WHERE User_ID = ?", (user["User_ID"],)
    render_crud(spec)
