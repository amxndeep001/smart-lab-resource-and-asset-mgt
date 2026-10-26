"""Due / overdue calculations and automatic notifications."""
import datetime as dt

from db import notify, query_df, today_str, transaction

DUE_WINDOW_DAYS = 30
WARRANTY_WINDOW_DAYS = 60


def _plus(days):
    return (dt.date.today() + dt.timedelta(days=days)).isoformat()


# Scheduled maintenance whose date has passed without being started/completed
OVERDUE_MAINTENANCE_SQL = """
SELECT m.Maintenance_ID, e.Equipment_ID, e.Equipment_Name, l.Lab_Name, m.Maintenance_Type,
       m.Maintenance_Date, CAST(julianday(?) - julianday(m.Maintenance_Date) AS INTEGER) AS Days_Overdue
FROM MAINTENANCE m JOIN EQUIPMENT e ON e.Equipment_ID = m.Equipment_ID
LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID
WHERE m.Status = 'SCHEDULED' AND m.Maintenance_Date < ?
ORDER BY m.Maintenance_Date"""

DUE_MAINTENANCE_SQL = """
SELECT m.Maintenance_ID, e.Equipment_ID, e.Equipment_Name, l.Lab_Name, m.Maintenance_Type,
       m.Maintenance_Date, CAST(julianday(m.Maintenance_Date) - julianday(?) AS INTEGER) AS Days_Left
FROM MAINTENANCE m JOIN EQUIPMENT e ON e.Equipment_ID = m.Equipment_ID
LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID
WHERE m.Status = 'SCHEDULED' AND m.Maintenance_Date BETWEEN ? AND ?
ORDER BY m.Maintenance_Date"""

# The current calibration of an item is its most recent COMPLETED one; its Next_Due_Date drives alerts.
_LATEST_CAL = """
SELECT c.* FROM CALIBRATION c
WHERE c.Status = 'COMPLETED' AND c.Calibration_Date = (
    SELECT MAX(c2.Calibration_Date) FROM CALIBRATION c2
    WHERE c2.Equipment_ID = c.Equipment_ID AND c2.Status = 'COMPLETED')"""

OVERDUE_CALIBRATION_SQL = f"""
SELECT e.Equipment_ID, e.Equipment_Name, l.Lab_Name, lc.Calibration_Date AS Last_Calibrated,
       lc.Next_Due_Date, CAST(julianday(?) - julianday(lc.Next_Due_Date) AS INTEGER) AS Days_Overdue
FROM ({_LATEST_CAL}) lc JOIN EQUIPMENT e ON e.Equipment_ID = lc.Equipment_ID
LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID
WHERE e.Equipment_Status <> 'RETIRED' AND lc.Next_Due_Date < ?
ORDER BY lc.Next_Due_Date"""

DUE_CALIBRATION_SQL = f"""
SELECT e.Equipment_ID, e.Equipment_Name, l.Lab_Name, lc.Calibration_Date AS Last_Calibrated,
       lc.Next_Due_Date, CAST(julianday(lc.Next_Due_Date) - julianday(?) AS INTEGER) AS Days_Left
FROM ({_LATEST_CAL}) lc JOIN EQUIPMENT e ON e.Equipment_ID = lc.Equipment_ID
LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID
WHERE e.Equipment_Status <> 'RETIRED' AND lc.Next_Due_Date BETWEEN ? AND ?
ORDER BY lc.Next_Due_Date"""

LOW_STOCK_SQL = "SELECT * FROM V_LOW_STOCK ORDER BY Quantity * 1.0 / NULLIF(Reorder_Level, 0)"

EXPIRING_WARRANTY_SQL = """
SELECT w.Warranty_ID, e.Equipment_Name, v.Vendor_Name, w.Warranty_End_Date,
       CAST(julianday(w.Warranty_End_Date) - julianday(?) AS INTEGER) AS Days_Left
FROM WARRANTY w JOIN EQUIPMENT e ON e.Equipment_ID = w.Equipment_ID
LEFT JOIN VENDOR v ON v.Vendor_ID = w.Vendor_ID
WHERE w.Warranty_Status = 'ACTIVE' AND w.Warranty_End_Date BETWEEN ? AND ?
ORDER BY w.Warranty_End_Date"""


def overdue_maintenance():
    t = today_str()
    return query_df(OVERDUE_MAINTENANCE_SQL, (t, t))


def due_maintenance(days=DUE_WINDOW_DAYS):
    t = today_str()
    return query_df(DUE_MAINTENANCE_SQL, (t, t, _plus(days)))


def overdue_calibration():
    t = today_str()
    return query_df(OVERDUE_CALIBRATION_SQL, (t, t))


def due_calibration(days=DUE_WINDOW_DAYS):
    t = today_str()
    return query_df(DUE_CALIBRATION_SQL, (t, t, _plus(days)))


def low_stock():
    return query_df(LOW_STOCK_SQL)


def expiring_warranties(days=WARRANTY_WINDOW_DAYS):
    t = today_str()
    return query_df(EXPIRING_WARRANTY_SQL, (t, t, _plus(days)))


def refresh_statuses(conn):
    """Keep derived statuses in sync with today's date."""
    conn.execute("UPDATE WARRANTY SET Warranty_Status = 'EXPIRED' "
                 "WHERE Warranty_Status = 'ACTIVE' AND Warranty_End_Date < ?", (today_str(),))


def generate_notifications():
    """Create notifications for every alert, for each manager-level user. Returns rows created."""
    created = 0
    alerts = []
    for _, r in overdue_maintenance().iterrows():
        alerts.append(("MAINTENANCE_OVERDUE", f"Maintenance #{r.Maintenance_ID} ({r.Maintenance_Type}) for "
                       f"{r.Equipment_Name} was due on {r.Maintenance_Date} and is overdue."))
    for _, r in due_maintenance().iterrows():
        alerts.append(("MAINTENANCE_DUE", f"{r.Maintenance_Type} maintenance for {r.Equipment_Name} is "
                       f"scheduled on {r.Maintenance_Date}."))
    for _, r in overdue_calibration().iterrows():
        alerts.append(("CALIBRATION_OVERDUE", f"Calibration of {r.Equipment_Name} was due on "
                       f"{r.Next_Due_Date} and is overdue."))
    for _, r in due_calibration().iterrows():
        alerts.append(("CALIBRATION_DUE", f"Calibration of {r.Equipment_Name} is due on {r.Next_Due_Date}."))
    for _, r in low_stock().iterrows():
        alerts.append(("LOW_STOCK", f"Low stock: {r.Item_Name} at {r.Lab_Name} — {r.Quantity:g} {r.Unit or ''} "
                       f"left (reorder level {r.Reorder_Level:g})."))
    for _, r in expiring_warranties().iterrows():
        alerts.append(("WARRANTY_EXPIRING", f"Warranty for {r.Equipment_Name} ({r.Vendor_Name}) expires on "
                       f"{r.Warranty_End_Date}."))
    with transaction() as conn:
        refresh_statuses(conn)
        recipients = [r[0] for r in conn.execute(
            "SELECT u.User_ID FROM LAB_USER u JOIN ROLE r ON r.Role_ID = u.Role_ID "
            "WHERE r.Access_Level >= 3 AND COALESCE(r.Status, 'ACTIVE') = 'ACTIVE'")]
        for user_id in recipients:
            for ntype, msg in alerts:
                created += notify(conn, user_id, ntype, msg)
    return created
