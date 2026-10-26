# Smart Laboratory Resource and Asset Management System

A Streamlit web app for the **Database Modelling and Design (MACSE518)** course project. It implements the
relational schema from the ER / EER / normalization assessments: 16 core tables plus the EER subclass tables.
It has a login page, full CRUD for every entity and a dashboard with operational insights.

## Setup

Requires Python 3.9 or newer (developed on 3.9 and Streamlit 1.50).

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python seed.py                  # optional: (re)build data/smart_lab.db with fresh sample data
streamlit run app.py
```

On first launch, if `data/smart_lab.db` does not exist, the app creates the schema and loads the sample data
itself. Run `python seed.py` at any time to reset everything. Sample dates are relative to today, so overdue
and due-soon items always show up.

### Sign in

Only **administrator** accounts can sign in: role access level 5, or a user with the ADMINISTRATOR subtype.
Other users (lab managers, technicians, faculty, researchers) are records that the administrator manages.
Their sign-in attempts are refused and logged as `LOGIN_DENIED` in the audit log.

| Account | Name | Password |
|---|---|---|
| `admin@smartlab.edu` | Jyotsna | `lab12345` |

To let another person sign in, open **Users**, then **Edit / Delete**, and give them the Administrator role
or the ADMINISTRATOR subtype.

## Project structure

```
app.py              entry point: login page, role-based navigation (st.navigation)
db.py               SQLite connections (PRAGMA foreign_keys = ON), audit logging, friendly constraint errors
crud.py             generic metadata-driven CRUD engine (View / Add / Edit-Delete tabs, CSV export)
auth.py             bcrypt hashing, login/logout, access levels
alerts.py           overdue / due-soon / low-stock / warranty queries and automatic notifications
seed.py             schema creation and sample data
schema_sqlite.sql   DDL used by the app
schema_mysql.sql    the same DDL for MySQL 8.0.16+ / MySQL Workbench
views/              one module per area: dashboard, equipment, bookings, operations, master, users, activity
```

## How the problem statement maps to features

| Problem / objective | Where it is solved |
|---|---|
| Tracking equipment availability | `EQUIPMENT.Equipment_Status` (CHECK constraint), the **Equipment → Availability** tab, status charts on the dashboard, and the **Bookings → Check availability** tab for a given date and slot |
| Double booking | Bookings for the same equipment and date with overlapping slots (`PENDING`/`APPROVED`) are rejected by the app. Triggers `trg_booking_no_double_*` also block identical slots at the database level |
| Delayed maintenance and calibration | Maintenance and Calibration modules, each with an **Overdue & due soon** tab (next 30 days). Notifications are generated automatically at sign-in. Starting or completing a job updates the equipment status |
| Poor inventory management | Consumables with `Reorder_Level` (the added enhancement), a low-stock tab and alert, and stock issue/receive movements that are audited |
| Loss of asset history | **Equipment → History**: one timeline of purchase, bookings, maintenance, calibration, transfers and warranty. FKs use `ON DELETE RESTRICT`, so history cannot be silently deleted; retire equipment instead |
| Lack of accountability | `AUDIT_LOG` row for every create / update / delete (including field-level before → after changes), every login, failed login and logout. Records user, timestamp, client IP (falls back to `127.0.0.1`) and remarks. Maintenance actions fill `Maintenance_ID` |
| Digitize resource management | Full CRUD for all 16 entities plus the subtype tables |
| Reports and dashboards | Dashboard page; **Export CSV** on every table |
| Resource utilization | Booked hours, utilization % (booked hours ÷ bookable hours), most used, least used and idle equipment; view `V_EQUIPMENT_UTILIZATION` |
| Audit logs | **Audit log** page: read-only, filterable by date, user, action and entity |
| User and role management | Users (with EER subtype assignment) and Roles pages; access level controls navigation and write permissions |

## Database design notes

- **Exact table and column names** from the assessment. `USER` is implemented as `LAB_USER` because `USER` is a reserved word.
- **Named constraints** (`chk_*`, `fk_*`) are translated into readable messages in the UI (`db.friendly_error`).
- **USER specialization (Total + Overlapping):** `ADMINISTRATOR`, `LAB_MANAGER`, `LAB_TECHNICIAN`, `RESEARCHER`
  and `FACULTY` each use `User_ID` as both PK and FK → `LAB_USER` with `ON DELETE CASCADE`. The user form
  requires at least one subtype, allows several, and shows the fields for each selected subtype.
  **Users → Subtype tables** shows each subclass table plus a total-participation check.
  `ADMINISTRATOR.Last_Login` is updated by the login process.
- **EQUIPMENT specialization (Total + Disjoint):** the discriminator is `EQUIPMENT.Equipment_Type` (CHECK constraint).
  Each subtype table has `Equipment_ID` as PK/FK with `ON DELETE CASCADE`. `BEFORE INSERT` triggers reject a
  subtype row whose discriminator does not match (disjointness). When an item's type changes, the app moves
  its subtype row inside the same transaction.
- **WARRANTY** is 1:1 with EQUIPMENT through `UNIQUE (Equipment_ID)`. Its status changes to `EXPIRED` automatically once the end date passes.
- **AUDIT_LOG** FKs use `ON DELETE SET NULL`, so the trail survives when a user or maintenance record is deleted.
- **Automatic state changes:**
  - Maintenance `IN_PROGRESS` → equipment `UNDER_MAINTENANCE`; `COMPLETED` → `AVAILABLE`.
  - Calibration `IN_PROGRESS` → equipment `UNDER_CALIBRATION`; `COMPLETED` → `AVAILABLE`.
  - A transfer marked `COMPLETED` moves the equipment to `To_Lab_ID`.
  - Each of these changes is audited.

### Using the MySQL script

Open `schema_mysql.sql` in MySQL Workbench and run it. It creates the `smart_lab_db` database with the same
tables, constraints, triggers and views. Use **Database → Reverse Engineer** to generate the EER diagram.
The Streamlit app itself runs on SQLite.

## Assumptions to review

- **Equipment subtypes:** the specification was cut off after `COMPUTING_EQUIPMENT:`, so these subtypes and
  attributes were chosen to fit the lab domain:
  - `COMPUTING_EQUIPMENT`: Processor, RAM_GB, Operating_System
  - `ELECTRONIC_EQUIPMENT`: Voltage_Rating, Power_Rating, Frequency_Range
  - `MECHANICAL_EQUIPMENT`: Material, Load_Capacity, Dimensions
  - `MEASURING_INSTRUMENT`: Measurement_Range, Accuracy, Resolution
  - `MEDICAL_EQUIPMENT`: Device_Class (`Class I / IIa / IIb / III`, CHECK constraint), Sterilization_Method,
    Regulatory_Approval

  To match your EER diagram, edit the subtype tables in both schema files, the `chk_equipment_type` list,
  the disjoint triggers, `EQUIPMENT_SUBTYPES` in `views/equipment.py` and the catalog in `seed.py`.
- Calibration status values are `SCHEDULED / IN_PROGRESS / COMPLETED / FAILED`. Role and category status values are `ACTIVE / INACTIVE`.
- Time slots are `HH:MM-HH:MM`. The form offers hourly slots (08:00–18:00) and two-hour blocks.

## Input validation

Text fields that hold names are checked before anything is written to the database (`TEXT_RULES` in `crud.py`):

| Rule | Fields | Allowed |
|---|---|---|
| person | Full name, HOD, lab in-charge, contact person, technician, approved by | letters, spaces, `. ' -`; 2–100 characters |
| title | Organization, department, lab, building, location, role, vendor, category, storage requirement, equipment and consumable names, regulatory approval | starts with a letter or digit, contains a letter; letters, digits, spaces and `& ( ) , . ' / + % -`; 2–120 characters |
| code | Serial number | letters, digits, `-` and `/`; 3–40 characters; stored in upper case |

Emails and phone numbers have their own format checks. Numeric ranges, dates and status values are enforced
by both the form and the database CHECK constraints.

## Schema migrations

On startup, `db.migrate()` upgrades an existing database to the current schema: for example, the MEDICAL
equipment type was added after the first release. Before changing anything it saves a timestamped backup next
to the database (`data/smart_lab.backup-*.db`). A fresh database from `python seed.py` needs no migration.

## Out of scope (project limitations)

IoT integration, predictive maintenance, a mobile app and advanced security (beyond bcrypt-hashed passwords
and simple role-based access) are intentionally not implemented.
