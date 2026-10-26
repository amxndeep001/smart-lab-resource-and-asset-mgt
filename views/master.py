"""Master data: organisations, departments, laboratories, roles, vendors, equipment categories."""
from auth import can_manage, is_admin
from crud import Col, TableSpec, render_crud
from views.common import DEPT_FK, ORG_FK, contact_errors, header, read_only_note

STATUS = ["ACTIVE", "INACTIVE"]


def _permissions(spec, allowed):
    spec.can_add = spec.can_edit = spec.can_delete = allowed
    if not allowed:
        read_only_note()
    return spec


def organizations():
    header("🏛 Organizations", "Top of the hierarchy: Organization has Department.")
    spec = TableSpec(
        table="ORGANIZATION", pk="Organization_ID", title="Organization", label_sql="Organization_Name",
        columns=[
            Col("Organization_Name", required=True, rule="title"),
            Col("Organization_Type", kind="select", options=["University", "Research Institute", "College",
                                                              "Hospital", "Private Lab", "Government"]),
            Col("Contact_Email"),
            Col("Contact_Number"),
            Col("Address", kind="textarea"),
        ],
        view_sql="""SELECT o.*, (SELECT COUNT(*) FROM DEPARTMENT d WHERE d.Organization_ID = o.Organization_ID)
                    AS Departments FROM ORGANIZATION o ORDER BY o.Organization_ID""",
        filters=["Organization_Type"],
        validate=lambda v, m, o, c: contact_errors(v, ["Contact_Email"], ["Contact_Number"]),
    )
    render_crud(_permissions(spec, is_admin()))


def departments():
    header("🏢 Departments", "Organization has Department · Department contains Laboratory and User.")
    spec = TableSpec(
        table="DEPARTMENT", pk="Department_ID", title="Department", label_sql="Department_Name",
        columns=[
            Col("Department_Name", required=True, rule="title"),
            Col("Organization_ID", "Organization", kind="fk", fk_sql=ORG_FK, required=True),
            Col("HOD_Name", "HOD name", rule="person"),
            Col("Building_Name", rule="title"),
            Col("Contact_Number"),
            Col("Status", kind="select", options=STATUS, required=True, default="ACTIVE"),
        ],
        view_sql="""SELECT d.Department_ID, d.Department_Name, o.Organization_Name, d.HOD_Name, d.Building_Name,
                    d.Contact_Number, d.Status,
                    (SELECT COUNT(*) FROM LABORATORY l WHERE l.Department_ID = d.Department_ID) AS Labs,
                    (SELECT COUNT(*) FROM LAB_USER u WHERE u.Department_ID = d.Department_ID) AS Users
                    FROM DEPARTMENT d JOIN ORGANIZATION o ON o.Organization_ID = d.Organization_ID
                    ORDER BY d.Department_ID""",
        filters=["Organization_Name", "Status"],
        validate=lambda v, m, o, c: contact_errors(v, [], ["Contact_Number"]),
    )
    render_crud(_permissions(spec, can_manage()))


def laboratories():
    header("🧪 Laboratories", "Department contains Laboratory · Laboratory houses Equipment and stores Consumables.")
    spec = TableSpec(
        table="LABORATORY", pk="Lab_ID", title="Laboratory", label_sql="Lab_Name",
        columns=[
            Col("Lab_Name", required=True, rule="title"),
            Col("Department_ID", "Department", kind="fk", fk_sql=DEPT_FK, required=True),
            Col("Capacity", kind="int", min_value=1, help="Seating / working capacity (must be > 0)"),
            Col("Location", rule="title"),
            Col("Lab_Incharge", "Lab in-charge", rule="person"),
        ],
        view_sql="""SELECT l.Lab_ID, l.Lab_Name, d.Department_Name, l.Capacity, l.Location, l.Lab_Incharge,
                    (SELECT COUNT(*) FROM EQUIPMENT e WHERE e.Lab_ID = l.Lab_ID) AS Equipment_Count,
                    (SELECT COUNT(*) FROM CONSUMABLE c WHERE c.Lab_ID = l.Lab_ID) AS Consumable_Items
                    FROM LABORATORY l JOIN DEPARTMENT d ON d.Department_ID = l.Department_ID ORDER BY l.Lab_ID""",
        filters=["Department_Name"],
    )
    render_crud(_permissions(spec, can_manage()))


def roles():
    header("🎭 Roles", "Role is assigned to User. Access level drives permissions: "
                       "5 = administrator, 3–4 = manage assets, 1–2 = view and book.")
    spec = TableSpec(
        table="ROLE", pk="Role_ID", title="Role", label_sql="Role_Name",
        columns=[
            Col("Role_Name", required=True, rule="title"),
            Col("Access_Level", kind="int", min_value=1, max_value=5, required=True, default=1),
            Col("Created_Date", kind="date", required=True),
            Col("Status", kind="select", options=STATUS, required=True, default="ACTIVE"),
        ],
        view_sql="""SELECT r.*, (SELECT COUNT(*) FROM LAB_USER u WHERE u.Role_ID = r.Role_ID) AS Users
                    FROM ROLE r ORDER BY r.Access_Level DESC""",
        filters=["Status"],
    )
    render_crud(_permissions(spec, is_admin()))


def vendors():
    header("🚚 Vendors", "Vendor supplies Equipment · Vendor provides Warranty.")
    spec = TableSpec(
        table="VENDOR", pk="Vendor_ID", title="Vendor", label_sql="Vendor_Name",
        columns=[
            Col("Vendor_Name", required=True, rule="title"),
            Col("Contact_Person", rule="person"),
            Col("Phone_Number"),
            Col("Email"),
            Col("Address", kind="textarea"),
        ],
        view_sql="""SELECT v.*, (SELECT COUNT(*) FROM EQUIPMENT e WHERE e.Vendor_ID = v.Vendor_ID) AS Equipment_Supplied,
                    (SELECT COUNT(*) FROM WARRANTY w WHERE w.Vendor_ID = v.Vendor_ID) AS Warranties
                    FROM VENDOR v ORDER BY v.Vendor_ID""",
        validate=lambda v, m, o, c: contact_errors(v, ["Email"], ["Phone_Number"]),
    )
    render_crud(_permissions(spec, can_manage()))


def categories():
    header("🗂 Equipment Categories", "Equipment Category classifies Equipment.")
    spec = TableSpec(
        table="EQUIPMENT_CATEGORY", pk="Category_ID", title="Category", label_sql="Category_Name",
        columns=[
            Col("Category_Name", required=True, rule="title"),
            Col("Safety_Level", kind="select", options=["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
            Col("Storage_Requirement", rule="title"),
            Col("Status", kind="select", options=STATUS, default="ACTIVE"),
            Col("Description", kind="textarea"),
        ],
        view_sql="""SELECT c.*, (SELECT COUNT(*) FROM EQUIPMENT e WHERE e.Category_ID = c.Category_ID) AS Equipment_Count
                    FROM EQUIPMENT_CATEGORY c ORDER BY c.Category_ID""",
        filters=["Safety_Level", "Status"],
    )
    render_crud(_permissions(spec, can_manage()))
