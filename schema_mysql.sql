-- =====================================================================
-- Smart Laboratory Resource and Asset Management System
-- MySQL 8.0.16+ DDL (CHECK constraints are enforced from 8.0.16).
-- Same tables, columns, keys and constraints as schema_sqlite.sql.
-- Open in MySQL Workbench and run the whole script (Ctrl+Shift+Enter),
-- or use Database > Reverse Engineer to produce the EER diagram.
-- =====================================================================

DROP DATABASE IF EXISTS smart_lab_db;
CREATE DATABASE smart_lab_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_lab_db;

-- ---------------------------------------------------------------------
-- Organisation structure
-- ---------------------------------------------------------------------
CREATE TABLE ORGANIZATION (
    Organization_ID    INT AUTO_INCREMENT PRIMARY KEY,
    Organization_Name  VARCHAR(150) NOT NULL,
    Organization_Type  VARCHAR(50),
    Address            VARCHAR(255),
    Contact_Email      VARCHAR(120) UNIQUE,
    Contact_Number     VARCHAR(20)  UNIQUE
) ENGINE = InnoDB;

CREATE TABLE DEPARTMENT (
    Department_ID      INT AUTO_INCREMENT PRIMARY KEY,
    Department_Name    VARCHAR(120) NOT NULL,
    HOD_Name           VARCHAR(100),
    Building_Name      VARCHAR(100),
    Contact_Number     VARCHAR(20) UNIQUE,
    Status             VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    Organization_ID    INT NOT NULL,
    CONSTRAINT chk_department_status CHECK (Status IN ('ACTIVE', 'INACTIVE')),
    CONSTRAINT fk_department_org FOREIGN KEY (Organization_ID)
        REFERENCES ORGANIZATION (Organization_ID)
) ENGINE = InnoDB;

