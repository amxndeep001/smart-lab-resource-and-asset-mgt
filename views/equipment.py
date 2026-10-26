"""Equipment (Total + Disjoint specialization) and the per-asset history timeline."""
import plotly.express as px
import streamlit as st

from auth import can_manage
from crud import Col, TableSpec, render_crud, render_fields, render_table, rule_errors
from db import query_df, query_one, today_str
from views.common import CATEGORY_FK, LAB_FK, VENDOR_FK, header, read_only_note
from views.theme import EVENT_COLORS, style_fig

EQUIPMENT_STATUS = ["AVAILABLE", "IN_USE", "UNDER_MAINTENANCE", "UNDER_CALIBRATION", "RETIRED"]

# Equipment_Type value -> (subtype table, label, subtype columns)
EQUIPMENT_SUBTYPES = {
    "COMPUTING": ("COMPUTING_EQUIPMENT", "Computing equipment", [
        Col("Processor"), Col("RAM_GB", "RAM (GB)", kind="int", min_value=1), Col("Operating_System")]),
    "ELECTRONIC": ("ELECTRONIC_EQUIPMENT", "Electronic equipment", [
        Col("Voltage_Rating"), Col("Power_Rating"), Col("Frequency_Range")]),
    "MECHANICAL": ("MECHANICAL_EQUIPMENT", "Mechanical equipment", [
        Col("Material"), Col("Load_Capacity"), Col("Dimensions")]),
    "MEASURING": ("MEASURING_INSTRUMENT", "Measuring instrument", [
        Col("Measurement_Range"), Col("Accuracy"), Col("Resolution")]),
    "MEDICAL": ("MEDICAL_EQUIPMENT", "Medical equipment", [
        Col("Device_Class", kind="select", options=["Class I", "Class IIa", "Class IIb", "Class III"],
            help="Regulatory risk class (Class III = highest risk)"),
        Col("Sterilization_Method", kind="select",
            options=["Autoclave (steam)", "Ethylene oxide", "UV", "Chemical disinfection", "Not required"]),
        Col("Regulatory_Approval", rule="title", help="e.g. CDSCO, CE, FDA 510(k)")]),
}

VIEW_SQL = """
SELECT e.Equipment_ID, e.Equipment_Name, e.Serial_Number, e.Equipment_Type, e.Equipment_Status,
       l.Lab_Name, c.Category_Name, v.Vendor_Name, e.Purchase_Date,
       CASE e.Equipment_Type
         WHEN 'COMPUTING' THEN 'CPU ' || IFNULL(ce.Processor, '—') || ', ' || IFNULL(ce.RAM_GB || ' GB', '—')
                               || ', ' || IFNULL(ce.Operating_System, '—')
         WHEN 'ELECTRONIC' THEN IFNULL(ee.Voltage_Rating, '—') || ', ' || IFNULL(ee.Power_Rating, '—')
                               || ', ' || IFNULL(ee.Frequency_Range, '—')
         WHEN 'MECHANICAL' THEN IFNULL(me.Material, '—') || ', load ' || IFNULL(me.Load_Capacity, '—')
                               || ', ' || IFNULL(me.Dimensions, '—')
         WHEN 'MEASURING' THEN 'Range ' || IFNULL(mi.Measurement_Range, '—') || ', accuracy '
                               || IFNULL(mi.Accuracy, '—') || ', res. ' || IFNULL(mi.Resolution, '—')
         WHEN 'MEDICAL' THEN IFNULL(md.Device_Class, '—') || ', ' || IFNULL(md.Sterilization_Method, '—')
                               || ', ' || IFNULL(md.Regulatory_Approval, '—')
       END AS Subtype_Details
FROM EQUIPMENT e
LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID
LEFT JOIN EQUIPMENT_CATEGORY c ON c.Category_ID = e.Category_ID
LEFT JOIN VENDOR v ON v.Vendor_ID = e.Vendor_ID
LEFT JOIN COMPUTING_EQUIPMENT ce ON ce.Equipment_ID = e.Equipment_ID
LEFT JOIN ELECTRONIC_EQUIPMENT ee ON ee.Equipment_ID = e.Equipment_ID
LEFT JOIN MECHANICAL_EQUIPMENT me ON me.Equipment_ID = e.Equipment_ID
LEFT JOIN MEASURING_INSTRUMENT mi ON mi.Equipment_ID = e.Equipment_ID
LEFT JOIN MEDICAL_EQUIPMENT md ON md.Equipment_ID = e.Equipment_ID
ORDER BY e.Equipment_ID DESC"""


