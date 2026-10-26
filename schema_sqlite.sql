-- =====================================================================
-- Smart Laboratory Resource and Asset Management System
-- SQLite DDL (used by the Streamlit app).  MySQL version: schema_mysql.sql
-- The app runs  PRAGMA foreign_keys = ON  on every connection.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Organisation structure
-- ---------------------------------------------------------------------
CREATE TABLE ORGANIZATION (
    Organization_ID    INTEGER PRIMARY KEY AUTOINCREMENT,
    Organization_Name  VARCHAR(150) NOT NULL,
    Organization_Type  VARCHAR(50),
    Address            VARCHAR(255),
    Contact_Email      VARCHAR(120) UNIQUE,
    Contact_Number     VARCHAR(20)  UNIQUE
);

CREATE TABLE DEPARTMENT (
    Department_ID      INTEGER PRIMARY KEY AUTOINCREMENT,
    Department_Name    VARCHAR(120) NOT NULL,
    HOD_Name           VARCHAR(100),
    Building_Name      VARCHAR(100),
    Contact_Number     VARCHAR(20) UNIQUE,
    Status             VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    Organization_ID    INTEGER NOT NULL,
    CONSTRAINT chk_department_status CHECK (Status IN ('ACTIVE', 'INACTIVE')),
    CONSTRAINT fk_department_org FOREIGN KEY (Organization_ID)
        REFERENCES ORGANIZATION (Organization_ID) ON DELETE RESTRICT
);

