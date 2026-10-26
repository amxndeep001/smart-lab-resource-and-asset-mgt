"""Maintenance, calibration, asset transfers, warranties and consumables."""
import streamlit as st

import alerts
from auth import can_manage
from crud import Col, TableSpec, flash, render_crud, render_table
from db import friendly_error, log_action, query_df, today_str, transaction
from views.common import EQUIPMENT_FK, LAB_FK, VENDOR_FK, header, read_only_note


def _manage_flags(spec):
    allowed = can_manage()
    spec.can_add = spec.can_edit = spec.can_delete = allowed
    if not allowed:
        read_only_note()
    return spec


def _set_equipment_status(conn, equipment_id, new_status, only_if=None):
    sql = "UPDATE EQUIPMENT SET Equipment_Status = ? WHERE Equipment_ID = ?"
    params = [new_status, equipment_id]
    if only_if:
        sql += f" AND Equipment_Status IN ({', '.join('?' * len(only_if))})"
        params += list(only_if)
    if conn.execute(sql, params).rowcount:
        log_action("UPDATE EQUIPMENT", f"Equipment_ID={equipment_id}: Equipment_Status → {new_status} (automatic)",
                   conn=conn)


def _alert_tables(sections):
    for title, df, empty_msg, key in sections:
        st.subheader(title)
        if df.empty:
            st.success(empty_msg)
        else:
            render_table(df, key, file_name=f"{key}.csv", search=False)


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------
MAINT_STATUS = ["SCHEDULED", "IN_PROGRESS", "COMPLETED"]


def _maintenance_after_save(conn, mid, values, extra, mode, old):
    # Keep equipment availability in step with the work order.
    if values["Status"] == "IN_PROGRESS":
        _set_equipment_status(conn, values["Equipment_ID"], "UNDER_MAINTENANCE", only_if=("AVAILABLE", "IN_USE"))
    elif values["Status"] == "COMPLETED":
        _set_equipment_status(conn, values["Equipment_ID"], "AVAILABLE", only_if=("UNDER_MAINTENANCE",))


def maintenance():
    header("🛠 Maintenance", "Equipment undergoes Maintenance. Starting a job marks the item UNDER_MAINTENANCE; "
                            "completing it returns the item to AVAILABLE.")
    spec = TableSpec(
        table="MAINTENANCE", pk="Maintenance_ID", title="Maintenance",
        label_sql="Maintenance_Date || ' · ' || Maintenance_Type || ' · ' || Status || ' · ' || "
                  "(SELECT Equipment_Name FROM EQUIPMENT e WHERE e.Equipment_ID = MAINTENANCE.Equipment_ID)",
        columns=[
            Col("Equipment_ID", "Equipment", kind="fk", fk_sql=EQUIPMENT_FK, required=True),
            Col("Maintenance_Date", kind="date", required=True),
            Col("Maintenance_Type", kind="select", options=["Preventive", "Repair", "Inspection"], required=True),
            Col("Cost", kind="float", min_value=0, default=0.0),
            Col("Status", kind="select", options=MAINT_STATUS, required=True, default="SCHEDULED"),
        ],
        view_sql="""SELECT m.Maintenance_ID, m.Maintenance_Date, m.Maintenance_Type, m.Status, m.Cost,
                    e.Equipment_Name, e.Serial_Number, l.Lab_Name,
                    CASE WHEN m.Status = 'SCHEDULED' AND m.Maintenance_Date < date('now', 'localtime')
                         THEN 'OVERDUE' ELSE '' END AS Flag
                    FROM MAINTENANCE m JOIN EQUIPMENT e ON e.Equipment_ID = m.Equipment_ID
                    LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID ORDER BY m.Maintenance_Date DESC""",
        filters=["Status", "Maintenance_Type", "Flag"],
        after_save=_maintenance_after_save,
        audit_maintenance=True,
        extra_tabs=[("⏰ Overdue & due soon", lambda: _alert_tables([
            ("Overdue maintenance", alerts.overdue_maintenance(), "No overdue maintenance. 🎉", "maint_overdue"),
            (f"Due in the next {alerts.DUE_WINDOW_DAYS} days", alerts.due_maintenance(),
             "Nothing scheduled in the next 30 days.", "maint_due"),
        ]))],
        tabs_first=True,
    )
    render_crud(_manage_flags(spec))


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------
def _calibration_validate(values, mode, old, conn):
    if values.get("Next_Due_Date") and values["Next_Due_Date"] <= values["Calibration_Date"]:
        return ["Next due date must be after the calibration date."]
    if values.get("Status") == "COMPLETED" and not values.get("Next_Due_Date"):
        return ["A completed calibration needs a next due date."]
    return []


