"""Dashboard: availability, utilization, maintenance and inventory insights."""
import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

import alerts
from auth import current_user, is_admin
from crud import render_table, show_flash
from db import query_df, scalar
from views.bookings import parse_slot
from views.theme import (BOOKING_STATUS_COLORS, EQUIPMENT_STATUS_COLORS, MAINTENANCE_TYPE_COLORS, SERIES,
                         style_fig)

WORK_HOURS_PER_DAY = 10  # bookable window 08:00-18:00
PERIODS = {"Last 30 days": 30, "Last 90 days": 90, "Last 6 months": 182, "Last 12 months": 365}


def _slot_hours(slot):
    span = parse_slot(slot)
    return (span[1] - span[0]) / 60 if span else 0


def _tile(col, label, value, note=None, alert=False):
    with col:
        with st.container(border=True):
            st.metric(label, value)
            if note:
                st.caption(f":red[{note}]" if alert else note)


def _df_or(df, message):
    if df.empty:
        st.success(message)
    else:
        st.dataframe(df, hide_index=True)


def _alerts_block():
    om, oc = alerts.overdue_maintenance(), alerts.overdue_calibration()
    dm, dc = alerts.due_maintenance(), alerts.due_calibration()
    ls, ew = alerts.low_stock(), alerts.expiring_warranties()
    tabs = st.tabs([f"🔴 Overdue maintenance ({len(om)})", f"🔴 Overdue calibration ({len(oc)})",
                    f"🟠 Due in 30 days ({len(dm) + len(dc)})", f"🟠 Low stock ({len(ls)})",
                    f"🟡 Warranties expiring ({len(ew)})"])
    with tabs[0]:
        _df_or(om, "No overdue maintenance.")
    with tabs[1]:
        _df_or(oc, "No overdue calibrations.")
    with tabs[2]:
        if dm.empty and dc.empty:
            st.success("Nothing due in the next 30 days.")
        if not dm.empty:
            st.markdown("**Maintenance**")
            st.dataframe(dm, hide_index=True)
        if not dc.empty:
            st.markdown("**Calibration**")
            st.dataframe(dc, hide_index=True)
    with tabs[3]:
        _df_or(ls, "All stock levels healthy.")
    with tabs[4]:
        _df_or(ew, "No warranties expiring in 60 days.")
    return len(om) + len(oc), len(ls)