CREATE TABLE LABORATORY (
    Lab_ID             INT AUTO_INCREMENT PRIMARY KEY,
    Lab_Name           VARCHAR(120) NOT NULL,
    Capacity           INT,
    Location           VARCHAR(150),
    Lab_Incharge       VARCHAR(100),
    Department_ID      INT NOT NULL,
    CONSTRAINT chk_lab_capacity CHECK (Capacity > 0),
    CONSTRAINT fk_lab_department FOREIGN KEY (Department_ID)
        REFERENCES DEPARTMENT (Department_ID)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Users, roles and the USER specialization (Total + Overlapping)
-- ---------------------------------------------------------------------
CREATE TABLE ROLE (
    Role_ID            INT AUTO_INCREMENT PRIMARY KEY,
    Role_Name          VARCHAR(50) NOT NULL UNIQUE,
    Access_Level       INT,
    Created_Date       DATE,
    Status             VARCHAR(10) DEFAULT 'ACTIVE',
    CONSTRAINT chk_role_access CHECK (Access_Level BETWEEN 1 AND 5),
    CONSTRAINT chk_role_status CHECK (Status IN ('ACTIVE', 'INACTIVE'))
) ENGINE = InnoDB;

CREATE TABLE LAB_USER (
    User_ID            INT AUTO_INCREMENT PRIMARY KEY,
    Full_Name          VARCHAR(100) NOT NULL,
    Email              VARCHAR(120) NOT NULL UNIQUE,
    Phone_Number       VARCHAR(20) UNIQUE,
    Password_Hash      VARCHAR(255) NOT NULL,
    Department_ID      INT NOT NULL,
    Role_ID            INT NOT NULL,
    CONSTRAINT fk_user_department FOREIGN KEY (Department_ID)
        REFERENCES DEPARTMENT (Department_ID),
    CONSTRAINT fk_user_role FOREIGN KEY (Role_ID)
        REFERENCES ROLE (Role_ID)
) ENGINE = InnoDB;

CREATE TABLE ADMINISTRATOR (
    User_ID            INT PRIMARY KEY,
    Admin_Level        VARCHAR(30),
    Permissions        VARCHAR(255),
    Last_Login         DATETIME,
    CONSTRAINT fk_admin_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE LAB_MANAGER (
    User_ID            INT PRIMARY KEY,
    Office_Room        VARCHAR(30),
    Experience         INT,
    Managed_Labs       VARCHAR(255),
    CONSTRAINT chk_manager_experience CHECK (Experience >= 0),
    CONSTRAINT fk_manager_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE LAB_TECHNICIAN (
    User_ID            INT PRIMARY KEY,
    Skill_Type         VARCHAR(100),
    Shift_Time         VARCHAR(30),
    Certification      VARCHAR(150),
    CONSTRAINT fk_technician_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE RESEARCHER (
    User_ID            INT PRIMARY KEY,
    Research_Area      VARCHAR(150),
    Qualification      VARCHAR(100),
    Research_Interest  VARCHAR(255),
    CONSTRAINT fk_researcher_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE FACULTY (
    User_ID                 INT PRIMARY KEY,
    Department_Affiliation  VARCHAR(120),
    Designation             VARCHAR(80),
    Date_of_Joining         DATE,
    CONSTRAINT fk_faculty_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Suppliers and classification
-- ---------------------------------------------------------------------
CREATE TABLE VENDOR (
    Vendor_ID          INT AUTO_INCREMENT PRIMARY KEY,
    Vendor_Name        VARCHAR(120) NOT NULL,
    Contact_Person     VARCHAR(100),
    Phone_Number       VARCHAR(20),
    Email              VARCHAR(120) UNIQUE,
    Address            VARCHAR(255)
) ENGINE = InnoDB;

CREATE TABLE EQUIPMENT_CATEGORY (
    Category_ID          INT AUTO_INCREMENT PRIMARY KEY,
    Category_Name        VARCHAR(80) NOT NULL UNIQUE,
    Description          VARCHAR(255),
    Safety_Level         VARCHAR(20),
    Storage_Requirement  VARCHAR(150),
    Status               VARCHAR(10) DEFAULT 'ACTIVE',
    CONSTRAINT chk_category_status CHECK (Status IN ('ACTIVE', 'INACTIVE'))
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Equipment and the EQUIPMENT specialization (Total + Disjoint)
-- ---------------------------------------------------------------------
CREATE TABLE EQUIPMENT (
    Equipment_ID       INT AUTO_INCREMENT PRIMARY KEY,
    Equipment_Name     VARCHAR(120) NOT NULL,
    Purchase_Date      DATE,
    Serial_Number      VARCHAR(60) NOT NULL UNIQUE,
    Equipment_Status   VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    Equipment_Type     VARCHAR(20) NOT NULL,
    Lab_ID             INT,
    Category_ID        INT,
    Vendor_ID          INT,
    CONSTRAINT chk_equipment_status CHECK (Equipment_Status IN
        ('AVAILABLE', 'IN_USE', 'UNDER_MAINTENANCE', 'UNDER_CALIBRATION', 'RETIRED')),
    CONSTRAINT chk_equipment_type CHECK (Equipment_Type IN
        ('COMPUTING', 'ELECTRONIC', 'MECHANICAL', 'MEASURING', 'MEDICAL')),
    CONSTRAINT fk_equipment_lab FOREIGN KEY (Lab_ID) REFERENCES LABORATORY (Lab_ID),
    CONSTRAINT fk_equipment_category FOREIGN KEY (Category_ID) REFERENCES EQUIPMENT_CATEGORY (Category_ID),
    CONSTRAINT fk_equipment_vendor FOREIGN KEY (Vendor_ID) REFERENCES VENDOR (Vendor_ID)
) ENGINE = InnoDB;

CREATE TABLE COMPUTING_EQUIPMENT (
    Equipment_ID       INT PRIMARY KEY,
    Processor          VARCHAR(80),
    RAM_GB             INT,
    Operating_System   VARCHAR(60),
    CONSTRAINT chk_computing_ram CHECK (RAM_GB > 0),
    CONSTRAINT fk_computing_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE ELECTRONIC_EQUIPMENT (
    Equipment_ID       INT PRIMARY KEY,
    Voltage_Rating     VARCHAR(30),
    Power_Rating       VARCHAR(30),
    Frequency_Range    VARCHAR(50),
    CONSTRAINT fk_electronic_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE MECHANICAL_EQUIPMENT (
    Equipment_ID       INT PRIMARY KEY,
    Material           VARCHAR(60),
    Load_Capacity      VARCHAR(30),
    Dimensions         VARCHAR(60),
    CONSTRAINT fk_mechanical_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE MEASURING_INSTRUMENT (
    Equipment_ID       INT PRIMARY KEY,
    Measurement_Range  VARCHAR(60),
    Accuracy           VARCHAR(30),
    Resolution         VARCHAR(30),
    CONSTRAINT fk_measuring_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE MEDICAL_EQUIPMENT (
    Equipment_ID          INT PRIMARY KEY,
    Device_Class          VARCHAR(10),
    Sterilization_Method  VARCHAR(40),
    Regulatory_Approval   VARCHAR(80),
    CONSTRAINT chk_medical_class CHECK (Device_Class IN ('Class I', 'Class IIa', 'Class IIb', 'Class III')),
    CONSTRAINT fk_medical_equipment FOREIGN KEY (Equipment_ID)
        REFERENCES EQUIPMENT (Equipment_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Inventory
-- ---------------------------------------------------------------------
CREATE TABLE CONSUMABLE (
    Consumable_ID      INT AUTO_INCREMENT PRIMARY KEY,
    Item_Name          VARCHAR(120) NOT NULL,
    Category           VARCHAR(60),
    Unit               VARCHAR(20),
    Quantity           DECIMAL(10,2) NOT NULL DEFAULT 0,
    Reorder_Level      DECIMAL(10,2) NOT NULL DEFAULT 0,
    Lab_ID             INT,
    CONSTRAINT chk_consumable_qty CHECK (Quantity >= 0),
    CONSTRAINT chk_consumable_reorder CHECK (Reorder_Level >= 0),
    CONSTRAINT fk_consumable_lab FOREIGN KEY (Lab_ID) REFERENCES LABORATORY (Lab_ID)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Operations on equipment
-- ---------------------------------------------------------------------
CREATE TABLE EQUIPMENT_BOOKING (
    Booking_ID         INT AUTO_INCREMENT PRIMARY KEY,
    Booking_Date       DATE NOT NULL,
    Time_Slot          VARCHAR(11) NOT NULL,
    Booking_Status     VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    Equipment_ID       INT NOT NULL,
    User_ID            INT NOT NULL,
    CONSTRAINT chk_booking_status CHECK (Booking_Status IN
        ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'COMPLETED')),
    CONSTRAINT fk_booking_equipment FOREIGN KEY (Equipment_ID) REFERENCES EQUIPMENT (Equipment_ID),
    CONSTRAINT fk_booking_user FOREIGN KEY (User_ID) REFERENCES LAB_USER (User_ID),
    INDEX idx_booking_equipment_date (Equipment_ID, Booking_Date)
) ENGINE = InnoDB;

CREATE TABLE CALIBRATION (
    Calibration_ID     INT AUTO_INCREMENT PRIMARY KEY,
    Calibration_Date   DATE NOT NULL,
    Technician_Name    VARCHAR(100),
    Next_Due_Date      DATE,
    Status             VARCHAR(15) DEFAULT 'SCHEDULED',
    Equipment_ID       INT NOT NULL,
    CONSTRAINT chk_calibration_due CHECK (Next_Due_Date > Calibration_Date),
    CONSTRAINT chk_calibration_status CHECK (Status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'FAILED')),
    CONSTRAINT fk_calibration_equipment FOREIGN KEY (Equipment_ID) REFERENCES EQUIPMENT (Equipment_ID)
) ENGINE = InnoDB;

CREATE TABLE ASSET_TRANSFER (
    Transfer_ID        INT AUTO_INCREMENT PRIMARY KEY,
    Equipment_ID       INT NOT NULL,
    From_Lab_ID        INT NOT NULL,
    To_Lab_ID          INT NOT NULL,
    Transfer_Date      DATE,
    Reason             VARCHAR(255),
    Approved_By        VARCHAR(100),
    Technician_Name    VARCHAR(100),
    Status             VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    CONSTRAINT chk_transfer_labs CHECK (From_Lab_ID <> To_Lab_ID),
    CONSTRAINT chk_transfer_status CHECK (Status IN ('PENDING', 'APPROVED', 'COMPLETED', 'REJECTED')),
    CONSTRAINT fk_transfer_equipment FOREIGN KEY (Equipment_ID) REFERENCES EQUIPMENT (Equipment_ID),
    CONSTRAINT fk_transfer_from_lab FOREIGN KEY (From_Lab_ID) REFERENCES LABORATORY (Lab_ID),
    CONSTRAINT fk_transfer_to_lab FOREIGN KEY (To_Lab_ID) REFERENCES LABORATORY (Lab_ID)
) ENGINE = InnoDB;

CREATE TABLE MAINTENANCE (
    Maintenance_ID     INT AUTO_INCREMENT PRIMARY KEY,
    Maintenance_Date   DATE NOT NULL,
    Maintenance_Type   VARCHAR(15),
    Cost               DECIMAL(10,2) DEFAULT 0,
    Status             VARCHAR(12) NOT NULL DEFAULT 'SCHEDULED',
    Equipment_ID       INT NOT NULL,
    CONSTRAINT chk_maintenance_type CHECK (Maintenance_Type IN ('Preventive', 'Repair', 'Inspection')),
    CONSTRAINT chk_maintenance_cost CHECK (Cost >= 0),
    CONSTRAINT chk_maintenance_status CHECK (Status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED')),
    CONSTRAINT fk_maintenance_equipment FOREIGN KEY (Equipment_ID) REFERENCES EQUIPMENT (Equipment_ID)
) ENGINE = InnoDB;

CREATE TABLE WARRANTY (
    Warranty_ID          INT AUTO_INCREMENT PRIMARY KEY,
    Equipment_ID         INT NOT NULL UNIQUE,
    Vendor_ID            INT,
    Warranty_Start_Date  DATE,
    Warranty_End_Date    DATE,
    Warranty_Status      VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT chk_warranty_dates CHECK (Warranty_End_Date >= Warranty_Start_Date),
    CONSTRAINT chk_warranty_status CHECK (Warranty_Status IN ('ACTIVE', 'EXPIRED')),
    CONSTRAINT fk_warranty_equipment FOREIGN KEY (Equipment_ID) REFERENCES EQUIPMENT (Equipment_ID),
    CONSTRAINT fk_warranty_vendor FOREIGN KEY (Vendor_ID) REFERENCES VENDOR (Vendor_ID)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Accountability and communication
-- ---------------------------------------------------------------------
CREATE TABLE AUDIT_LOG (
    Log_ID             INT AUTO_INCREMENT PRIMARY KEY,
    Action_Performed   VARCHAR(100) NOT NULL,
    Date_Time          DATETIME DEFAULT CURRENT_TIMESTAMP,
    IP_Address         VARCHAR(45),
    Remarks            VARCHAR(500),
    User_ID            INT NULL,
    Maintenance_ID     INT NULL,
    CONSTRAINT fk_audit_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE SET NULL,
    CONSTRAINT fk_audit_maintenance FOREIGN KEY (Maintenance_ID)
        REFERENCES MAINTENANCE (Maintenance_ID) ON DELETE SET NULL,
    INDEX idx_audit_datetime (Date_Time)
) ENGINE = InnoDB;

CREATE TABLE NOTIFICATION (
    Notification_ID    INT AUTO_INCREMENT PRIMARY KEY,
    User_ID            INT NOT NULL,
    Notification_Type  VARCHAR(30),
    Message            VARCHAR(500),
    Date_Time          DATETIME DEFAULT CURRENT_TIMESTAMP,
    Status             VARCHAR(6) NOT NULL DEFAULT 'UNREAD',
    CONSTRAINT chk_notification_status CHECK (Status IN ('UNREAD', 'READ')),
    CONSTRAINT fk_notification_user FOREIGN KEY (User_ID)
        REFERENCES LAB_USER (User_ID) ON DELETE CASCADE
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Triggers: double booking guard and subtype disjointness
-- ---------------------------------------------------------------------
DELIMITER $$

CREATE TRIGGER trg_booking_no_double_insert BEFORE INSERT ON EQUIPMENT_BOOKING
FOR EACH ROW
BEGIN
    IF NEW.Booking_Status IN ('PENDING', 'APPROVED') AND EXISTS (
        SELECT 1 FROM EQUIPMENT_BOOKING b
        WHERE b.Equipment_ID = NEW.Equipment_ID AND b.Booking_Date = NEW.Booking_Date
          AND b.Time_Slot = NEW.Time_Slot AND b.Booking_Status IN ('PENDING', 'APPROVED')) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Double booking: this equipment is already booked for that date and time slot';
    END IF;
END$$

CREATE TRIGGER trg_booking_no_double_update BEFORE UPDATE ON EQUIPMENT_BOOKING
FOR EACH ROW
BEGIN
    IF NEW.Booking_Status IN ('PENDING', 'APPROVED') AND EXISTS (
        SELECT 1 FROM EQUIPMENT_BOOKING b
        WHERE b.Equipment_ID = NEW.Equipment_ID AND b.Booking_Date = NEW.Booking_Date
          AND b.Time_Slot = NEW.Time_Slot AND b.Booking_Status IN ('PENDING', 'APPROVED')
          AND b.Booking_ID <> NEW.Booking_ID) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Double booking: this equipment is already booked for that date and time slot';
    END IF;
END$$

CREATE TRIGGER trg_computing_disjoint BEFORE INSERT ON COMPUTING_EQUIPMENT
FOR EACH ROW
BEGIN
    IF (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'COMPUTING' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Disjoint violation: equipment is not of type COMPUTING';
    END IF;
END$$

CREATE TRIGGER trg_electronic_disjoint BEFORE INSERT ON ELECTRONIC_EQUIPMENT
FOR EACH ROW
BEGIN
    IF (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'ELECTRONIC' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Disjoint violation: equipment is not of type ELECTRONIC';
    END IF;
END$$

CREATE TRIGGER trg_mechanical_disjoint BEFORE INSERT ON MECHANICAL_EQUIPMENT
FOR EACH ROW
BEGIN
    IF (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'MECHANICAL' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Disjoint violation: equipment is not of type MECHANICAL';
    END IF;
END$$

CREATE TRIGGER trg_measuring_disjoint BEFORE INSERT ON MEASURING_INSTRUMENT
FOR EACH ROW
BEGIN
    IF (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'MEASURING' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Disjoint violation: equipment is not of type MEASURING';
    END IF;
END$$

CREATE TRIGGER trg_medical_disjoint BEFORE INSERT ON MEDICAL_EQUIPMENT
FOR EACH ROW
BEGIN
    IF (SELECT Equipment_Type FROM EQUIPMENT WHERE Equipment_ID = NEW.Equipment_ID) <> 'MEDICAL' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Disjoint violation: equipment is not of type MEDICAL';
    END IF;
END$$

DELIMITER ;

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