def _subtype_form(mode, record, values, key):
    etype = values.get("Equipment_Type")
    if not etype:
        return {}
    table, label, cols = EQUIPMENT_SUBTYPES[etype]
    st.markdown(f"**{label} details** · stored in `{table}` (disjoint subtype)")
    existing = query_one(f"SELECT * FROM {table} WHERE Equipment_ID = ?", (record["Equipment_ID"],)) \
        if record else None
    return {"type": etype, "data": render_fields(cols, existing, f"{key}_{etype}", ncols=3)}


def _save_subtype(conn, equipment_id, values, extra, mode, old):
    etype = values["Equipment_Type"]
    # Disjoint: remove any row in the other subtype tables, then upsert the matching one.
    for t, (table, _, _) in EQUIPMENT_SUBTYPES.items():
        if t != etype:
            conn.execute(f"DELETE FROM {table} WHERE Equipment_ID = ?", (equipment_id,))
    table, _, cols = EQUIPMENT_SUBTYPES[etype]
    data = extra.get("data", {})
    names = ["Equipment_ID"] + [c.name for c in cols]
    conn.execute(f"INSERT OR REPLACE INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
                 [equipment_id] + [data.get(c.name) for c in cols])


def _validate_subtype(extra, mode):
    if not extra.get("type"):
        return []
    return rule_errors(EQUIPMENT_SUBTYPES[extra["type"]][2], extra.get("data", {}))


def _validate(values, mode, old, conn):
    errors = []
    if values.get("Purchase_Date") and values["Purchase_Date"] > today_str():
        errors.append("Purchase date cannot be in the future.")
    return errors


def _availability_tab():
    st.subheader("Equipment availability")
    df = query_df("""SELECT e.Equipment_Status AS Status, COUNT(*) AS Items FROM EQUIPMENT e
                     GROUP BY e.Equipment_Status""")
    cols = st.columns(len(EQUIPMENT_STATUS))
    counts = dict(zip(df.Status, df.Items))
    for c, s in zip(cols, EQUIPMENT_STATUS):
        c.metric(s.replace("_", " ").title(), counts.get(s, 0))
    status = st.multiselect("Show equipment with status", EQUIPMENT_STATUS, default=["AVAILABLE"],
                            key="eq_avail_status")
    data = query_df(VIEW_SQL)
    if status:
        data = data[data.Equipment_Status.isin(status)]
    render_table(data.drop(columns=["Subtype_Details"]), "eq_avail", ["Lab_Name", "Equipment_Type"],
                 "equipment_availability.csv")


def history_df(equipment_id):
    """One timeline combining every event recorded for an equipment item."""
    return query_df("""
        SELECT Purchase_Date AS Date, 'Purchase' AS Event, 'Purchased · serial ' || Serial_Number AS Details,
               Equipment_Status AS Status
        FROM EQUIPMENT WHERE Equipment_ID = :id AND Purchase_Date IS NOT NULL
        UNION ALL
        SELECT b.Booking_Date, 'Booking', b.Time_Slot || ' by ' || u.Full_Name, b.Booking_Status
        FROM EQUIPMENT_BOOKING b JOIN LAB_USER u ON u.User_ID = b.User_ID WHERE b.Equipment_ID = :id
        UNION ALL
        SELECT Maintenance_Date, 'Maintenance', Maintenance_Type || ' · cost ' || printf('%.2f', COALESCE(Cost, 0)),
               Status
        FROM MAINTENANCE WHERE Equipment_ID = :id
        UNION ALL
        SELECT Calibration_Date, 'Calibration',
               'By ' || COALESCE(Technician_Name, '—') || ' · next due ' || COALESCE(Next_Due_Date, '—'), Status
        FROM CALIBRATION WHERE Equipment_ID = :id
        UNION ALL
        SELECT t.Transfer_Date, 'Transfer', fl.Lab_Name || ' → ' || tl.Lab_Name || COALESCE(' · ' || t.Reason, ''),
               t.Status
        FROM ASSET_TRANSFER t JOIN LABORATORY fl ON fl.Lab_ID = t.From_Lab_ID
        JOIN LABORATORY tl ON tl.Lab_ID = t.To_Lab_ID WHERE t.Equipment_ID = :id
        UNION ALL
        SELECT w.Warranty_Start_Date, 'Warranty', 'Warranty starts · ' || COALESCE(v.Vendor_Name, ''), w.Warranty_Status
        FROM WARRANTY w LEFT JOIN VENDOR v ON v.Vendor_ID = w.Vendor_ID WHERE w.Equipment_ID = :id
        UNION ALL
        SELECT w.Warranty_End_Date, 'Warranty', 'Warranty ends · ' || COALESCE(v.Vendor_Name, ''), w.Warranty_Status
        FROM WARRANTY w LEFT JOIN VENDOR v ON v.Vendor_ID = w.Vendor_ID WHERE w.Equipment_ID = :id
        ORDER BY Date DESC""", {"id": equipment_id})