def _calibration_after_save(conn, cid, values, extra, mode, old):
    if values["Status"] == "IN_PROGRESS":
        _set_equipment_status(conn, values["Equipment_ID"], "UNDER_CALIBRATION", only_if=("AVAILABLE", "IN_USE"))
    elif values["Status"] in ("COMPLETED", "FAILED"):
        _set_equipment_status(conn, values["Equipment_ID"],
                              "AVAILABLE" if values["Status"] == "COMPLETED" else "UNDER_MAINTENANCE",
                              only_if=("UNDER_CALIBRATION",))


def calibration():
    header("📏 Calibration", "Equipment requires Calibration. The latest completed calibration's next due date "
                            "drives the overdue / due-soon alerts.")
    spec = TableSpec(
        table="CALIBRATION", pk="Calibration_ID", title="Calibration",
        label_sql="Calibration_Date || ' · ' || Status || ' · ' || "
                  "(SELECT Equipment_Name FROM EQUIPMENT e WHERE e.Equipment_ID = CALIBRATION.Equipment_ID)",
        columns=[
            Col("Equipment_ID", "Equipment", kind="fk", fk_sql=EQUIPMENT_FK, required=True),
            Col("Calibration_Date", kind="date", required=True),
            Col("Next_Due_Date", kind="date", help="Must be after the calibration date"),
            Col("Technician_Name", rule="person"),
            Col("Status", kind="select", options=["SCHEDULED", "IN_PROGRESS", "COMPLETED", "FAILED"],
                required=True, default="SCHEDULED"),
        ],
        view_sql="""SELECT c.Calibration_ID, c.Calibration_Date, c.Next_Due_Date, c.Status, c.Technician_Name,
                    e.Equipment_Name, e.Serial_Number, l.Lab_Name
                    FROM CALIBRATION c JOIN EQUIPMENT e ON e.Equipment_ID = c.Equipment_ID
                    LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID ORDER BY c.Calibration_Date DESC""",
        filters=["Status", "Lab_Name"],
        validate=_calibration_validate,
        after_save=_calibration_after_save,
        extra_tabs=[("⏰ Overdue & due soon", lambda: _alert_tables([
            ("Overdue calibration", alerts.overdue_calibration(), "No overdue calibrations. 🎉", "cal_overdue"),
            (f"Due in the next {alerts.DUE_WINDOW_DAYS} days", alerts.due_calibration(),
             "No calibrations due in the next 30 days.", "cal_due"),
        ]))],
        tabs_first=True,
    )
    render_crud(_manage_flags(spec))


# ---------------------------------------------------------------------------
# Asset transfer
# ---------------------------------------------------------------------------
def _transfer_validate(values, mode, old, conn):
    errors = []
    if values["From_Lab_ID"] == values["To_Lab_ID"]:
        errors.append("From-lab and To-lab must be different.")
    current = conn.execute("SELECT Lab_ID FROM EQUIPMENT WHERE Equipment_ID = ?",
                           (values["Equipment_ID"],)).fetchone()
    newly_completed = values["Status"] == "COMPLETED" and (mode == "add" or old["Status"] != "COMPLETED")
    if newly_completed and current and current["Lab_ID"] not in (None, values["From_Lab_ID"]):
        errors.append("The equipment is not currently in the From-lab; check the transfer details.")
    return errors


def _transfer_after_save(conn, tid, values, extra, mode, old):
    if values["Status"] == "COMPLETED" and (mode == "add" or old["Status"] != "COMPLETED"):
        conn.execute("UPDATE EQUIPMENT SET Lab_ID = ? WHERE Equipment_ID = ?",
                     (values["To_Lab_ID"], values["Equipment_ID"]))
        log_action("UPDATE EQUIPMENT", f"Equipment_ID={values['Equipment_ID']}: Lab_ID "
                                       f"{values['From_Lab_ID']} → {values['To_Lab_ID']} (transfer #{tid})",
                   conn=conn)