def page():
    show_flash()
    user = current_user()
    top_l, top_r = st.columns([3, 1])
    top_l.title("📊 Dashboard")
    top_l.caption(f"Welcome back, {user['Full_Name']} · {user['Role_Name']} · {dt.date.today():%A, %d %B %Y}")
    period_name = top_r.selectbox("Analysis period", list(PERIODS), index=1, key="dash_period")
    days = PERIODS[period_name]
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    today = dt.date.today().isoformat()

    equipment = query_df("""SELECT e.Equipment_ID, e.Equipment_Name, e.Equipment_Type, e.Equipment_Status,
                            COALESCE(l.Lab_Name, 'Unassigned') AS Lab_Name, c.Category_Name
                            FROM EQUIPMENT e LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID
                            LEFT JOIN EQUIPMENT_CATEGORY c ON c.Category_ID = e.Category_ID""")
    bookings = query_df("""SELECT b.Booking_ID, b.Booking_Date, b.Time_Slot, b.Booking_Status, b.Equipment_ID
                           FROM EQUIPMENT_BOOKING b WHERE b.Booking_Date BETWEEN ? AND ?""", (since, today))
    maint = query_df("""SELECT Maintenance_Date, Maintenance_Type, Cost, Status FROM MAINTENANCE
                        WHERE Maintenance_Date BETWEEN ? AND ?""", (since, today))
    pending = scalar("SELECT COUNT(*) FROM EQUIPMENT_BOOKING WHERE Booking_Status = 'PENDING' AND Booking_Date >= ?",
                     (today,))
    upcoming = scalar("SELECT COUNT(*) FROM EQUIPMENT_BOOKING WHERE Booking_Status = 'APPROVED' AND Booking_Date >= ?",
                      (today,))

    total = len(equipment)
    status_counts = equipment.Equipment_Status.value_counts()
    available = int(status_counts.get("AVAILABLE", 0))
    servicing = int(status_counts.get("UNDER_MAINTENANCE", 0) + status_counts.get("UNDER_CALIBRATION", 0))
    used = bookings[bookings.Booking_Status.isin(["APPROVED", "COMPLETED"])].copy()
    used["Hours"] = used.Time_Slot.map(_slot_hours)
    overdue_n = len(alerts.overdue_maintenance()) + len(alerts.overdue_calibration())
    low_n = len(alerts.low_stock())

    # ---- KPI tiles ---------------------------------------------------------
    k = st.columns(4)
    _tile(k[0], "Total equipment", total, f"{int(status_counts.get('RETIRED', 0))} retired")
    _tile(k[1], "Available now", available, f"{available / total:.0%} of fleet" if total else None)
    _tile(k[2], "In maintenance / calibration", servicing, "out of service temporarily")
    _tile(k[3], "Overdue service items", overdue_n, "needs action" if overdue_n else "all on schedule",
          alert=overdue_n > 0)
    k = st.columns(4)
    _tile(k[0], f"Bookings ({period_name.lower()})", len(bookings), f"{len(used)} approved / completed")
    _tile(k[1], "Pending approvals", pending, f"{upcoming} approved upcoming")
    _tile(k[2], "Low-stock consumables", low_n, "reorder now" if low_n else "stock healthy", alert=low_n > 0)
    _tile(k[3], "Maintenance spend", f"{maint.Cost.fillna(0).sum():,.2f}", f"{len(maint)} jobs in period")

    st.divider()

    # ---- Availability ------------------------------------------------------
    st.subheader("Equipment availability")
    c1, c2 = st.columns(2)
    with c1:
        sc = (status_counts.rename_axis("Status").reset_index(name="Items")
              .sort_values("Items", ascending=True))
        fig = px.bar(sc, x="Items", y="Status", orientation="h", color="Status", text="Items",
                     color_discrete_map=EQUIPMENT_STATUS_COLORS, title="By status")
        fig.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(style_fig(fig, legend=False), key="dash_status")
    with c2:
        by_lab = equipment.groupby(["Lab_Name", "Equipment_Status"]).size().reset_index(name="Items")
        order = equipment.Lab_Name.value_counts().index.tolist()
        fig = px.bar(by_lab, x="Lab_Name", y="Items", color="Equipment_Status", title="By laboratory",
                     color_discrete_map=EQUIPMENT_STATUS_COLORS, category_orders={"Lab_Name": order})
        st.plotly_chart(style_fig(fig), key="dash_lab")

    # ---- Utilization -------------------------------------------------------
    st.subheader("Resource utilization")
    working_days = max(1, sum(1 for i in range(days) if (dt.date.today() - dt.timedelta(days=i)).weekday() < 5))
    capacity = working_days * WORK_HOURS_PER_DAY
    util = (equipment[equipment.Equipment_Status != "RETIRED"][["Equipment_ID", "Equipment_Name", "Lab_Name",
                                                               "Equipment_Type"]]
            .merge(used.groupby("Equipment_ID").agg(Bookings=("Booking_ID", "count"), Hours=("Hours", "sum"))
                   .reset_index(), on="Equipment_ID", how="left")
            .fillna({"Bookings": 0, "Hours": 0}))
    util["Utilization"] = util.Hours / capacity
    avg_util = util.Utilization.mean() if not util.empty else 0
    idle = util[util.Bookings == 0]
    u = st.columns(3)
    _tile(u[0], "Average utilization", f"{avg_util:.1%}",
          f"booked hours ÷ {capacity} bookable hours ({working_days} working days × {WORK_HOURS_PER_DAY} h)")
    _tile(u[1], "Booked hours", f"{util.Hours.sum():,.0f} h", "approved and completed bookings")
    _tile(u[2], "Idle equipment", len(idle), "no bookings in period", alert=len(idle) > 0)

    c1, c2 = st.columns([3, 2])
    with c1:
        top = util.sort_values("Hours", ascending=False).head(10).sort_values("Hours")
        fig = px.bar(top, x="Hours", y="Equipment_Name", orientation="h", text="Bookings",
                     title="Most used equipment (booked hours; label = bookings)",
                     hover_data={"Lab_Name": True, "Utilization": ":.1%"})
        fig.update_traces(marker_color=SERIES[0], textposition="outside", cliponaxis=False)
        st.plotly_chart(style_fig(fig, height=380, legend=False), key="dash_top")
    with c2:
        st.markdown("**Least used & idle equipment**")
        least = util.sort_values(["Hours", "Equipment_Name"]).head(10)
        st.dataframe(least[["Equipment_Name", "Bookings", "Utilization"]], hide_index=True,
                     height=350, column_config={"Utilization": st.column_config.ProgressColumn(
                         "Utilization", format="percent", min_value=0, max_value=1)})

    c1, c2 = st.columns([3, 2])
    with c1:
        if bookings.empty:
            st.info("No bookings in this period.")
        else:
            b = bookings.copy()
            b["Week"] = pd.to_datetime(b.Booking_Date).dt.to_period("W").dt.start_time
            this_week = pd.Timestamp(dt.date.today()).to_period("W").start_time
            weekly = b[b.Week < this_week].groupby("Week").size().reset_index(name="Bookings")
            fig = px.line(weekly, x="Week", y="Bookings", markers=True,
                          title="Bookings per week (complete weeks)")
            fig.update_traces(line_color=SERIES[0], marker_color=SERIES[0])
            st.plotly_chart(style_fig(fig, legend=False), key="dash_trend")
    with c2:
        bs = bookings.Booking_Status.value_counts().rename_axis("Status").reset_index(name="Bookings")
        fig = px.bar(bs, x="Status", y="Bookings", color="Status", text="Bookings", title="Booking outcomes",
                     color_discrete_map=BOOKING_STATUS_COLORS)
        fig.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(style_fig(fig, legend=False), key="dash_bstatus")

    # ---- Maintenance -------------------------------------------------------
    st.subheader("Maintenance & calibration")
    c1, c2 = st.columns([3, 2])
    with c1:
        if maint.empty:
            st.info("No maintenance in this period.")
        else:
            m = maint.copy()
            m["Month"] = pd.to_datetime(m.Maintenance_Date).dt.to_period("M").dt.start_time
            monthly = m.groupby(["Month", "Maintenance_Type"]).Cost.sum().reset_index()
            fig = px.bar(monthly, x="Month", y="Cost", color="Maintenance_Type", title="Maintenance cost per month",
                         color_discrete_map=MAINTENANCE_TYPE_COLORS)
            fig.update_xaxes(dtick="M1", tickformat="%b %Y")
            st.plotly_chart(style_fig(fig), key="dash_cost")
    with c2:
        types = equipment.Equipment_Type.value_counts().rename_axis("Type").reset_index(name="Items")
        fig = px.bar(types.sort_values("Items"), x="Items", y="Type", orientation="h", text="Items",
                     title="Fleet by equipment subtype")
        fig.update_traces(marker_color=SERIES[0], textposition="outside", cliponaxis=False)
        st.plotly_chart(style_fig(fig, legend=False), key="dash_types")

    st.subheader("Action items")
    _alerts_block()

    if is_admin():
        st.subheader("Recent activity")
        recent = query_df("""SELECT a.Date_Time, COALESCE(u.Full_Name, '—') AS User, a.Action_Performed, a.Remarks
                             FROM AUDIT_LOG a LEFT JOIN LAB_USER u ON u.User_ID = a.User_ID
                             ORDER BY a.Date_Time DESC, a.Log_ID DESC LIMIT 10""")
        st.dataframe(recent, hide_index=True)

    with st.expander("Export utilization report"):
        render_table(util.assign(Utilization=util.Utilization.round(4)), "dash_util", ["Lab_Name", "Equipment_Type"],
                     f"utilization_{since}_{today}.csv")