def _history_tab():
    items = query_df("SELECT Equipment_ID, Equipment_Name, Serial_Number FROM EQUIPMENT ORDER BY Equipment_Name")
    if items.empty:
        st.info("No equipment yet.")
        return
    labels = {r.Equipment_ID: f"{r.Equipment_Name} [{r.Serial_Number}]" for r in items.itertuples()}
    eid = st.selectbox("Equipment", list(labels), format_func=labels.get, key="eq_history_pick")
    info = query_df(VIEW_SQL.replace("ORDER BY e.Equipment_ID DESC", "WHERE e.Equipment_ID = ?"), (eid,)).iloc[0]
    a, b, c, d = st.columns(4)
    a.metric("Status", info.Equipment_Status.replace("_", " ").title())
    b.metric("Type", info.Equipment_Type.title())
    c.metric("Lab", info.Lab_Name or "—")
    d.metric("Vendor", info.Vendor_Name or "—")
    st.caption(f"Category: {info.Category_Name or '—'} · Purchased: {info.Purchase_Date or '—'} · "
               f"{info.Subtype_Details}")

    hist = history_df(eid)
    if hist.empty:
        st.info("No history recorded for this equipment yet.")
        return
    counts = hist.Event.value_counts()
    st.caption(" · ".join(f"{k}: {v}" for k, v in counts.items()))
    events = st.multiselect("Event types", sorted(hist.Event.unique()), default=sorted(hist.Event.unique()),
                            key="eq_history_events")
    hist = hist[hist.Event.isin(events)]
    fig = px.scatter(hist, x="Date", y="Event", color="Event", hover_data=["Details", "Status"],
                     color_discrete_map=EVENT_COLORS)
    fig.update_traces(marker=dict(size=11, line=dict(width=2, color="rgba(255,255,255,0.9)")))
    st.plotly_chart(style_fig(fig, height=300, legend=False), key="eq_history_chart")
    render_table(hist, f"eq_history_{eid}", ["Event", "Status"], f"equipment_{eid}_history.csv", search=True)


def page():
    header("🔬 Equipment", "Laboratory houses Equipment · every item has exactly one subtype "
                          "(Total + Disjoint specialization).")
    manage = can_manage()
    if not manage:
        read_only_note()
    spec = TableSpec(
        table="EQUIPMENT", pk="Equipment_ID", title="Equipment",
        label_sql="Equipment_Name || ' [' || Serial_Number || ']'",
        columns=[
            Col("Equipment_Name", required=True, rule="title"),
            Col("Serial_Number", required=True, rule="code",
                help="Letters, digits, hyphens and slashes; stored in upper case"),
            Col("Equipment_Type", "Equipment type (subtype)", kind="select", required=True,
                options=list(EQUIPMENT_SUBTYPES)),
            Col("Equipment_Status", "Status", kind="select", options=EQUIPMENT_STATUS, required=True,
                default="AVAILABLE"),
            Col("Lab_ID", "Laboratory", kind="fk", fk_sql=LAB_FK),
            Col("Category_ID", "Category", kind="fk", fk_sql=CATEGORY_FK),
            Col("Vendor_ID", "Vendor", kind="fk", fk_sql=VENDOR_FK),
            Col("Purchase_Date", kind="date"),
        ],
        view_sql=VIEW_SQL,
        filters=["Equipment_Status", "Equipment_Type", "Lab_Name"],
        validate=_validate,
        extra_form=_subtype_form,
        validate_extra=_validate_subtype,
        after_save=_save_subtype,
        extra_tabs=[("✅ Availability", _availability_tab), ("🕓 History", _history_tab)],
        can_add=manage, can_edit=manage, can_delete=manage,
    )
    render_crud(spec)