def transfers():
    header("🔁 Asset Transfers", "Equipment is transferred through Asset Transfer. Completing a transfer moves the "
                                "equipment to the destination lab.")
    spec = TableSpec(
        table="ASSET_TRANSFER", pk="Transfer_ID", title="Transfer",
        label_sql="COALESCE(Transfer_Date, '') || ' · ' || Status || ' · ' || "
                  "(SELECT Equipment_Name FROM EQUIPMENT e WHERE e.Equipment_ID = ASSET_TRANSFER.Equipment_ID)",
        columns=[
            Col("Equipment_ID", "Equipment", kind="fk", fk_sql=EQUIPMENT_FK, required=True),
            Col("Transfer_Date", kind="date", required=True),
            Col("From_Lab_ID", "From lab", kind="fk", fk_sql=LAB_FK, required=True),
            Col("To_Lab_ID", "To lab", kind="fk", fk_sql=LAB_FK, required=True),
            Col("Approved_By", rule="person"),
            Col("Technician_Name", rule="person"),
            Col("Status", kind="select", options=["PENDING", "APPROVED", "COMPLETED", "REJECTED"], required=True,
                default="PENDING"),
            Col("Reason", kind="textarea"),
        ],
        view_sql="""SELECT t.Transfer_ID, t.Transfer_Date, e.Equipment_Name, fl.Lab_Name AS From_Lab,
                    tl.Lab_Name AS To_Lab, t.Status, t.Reason, t.Approved_By, t.Technician_Name
                    FROM ASSET_TRANSFER t JOIN EQUIPMENT e ON e.Equipment_ID = t.Equipment_ID
                    JOIN LABORATORY fl ON fl.Lab_ID = t.From_Lab_ID JOIN LABORATORY tl ON tl.Lab_ID = t.To_Lab_ID
                    ORDER BY t.Transfer_Date DESC""",
        filters=["Status", "From_Lab", "To_Lab"],
        validate=_transfer_validate,
        after_save=_transfer_after_save,
    )
    render_crud(_manage_flags(spec))


# ---------------------------------------------------------------------------
# Warranty
# ---------------------------------------------------------------------------
def _warranty_validate(values, mode, old, conn):
    s, e = values.get("Warranty_Start_Date"), values.get("Warranty_End_Date")
    if s and e and e < s:
        return ["Warranty end date must be on or after the start date."]
    return []


def _warranty_prepare(values, extra, mode, old):
    if values.get("Warranty_End_Date") and values["Warranty_End_Date"] < today_str():
        values["Warranty_Status"] = "EXPIRED"


def warranty():
    header("🛡 Warranty", "Equipment is covered by Warranty (1:1) · Vendor provides Warranty. Status switches to "
                         "EXPIRED automatically once the end date passes.")
    spec = TableSpec(
        table="WARRANTY", pk="Warranty_ID", title="Warranty",
        label_sql="(SELECT Equipment_Name FROM EQUIPMENT e WHERE e.Equipment_ID = WARRANTY.Equipment_ID) "
                  "|| ' · until ' || COALESCE(Warranty_End_Date, '?')",
        columns=[
            Col("Equipment_ID", "Equipment", kind="fk", fk_sql=EQUIPMENT_FK, required=True,
                help="Each equipment item can have only one warranty (1:1)."),
            Col("Vendor_ID", "Vendor", kind="fk", fk_sql=VENDOR_FK),
            Col("Warranty_Start_Date", kind="date", required=True),
            Col("Warranty_End_Date", kind="date", required=True),
            Col("Warranty_Status", "Status", kind="select", options=["ACTIVE", "EXPIRED"], required=True,
                default="ACTIVE"),
        ],
        view_sql="""SELECT w.Warranty_ID, e.Equipment_Name, e.Serial_Number, v.Vendor_Name, w.Warranty_Start_Date,
                    w.Warranty_End_Date, w.Warranty_Status,
                    CAST(julianday(w.Warranty_End_Date) - julianday(date('now', 'localtime')) AS INTEGER) AS Days_Left
                    FROM WARRANTY w JOIN EQUIPMENT e ON e.Equipment_ID = w.Equipment_ID
                    LEFT JOIN VENDOR v ON v.Vendor_ID = w.Vendor_ID ORDER BY w.Warranty_End_Date""",
        filters=["Warranty_Status", "Vendor_Name"],
        validate=_warranty_validate,
        prepare=_warranty_prepare,
        extra_tabs=[("⏰ Expiring soon", lambda: _alert_tables([
            (f"Expiring in the next {alerts.WARRANTY_WINDOW_DAYS} days", alerts.expiring_warranties(),
             "No warranties expire in the next 60 days.", "warranty_exp")]))],
    )
    render_crud(_manage_flags(spec))


