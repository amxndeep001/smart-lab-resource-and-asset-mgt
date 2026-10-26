"""Shared lookups and small UI helpers for the pages."""
import re

import streamlit as st

ORG_FK = "SELECT Organization_ID AS id, Organization_Name AS label FROM ORGANIZATION ORDER BY label"
DEPT_FK = ("SELECT Department_ID AS id, Department_Name || CASE WHEN Status = 'INACTIVE' THEN ' (inactive)' ELSE '' END "
           "AS label FROM DEPARTMENT ORDER BY Status, Department_Name")
LAB_FK = "SELECT Lab_ID AS id, Lab_Name AS label FROM LABORATORY ORDER BY label"
ROLE_FK = "SELECT Role_ID AS id, Role_Name || ' (level ' || COALESCE(Access_Level, '-') || ')' AS label FROM ROLE ORDER BY Access_Level DESC"
VENDOR_FK = "SELECT Vendor_ID AS id, Vendor_Name AS label FROM VENDOR ORDER BY label"
CATEGORY_FK = "SELECT Category_ID AS id, Category_Name AS label FROM EQUIPMENT_CATEGORY ORDER BY label"
EQUIPMENT_FK = ("SELECT Equipment_ID AS id, Equipment_Name || ' [' || Serial_Number || '] · ' || Equipment_Status "
                "AS label FROM EQUIPMENT ORDER BY Equipment_Name")
USER_FK = "SELECT User_ID AS id, Full_Name || ' <' || Email || '>' AS label FROM LAB_USER ORDER BY Full_Name"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,20}$")


def header(title, caption=None):
    st.title(title)
    if caption:
        st.caption(caption)


def contact_errors(values, email_cols=(), phone_cols=()):
    errors = []
    for c in email_cols:
        if values.get(c) and not EMAIL_RE.match(values[c]):
            errors.append(f"{c.replace('_', ' ')} is not a valid email address.")
    for c in phone_cols:
        if values.get(c) and not PHONE_RE.match(values[c]):
            errors.append(f"{c.replace('_', ' ')} is not a valid phone number.")
    return errors


def read_only_note():
    st.info("Your role has read-only access to this module. Contact a lab manager to make changes.", icon="🔒")