CREATE TABLE LABORATORY (
    Lab_ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    Lab_Name           VARCHAR(120) NOT NULL,
    Capacity           INTEGER,
    Location           VARCHAR(150),
    Lab_Incharge       VARCHAR(100),
    Department_ID      INTEGER NOT NULL,
    CONSTRAINT chk_lab_capacity CHECK (Capacity > 0),
    CONSTRAINT fk_lab_department FOREIGN KEY (Department_ID)
        REFERENCES DEPARTMENT (Department_ID) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------------
-- Users, roles and the USER specialization (Total + Overlapping)
-- ---------------------------------------------------------------------
CREATE TABLE ROLE (
    Role_ID            INTEGER PRIMARY KEY AUTOINCREMENT,
    Role_Name          VARCHAR(50) NOT NULL UNIQUE,
    Access_Level       INTEGER,
    Created_Date       DATE,
    Status             VARCHAR(10) DEFAULT 'ACTIVE',
    CONSTRAINT chk_role_access CHECK (Access_Level BETWEEN 1 AND 5),
    CONSTRAINT chk_role_status CHECK (Status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE LAB_USER (
    User_ID            INTEGER PRIMARY KEY AUTOINCREMENT,
    Full_Name          VARCHAR(100) NOT NULL,
    Email              VARCHAR(120) NOT NULL UNIQUE,
    Phone_Number       VARCHAR(20) UNIQUE,
    Password_Hash      VARCHAR(255) NOT NULL,
    Department_ID      INTEGER NOT NULL,
    Role_ID            INTEGER NOT NULL,
    CONSTRAINT fk_user_department FOREIGN KEY (Department_ID)
        REFERENCES DEPARTMENT (Department_ID) ON DELETE RESTRICT,
    CONSTRAINT fk_user_role FOREIGN KEY (Role_ID)
        REFERENCES ROLE (Role_ID) ON DELETE RESTRICT
);

CREATE TABLE ADMINISTRATOR (
    User_ID            INTEGER PRIMARY KEY,
    Admin_Level        VARCHAR(30),
    Permissions        VARCHAR(255),
    Last_Login         DATETIME,
    CONSTRAINT fk_admin_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
);

CREATE TABLE LAB_MANAGER (
    User_ID            INTEGER PRIMARY KEY,
    Office_Room        VARCHAR(30),
    Experience         INTEGER,
    Managed_Labs       VARCHAR(255),
    CONSTRAINT chk_manager_experience CHECK (Experience >= 0),
    CONSTRAINT fk_manager_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
);

CREATE TABLE LAB_TECHNICIAN (
    User_ID            INTEGER PRIMARY KEY,
    Skill_Type         VARCHAR(100),
    Shift_Time         VARCHAR(30),
    Certification      VARCHAR(150),
    CONSTRAINT fk_technician_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
);

CREATE TABLE RESEARCHER (
    User_ID            INTEGER PRIMARY KEY,
    Research_Area      VARCHAR(150),
    Qualification      VARCHAR(100),
    Research_Interest  VARCHAR(255),
    CONSTRAINT fk_researcher_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
);

CREATE TABLE FACULTY (
    User_ID                 INTEGER PRIMARY KEY,
    Department_Affiliation  VARCHAR(120),
    Designation             VARCHAR(80),
    Date_of_Joining         DATE,
    CONSTRAINT fk_faculty_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Suppliers and classification
-- ---------------------------------------------------------------------
CREATE TABLE VENDOR (
    Vendor_ID          INTEGER PRIMARY KEY AUTOINCREMENT,
    Vendor_Name        VARCHAR(120) NOT NULL,
    Contact_Person     VARCHAR(100),
    Phone_Number       VARCHAR(20),
    Email              VARCHAR(120) UNIQUE,
    Address            VARCHAR(255)
);

CREATE TABLE EQUIPMENT_CATEGORY (
    Category_ID          INTEGER PRIMARY KEY AUTOINCREMENT,
    Category_Name        VARCHAR(80) NOT NULL UNIQUE,
    Description          VARCHAR(255),
    Safety_Level         VARCHAR(20),
    Storage_Requirement  VARCHAR(150),
    Status               VARCHAR(10) DEFAULT 'ACTIVE',
    CONSTRAINT chk_category_status CHECK (Status IN ('ACTIVE', 'INACTIVE'))
);

-- ---------------------------------------------------------------------
-- Equipment and the EQUIPMENT specialization (Total + Disjoint)
-- Equipment_Type is the subtype discriminator.
-- ---------------------------------------------------------------------
CREATE TABLE EQUIPMENT (
    Equipment_ID       INTEGER PRIMARY KEY AUTOINCREMENT,
    Equipment_Name     VARCHAR(120) NOT NULL,
    Purchase_Date      DATE,
    Serial_Number      VARCHAR(60) NOT NULL UNIQUE,
    Equipment_Status   VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    Equipment_Type     VARCHAR(20) NOT NULL,
    Lab_ID             INTEGER,
    Category_ID        INTEGER,
    Vendor_ID          INTEGER,
    CONSTRAINT chk_equipment_status CHECK (Equipment_Status IN
        ('AVAILABLE', 'IN_USE', 'UNDER_MAINTENANCE', 'UNDER_CALIBRATION', 'RETIRED')),
    CONSTRAINT chk_equipment_type CHECK (Equipment_Type IN
        ('COMPUTING', 'ELECTRONIC', 'MECHANICAL', 'MEASURING', 'MEDICAL')),
    CONSTRAINT fk_equipment_lab FOREIGN KEY (Lab_ID)
        REFERENCES LABORATORY (Lab_ID) ON DELETE RESTRICT,
    CONSTRAINT fk_equipment_category FOREIGN KEY (Category_ID)
        REFERENCES EQUIPMENT_CATEGORY (Category_ID) ON DELETE RESTRICT,
    CONSTRAINT fk_equipment_vendor FOREIGN KEY (Vendor_ID)
        REFERENCES VENDOR (Vendor_ID) ON DELETE RESTRICT
);

CREATE TABLE COMPUTING_EQUIPMENT (
    Equipment_ID       INTEGER PRIMARY KEY,
    Processor          VARCHAR(80),
    RAM_GB             INTEGER,
    Operating_System   VARCHAR(60),
    CONSTRAINT chk_computing_ram CHECK (RAM_GB > 0),
    CONSTRAINT fk_computing_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
);

CREATE TABLE ELECTRONIC_EQUIPMENT (
    Equipment_ID       INTEGER PRIMARY KEY,
    Voltage_Rating     VARCHAR(30),
    Power_Rating       VARCHAR(30),
    Frequency_Range    VARCHAR(50),
    CONSTRAINT fk_electronic_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
);

CREATE TABLE MECHANICAL_EQUIPMENT (
    Equipment_ID       INTEGER PRIMARY KEY,
    Material           VARCHAR(60),
    Load_Capacity      VARCHAR(30),
    Dimensions         VARCHAR(60),
    CONSTRAINT fk_mechanical_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
);

CREATE TABLE MEASURING_INSTRUMENT (
    Equipment_ID       INTEGER PRIMARY KEY,
    Measurement_Range  VARCHAR(60),
    Accuracy           VARCHAR(30),
    Resolution         VARCHAR(30),
    CONSTRAINT fk_measuring_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
);

CREATE TABLE MEDICAL_EQUIPMENT (
    Equipment_ID          INTEGER PRIMARY KEY,
    Device_Class          VARCHAR(10),
    Sterilization_Method  VARCHAR(40),
    Regulatory_Approval   VARCHAR(80),
    CONSTRAINT chk_medical_class CHECK (Device_Class IN ('Class I', 'Class IIa', 'Class IIb', 'Class III')),
    CONSTRAINT fk_medical_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
);

-- Disjointness: a subtype row may only exist for equipment whose
-- discriminator matches that subtype.
CREATE TRIGGER trg_computing_disjoint BEFORE INSERT ON COMPUTING_EQUIPMENT
WHEN (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'COMPUTING'
BEGIN SELECT RAISE(ABORT, 'Disjoint violation: equipment is not of type COMPUTING'); END;

CREATE TRIGGER trg_electronic_disjoint BEFORE INSERT ON ELECTRONIC_EQUIPMENT
WHEN (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'ELECTRONIC'
BEGIN SELECT RAISE(ABORT, 'Disjoint violation: equipment is not of type ELECTRONIC'); END;

CREATE TRIGGER trg_mechanical_disjoint BEFORE INSERT ON MECHANICAL_EQUIPMENT
WHEN (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'MECHANICAL'
BEGIN SELECT RAISE(ABORT, 'Disjoint violation: equipment is not of type MECHANICAL'); END;

CREATE TRIGGER trg_measuring_disjoint BEFORE INSERT ON MEASURING_INSTRUMENT
WHEN (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'MEASURING'
BEGIN SELECT RAISE(ABORT, 'Disjoint violation: equipment is not of type MEASURING'); END;

CREATE TRIGGER trg_medical_disjoint BEFORE INSERT ON MEDICAL_EQUIPMENT
WHEN (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'MEDICAL'
BEGIN SELECT RAISE(ABORT, 'Disjoint violation: equipment is not of type MEDICAL'); END;

-- ---------------------------------------------------------------------
-- Inventory
-- ---------------------------------------------------------------------
CREATE TABLE CONSUMABLE (
    Consumable_ID      INTEGER PRIMARY KEY AUTOINCREMENT,
    Item_Name          VARCHAR(120) NOT NULL,
    Category           VARCHAR(60),
    Unit               VARCHAR(20),
    Quantity           DECIMAL(10,2) NOT NULL DEFAULT 0,
    Reorder_Level      DECIMAL(10,2) NOT NULL DEFAULT 0,
    Lab_ID             INTEGER,
    CONSTRAINT chk_consumable_qty CHECK (Quantity >= 0),
    CONSTRAINT chk_consumable_reorder CHECK (Reorder_Level >= 0),
    CONSTRAINT fk_consumable_lab FOREIGN KEY (Lab_ID)
        REFERENCES LABORATORY (Lab_ID) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------------
-- Operations on equipment
-- ---------------------------------------------------------------------
CREATE TABLE EQUIPMENT_BOOKING (
    Booking_ID         INTEGER PRIMARY KEY AUTOINCREMENT,
    Booking_Date       DATE NOT NULL,
    Time_Slot          VARCHAR(11) NOT NULL,
    Booking_Status     VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    Equipment_ID       INTEGER NOT NULL,
    User_ID            INTEGER NOT NULL,
    CONSTRAINT chk_booking_status CHECK (Booking_Status IN
        ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'COMPLETED')),
    CONSTRAINT fk_booking_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE RESTRICT,
    CONSTRAINT fk_booking_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE RESTRICT
);
CREATE INDEX idx_booking_equipment_date ON EQUIPMENT_BOOKING (Equipment_ID, Booking_Date);

-- Database-level guard against double booking of the identical slot.
-- (The app additionally rejects partially overlapping slots, e.g. 09:00-11:00 vs 10:00-11:00.)
CREATE TRIGGER trg_booking_no_double_insert BEFORE INSERT ON EQUIPMENT_BOOKING
WHEN NEW.Booking_Status IN ('PENDING', 'APPROVED') AND EXISTS (
    SELECT 1 FROM EQUIPMENT_BOOKING b
    WHERE b.Equipment_ID = NEW.Equipment_ID AND b.Booking_Date = NEW.Booking_Date
      AND b.Time_Slot = NEW.Time_Slot AND b.Booking_Status IN ('PENDING', 'APPROVED'))
BEGIN SELECT RAISE(ABORT, 'Double booking: this equipment is already booked for that date and time slot'); END;

CREATE TRIGGER trg_booking_no_double_update BEFORE UPDATE ON EQUIPMENT_BOOKING
WHEN NEW.Booking_Status IN ('PENDING', 'APPROVED') AND EXISTS (
    SELECT 1 FROM EQUIPMENT_BOOKING b
    WHERE b.Equipment_ID = NEW.Equipment_ID AND b.Booking_Date = NEW.Booking_Date
      AND b.Time_Slot = NEW.Time_Slot AND b.Booking_Status IN ('PENDING', 'APPROVED')
      AND b.Booking_ID <> NEW.Booking_ID)
BEGIN SELECT RAISE(ABORT, 'Double booking: this equipment is already booked for that date and time slot'); END;

CREATE TABLE CALIBRATION (
    Calibration_ID     INTEGER PRIMARY KEY AUTOINCREMENT,
    Calibration_Date   DATE NOT NULL,
    Technician_Name    VARCHAR(100),
    Next_Due_Date      DATE,
    Status             VARCHAR(15) DEFAULT 'SCHEDULED',
    Equipment_ID       INTEGER NOT NULL,
    CONSTRAINT chk_calibration_due CHECK (Next_Due_Date > Calibration_Date),
    CONSTRAINT chk_calibration_status CHECK (Status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'FAILED')),
    CONSTRAINT fk_calibration_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE RESTRICT
);

CREATE TABLE ASSET_TRANSFER (
    Transfer_ID        INTEGER PRIMARY KEY AUTOINCREMENT,
    Equipment_ID       INTEGER NOT NULL,
    From_Lab_ID        INTEGER NOT NULL,
    To_Lab_ID          INTEGER NOT NULL,
    Transfer_Date      DATE,
    Reason             VARCHAR(255),
    Approved_By        VARCHAR(100),
    Technician_Name    VARCHAR(100),
    Status             VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    CONSTRAINT chk_transfer_labs CHECK (From_Lab_ID <> To_Lab_ID),
    CONSTRAINT chk_transfer_status CHECK (Status IN ('PENDING', 'APPROVED', 'COMPLETED', 'REJECTED')),
    CONSTRAINT fk_transfer_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE RESTRICT,
    CONSTRAINT fk_transfer_from_lab FOREIGN KEY (From_Lab_ID)
        REFERENCES LABORATORY (Lab_ID) ON DELETE RESTRICT,
    CONSTRAINT fk_transfer_to_lab FOREIGN KEY (To_Lab_ID)
        REFERENCES LABORATORY (Lab_ID) ON DELETE RESTRICT
);

CREATE TABLE MAINTENANCE (
    Maintenance_ID     INTEGER PRIMARY KEY AUTOINCREMENT,
    Maintenance_Date   DATE NOT NULL,
    Maintenance_Type   VARCHAR(15),
    Cost               DECIMAL(10,2) DEFAULT 0,
    Status             VARCHAR(12) NOT NULL DEFAULT 'SCHEDULED',
    Equipment_ID       INTEGER NOT NULL,
    CONSTRAINT chk_maintenance_type CHECK (Maintenance_Type IN ('Preventive', 'Repair', 'Inspection')),
    CONSTRAINT chk_maintenance_cost CHECK (Cost >= 0),
    CONSTRAINT chk_maintenance_status CHECK (Status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED')),
    CONSTRAINT fk_maintenance_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE RESTRICT
);

CREATE TABLE WARRANTY (
    Warranty_ID          INTEGER PRIMARY KEY AUTOINCREMENT,
    Equipment_ID         INTEGER NOT NULL UNIQUE,      -- 1:1 "Covered By"
    Vendor_ID            INTEGER,                      -- "Vendor Provides Warranty"
    Warranty_Start_Date  DATE,
    Warranty_End_Date    DATE,
    Warranty_Status      VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT chk_warranty_dates CHECK (Warranty_End_Date >= Warranty_Start_Date),
    CONSTRAINT chk_warranty_status CHECK (Warranty_Status IN ('ACTIVE', 'EXPIRED')),
    CONSTRAINT fk_warranty_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE RESTRICT,
    CONSTRAINT fk_warranty_vendor FOREIGN KEY (Vendor_ID)
        REFERENCES VENDOR (Vendor_ID) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------------
-- Accountability and communication
-- ---------------------------------------------------------------------
CREATE TABLE AUDIT_LOG (
    Log_ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    Action_Performed   VARCHAR(100) NOT NULL,
    Date_Time          DATETIME DEFAULT CURRENT_TIMESTAMP,
    IP_Address         VARCHAR(45),
    Remarks            VARCHAR(500),
    User_ID            INTEGER,
    Maintenance_ID     INTEGER,
    -- SET NULL keeps the audit trail when a user / maintenance record is removed
    CONSTRAINT fk_audit_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE SET NULL,
    CONSTRAINT fk_audit_maintenance FOREIGN KEY (Maintenance_ID)
        REFERENCES MAINTENANCE (Maintenance_ID) ON DELETE SET NULL
);
CREATE INDEX idx_audit_datetime ON AUDIT_LOG (Date_Time);

CREATE TABLE NOTIFICATION (
    Notification_ID    INTEGER PRIMARY KEY AUTOINCREMENT,
    User_ID            INTEGER NOT NULL,
    Notification_Type  VARCHAR(30),
    Message            VARCHAR(500),
    Date_Time          DATETIME DEFAULT CURRENT_TIMESTAMP,
    Status             VARCHAR(6) NOT NULL DEFAULT 'UNREAD',
    CONSTRAINT chk_notification_status CHECK (Status IN ('UNREAD', 'READ')),
    CONSTRAINT fk_notification_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Reporting views
-- ---------------------------------------------------------------------
CREATE VIEW V_EQUIPMENT_UTILIZATION AS
SELECT e.Equipment_ID, e.Equipment_Name, e.Equipment_Type, e.Equipment_Status,
       l.Lab_Name,
       COUNT(b.Booking_ID) AS Total_Bookings,
       SUM(CASE WHEN b.Booking_Status IN ('APPROVED', 'COMPLETED') THEN 1 ELSE 0 END) AS Used_Bookings,
       MAX(b.Booking_Date) AS Last_Booked
FROM EQUIPMENT e
LEFT JOIN LABORATORY l ON l.Lab_ID = e.Lab_ID
LEFT JOIN EQUIPMENT_BOOKING b ON b.Equipment_ID = e.Equipment_ID
GROUP BY e.Equipment_ID, e.Equipment_Name, e.Equipment_Type, e.Equipment_Status, l.Lab_Name;

CREATE VIEW V_LOW_STOCK AS
SELECT c.Consumable_ID, c.Item_Name, c.Category, c.Quantity, c.Unit, c.Reorder_Level, l.Lab_Name
FROM CONSUMABLE c
LEFT JOIN LABORATORY l ON l.Lab_ID = c.Lab_ID
WHERE c.Quantity <= c.Reorder_Level;