# ---------------------------------------------------------------------------
# Consumables
# ---------------------------------------------------------------------------
def _stock_tab():
    low = alerts.low_stock()
    st.subheader("Low-stock items")
    if low.empty:
        st.success("All consumables are above their reorder level.")
    else:
        st.warning(f"{len(low)} item(s) at or below the reorder level.", icon="⚠️")
        render_table(low, "low_stock", file_name="low_stock.csv", search=False)
    if not can_manage():
        return
    st.subheader("Stock movement")
    items = query_df("SELECT Consumable_ID, Item_Name, Quantity, Unit, Reorder_Level, Lab_ID FROM CONSUMABLE "
                     "ORDER BY Item_Name")
    if items.empty:
        return
    labels = {r.Consumable_ID: f"{r.Item_Name} — {r.Quantity:g} {r.Unit or ''}" for r in items.itertuples()}
    c1, c2, c3 = st.columns([3, 1, 1])
    cid = c1.selectbox("Item", list(labels), format_func=labels.get, key="stock_item")
    direction = c2.radio("Movement", ["Issue (−)", "Receive (+)"], key="stock_dir")
    qty = c3.number_input("Quantity", min_value=0.0, step=1.0, key="stock_qty")
    if st.button("Apply movement", type="primary", disabled=qty <= 0):
        item = items[items.Consumable_ID == cid].iloc[0]
        delta = qty if direction.startswith("Receive") else -qty
        new_qty = float(item.Quantity) + delta
        if new_qty < 0:
            st.error(f"Only {item.Quantity:g} {item.Unit or ''} in stock — cannot issue {qty:g}.")
            return
        try:
            with transaction() as conn:
                conn.execute("UPDATE CONSUMABLE SET Quantity = ? WHERE Consumable_ID = ?", (new_qty, cid))
                log_action("STOCK " + ("RECEIVE" if delta > 0 else "ISSUE"),
                           f"Consumable_ID={cid} ({item.Item_Name}): {item.Quantity:g} → {new_qty:g}", conn=conn)
            flash("success", f"{item.Item_Name}: stock is now {new_qty:g} {item.Unit or ''}.")
            if new_qty <= float(item.Reorder_Level):
                flash("warning", f"{item.Item_Name} is at or below its reorder level ({item.Reorder_Level:g}).")
                alerts.generate_notifications()
            st.rerun()
        except Exception as exc:
            st.error(friendly_error(exc))


def consumables():
    header("📦 Consumables", "Laboratory stores Consumable. Items at or below their reorder level raise a "
                            "low-stock alert.")
    spec = TableSpec(
        table="CONSUMABLE", pk="Consumable_ID", title="Consumable",
        label_sql="Item_Name || ' (' || Quantity || ' ' || COALESCE(Unit, '') || ')'",
        columns=[
            Col("Item_Name", required=True, rule="title"),
            Col("Category", kind="select", options=["Chemical", "Glassware", "Electronic Component", "Cable",
                                                    "Safety Supply", "Stationery", "Biological", "Other"]),
            Col("Unit", kind="select", options=["pcs", "box", "pack", "L", "mL", "kg", "g", "m", "roll"]),
            Col("Lab_ID", "Laboratory", kind="fk", fk_sql=LAB_FK),
            Col("Quantity", kind="float", min_value=0, required=True),
            Col("Reorder_Level", kind="float", min_value=0, required=True),
        ],
        view_sql="""SELECT c.Consumable_ID, c.Item_Name, c.Category, c.Quantity, c.Unit, c.Reorder_Level,
                    l.Lab_Name, CASE WHEN c.Quantity <= c.Reorder_Level THEN 'LOW STOCK' ELSE 'OK' END AS Stock_Status
                    FROM CONSUMABLE c LEFT JOIN LABORATORY l ON l.Lab_ID = c.Lab_ID ORDER BY c.Item_Name""",
        filters=["Stock_Status", "Category", "Lab_Name"],
        extra_tabs=[("⚠️ Low stock & movements", _stock_tab)],
        tabs_first=True,
    )
    render_crud(_manage_flags(spec))
