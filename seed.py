"""Create the SQLite database and load realistic sample data.

    python seed.py            # drop and rebuild data/smart_lab.db with fresh sample data

Dates are generated relative to today so the dashboard always has recent activity,
overdue items and upcoming deadlines to show. All demo accounts use password  lab12345.
"""
import datetime as dt
import os
import random

import bcrypt

import db

DEMO_PASSWORD = "lab12345"
TODAY = dt.date.today()


def d(days):
    """Date offset from today as ISO string."""
    return (TODAY + dt.timedelta(days=days)).isoformat()


def insert(conn, table, row):
    cols = list(row)
    cur = conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                       [row[c] for c in cols])
    return cur.lastrowid


def seed():
    rng = random.Random(518)
    pw_hash = lambda: bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt(rounds=10)).decode()  # noqa: E731

    with db.transaction() as conn:
        # ---------------- Organisation ----------------
        org = insert(conn, "ORGANIZATION", dict(
            Organization_Name="Northfield Institute of Technology", Organization_Type="University",
            Address="12 College Road, Northfield", Contact_Email="info@northfield.edu",
            Contact_Number="+91 11 4000 1000"))
        insert(conn, "ORGANIZATION", dict(
            Organization_Name="Northfield Research Foundation", Organization_Type="Research Institute",
            Address="Innovation Park, Block C, Northfield", Contact_Email="contact@nrf.org",
            Contact_Number="+91 11 4000 2000"))

        depts = {}
        for name, hod, building, phone, status in [
            ("Computer Science & Engineering", "Dr. R. Menon", "Turing Block", "+91 11 4000 1101", "ACTIVE"),
            ("Electronics & Communication", "Dr. S. Pillai", "Bose Block", "+91 11 4000 1102", "ACTIVE"),
            ("Mechanical Engineering", "Dr. K. Rathore", "Visvesvaraya Block", "+91 11 4000 1103", "ACTIVE"),
            ("Physics", "Dr. L. Fernandes", "Raman Block", "+91 11 4000 1104", "ACTIVE"),
            ("Biotechnology", "Dr. P. Das", "Khorana Block", "+91 11 4000 1105", "INACTIVE"),
        ]:
            depts[name] = insert(conn, "DEPARTMENT", dict(
                Department_Name=name, HOD_Name=hod, Building_Name=building, Contact_Number=phone,
                Status=status, Organization_ID=org))
        cse, ece, mech, phy = (depts[k] for k in list(depts)[:4])

        labs = {}
        for name, cap, loc, incharge, dept in [
            ("AI & Data Science Lab", 40, "Turing Block, Room 201", "Rahul Verma", cse),
            ("Computer Networks Lab", 36, "Turing Block, Room 105", "Sanjay Gupta", cse),
            ("Embedded Systems Lab", 30, "Bose Block, Room 310", "Rahul Verma", ece),
            ("Signal Processing Lab", 24, "Bose Block, Room 312", "Sanjay Gupta", ece),
            ("Manufacturing Lab", 20, "Visvesvaraya Block, Ground Floor", "Sanjay Gupta", mech),
            ("Materials Testing Lab", 18, "Visvesvaraya Block, Room 120", "Rahul Verma", mech),
            ("Optics & Photonics Lab", 16, "Raman Block, Room 014", "Rahul Verma", phy),
        ]:
            labs[name] = insert(conn, "LABORATORY", dict(Lab_Name=name, Capacity=cap, Location=loc,
                                                         Lab_Incharge=incharge, Department_ID=dept))
        lab_ids = list(labs.values())

        # ---------------- Roles & users ----------------
        roles = {}
        for name, level, created in [("Administrator", 5, -900), ("Lab Manager", 4, -900),
                                     ("Lab Technician", 3, -900), ("Faculty", 2, -900),
                                     ("Researcher", 2, -900), ("Student", 1, -400)]:
            roles[name] = insert(conn, "ROLE", dict(Role_Name=name, Access_Level=level, Created_Date=d(created),
                                                    Status="ACTIVE"))

        users = {}
        people = [
            # key, name, email, phone, dept, role, {subtype: data}
            ("admin", "Jyotsna", "admin@smartlab.edu", "+91 98100 00001", cse, "Administrator",
             {"ADMINISTRATOR": dict(Admin_Level="Super Admin", Permissions="ALL")}),
            ("manager", "Rahul Verma", "manager@smartlab.edu", "+91 98100 00002", ece, "Lab Manager",
             {"LAB_MANAGER": dict(Office_Room="B-301", Experience=11,
                                  Managed_Labs="AI & Data Science Lab, Embedded Systems Lab, Optics & Photonics Lab")}),
            ("manager2", "Sanjay Gupta", "manager2@smartlab.edu", "+91 98100 00003", mech, "Lab Manager",
             {"LAB_MANAGER": dict(Office_Room="V-110", Experience=8,
                                  Managed_Labs="Manufacturing Lab, Computer Networks Lab, Signal Processing Lab"),
              "FACULTY": dict(Department_Affiliation="Mechanical Engineering", Designation="Associate Professor",
                              Date_of_Joining=d(-3200))}),
            ("tech", "Arjun Singh", "tech@smartlab.edu", "+91 98100 00004", ece, "Lab Technician",
             {"LAB_TECHNICIAN": dict(Skill_Type="Electronics & instrumentation", Shift_Time="Morning",
                                     Certification="NABL Calibration Technician")}),
            ("tech2", "Neha Kapoor", "tech2@smartlab.edu", "+91 98100 00005", cse, "Lab Technician",
             {"LAB_TECHNICIAN": dict(Skill_Type="Computer hardware & networking", Shift_Time="Afternoon",
                                     Certification="CompTIA A+, CCNA")}),
            ("tech3", "Vikram Rao", "tech3@smartlab.edu", "+91 98100 00006", mech, "Lab Technician",
             {"LAB_TECHNICIAN": dict(Skill_Type="CNC & mechanical testing", Shift_Time="Morning",
                                     Certification="ISO 17025 Internal Auditor")}),
            ("faculty", "Dr. Meera Iyer", "faculty@smartlab.edu", "+91 98100 00007", cse, "Faculty",
             {"FACULTY": dict(Department_Affiliation="Computer Science & Engineering", Designation="Professor",
                              Date_of_Joining=d(-4800)),
              "RESEARCHER": dict(Research_Area="Machine Learning", Qualification="PhD",
                                 Research_Interest="Federated learning, medical imaging")}),
            ("faculty2", "Dr. Anil Kumar", "faculty2@smartlab.edu", "+91 98100 00008", ece, "Faculty",
             {"FACULTY": dict(Department_Affiliation="Electronics & Communication", Designation="Assistant Professor",
                              Date_of_Joining=d(-1500))}),
            ("faculty3", "Dr. Sunita Joshi", "faculty3@smartlab.edu", "+91 98100 00009", phy, "Faculty",
             {"FACULTY": dict(Department_Affiliation="Physics", Designation="Associate Professor",
                              Date_of_Joining=d(-2900)),
              "RESEARCHER": dict(Research_Area="Photonics", Qualification="PhD",
                                 Research_Interest="Fibre lasers, spectroscopy")}),
            ("researcher", "Kavya Nair", "researcher@smartlab.edu", "+91 98100 00010", cse, "Researcher",
             {"RESEARCHER": dict(Research_Area="Computer Vision", Qualification="MTech",
                                 Research_Interest="Edge AI on embedded GPUs")}),
            ("researcher2", "Rohan Mehta", "researcher2@smartlab.edu", "+91 98100 00011", mech, "Researcher",
             {"RESEARCHER": dict(Research_Area="Advanced Materials", Qualification="MSc",
                                 Research_Interest="Composite fatigue testing")}),
            ("student", "Ishita Banerjee", "student@smartlab.edu", "+91 98100 00012", ece, "Student",
             {"RESEARCHER": dict(Research_Area="Wireless Communication", Qualification="BSc",
                                 Research_Interest="SDR-based 5G testbeds")}),
        ]
        for key, name, email, phone, dept, role, subtypes in people:
            uid = insert(conn, "LAB_USER", dict(Full_Name=name, Email=email, Phone_Number=phone,
                                                Password_Hash=pw_hash(), Department_ID=dept, Role_ID=roles[role]))
            users[key] = uid
            for table, data in subtypes.items():
                insert(conn, table, dict(User_ID=uid, **data))
        bookers = [users[k] for k in ("faculty", "faculty2", "faculty3", "researcher", "researcher2", "student",
                                      "manager2", "tech", "tech2")]
        technicians = ["Arjun Singh", "Neha Kapoor", "Vikram Rao"]

        # ---------------- Vendors & categories ----------------
        vendors = {}
        for name, person, phone, email, addr in [
            ("Dell Technologies India", "Amit Khanna", "+91 80 2800 1000", "edu.sales@dell.example", "Bengaluru"),
            ("Keysight Technologies", "Lisa Thomas", "+91 80 4000 2000", "support@keysight.example", "Bengaluru"),
            ("Tektronix India", "Ravi Shetty", "+91 80 4100 3000", "india@tek.example", "Bengaluru"),
            ("Haas Automation", "Mark Ellis", "+1 805 278 1800", "service@haas.example", "Oxnard, CA"),
            ("Thorlabs", "Julia Weber", "+49 8131 5956 0", "europe@thorlabs.example", "Munich"),
            ("Cisco Systems", "Deepak Jain", "+91 22 6100 4000", "academy@cisco.example", "Mumbai"),
            ("Instron", "Peter Grant", "+44 1494 464646", "info@instron.example", "High Wycombe"),
        ]:
            vendors[name] = insert(conn, "VENDOR", dict(Vendor_Name=name, Contact_Person=person, Phone_Number=phone,
                                                        Email=email, Address=addr))
        cats = {}
        for name, desc, safety, storage in [
            ("Computing", "Workstations, servers and GPU systems", "LOW", "Air-conditioned, dust-free"),
            ("Test & Measurement", "Oscilloscopes, analysers, meters", "MEDIUM", "ESD-safe benches"),
            ("Fabrication", "CNC, 3D printers and machine tools", "HIGH", "Ventilated workshop floor"),
            ("Optical", "Lasers, spectrometers and optical benches", "CRITICAL", "Dark room, vibration isolated"),
            ("Networking", "Routers, switches and SDR kits", "LOW", "Rack mounted, 19-inch"),
            ("Materials Testing", "Universal testing and hardness machines", "HIGH", "Reinforced floor"),
            ("Biomedical", "Patient monitoring and diagnostic devices", "HIGH", "Clean room, controlled humidity"),
        ]:
            cats[name] = insert(conn, "EQUIPMENT_CATEGORY", dict(Category_Name=name, Description=desc,
                                                                 Safety_Level=safety, Storage_Requirement=storage,
                                                                 Status="ACTIVE"))

        # ---------------- Equipment (each with exactly one subtype) ----------------
        C, E, M, I, MD = "COMPUTING", "ELECTRONIC", "MECHANICAL", "MEASURING", "MEDICAL"
        sub_table = {C: "COMPUTING_EQUIPMENT", E: "ELECTRONIC_EQUIPMENT", M: "MECHANICAL_EQUIPMENT",
                     I: "MEASURING_INSTRUMENT", MD: "MEDICAL_EQUIPMENT"}
        catalog = [
            # name, serial, type, category, lab, vendor, age_days, status, popularity, subtype data
            ("GPU Workstation A1", "DL-GPU-0001", C, "Computing", "AI & Data Science Lab", "Dell Technologies India",
             700, "AVAILABLE", 10, dict(Processor="Intel Xeon W-2295", RAM_GB=128, Operating_System="Ubuntu 22.04")),
            ("GPU Workstation A2", "DL-GPU-0002", C, "Computing", "AI & Data Science Lab", "Dell Technologies India",
             700, "IN_USE", 9, dict(Processor="Intel Xeon W-2295", RAM_GB=128, Operating_System="Ubuntu 22.04")),
            ("HPC Compute Node", "DL-HPC-0101", C, "Computing", "AI & Data Science Lab", "Dell Technologies India",
             1100, "AVAILABLE", 7, dict(Processor="AMD EPYC 7543", RAM_GB=512, Operating_System="Rocky Linux 9")),
            ("Jetson Edge AI Kit", "NV-JET-0310", C, "Computing", "Embedded Systems Lab", "Dell Technologies India",
             400, "AVAILABLE", 6, dict(Processor="ARM Cortex-A78AE", RAM_GB=32, Operating_System="JetPack 6")),
            ("Data Visualisation PC", "DL-OPT-0450", C, "Computing", "AI & Data Science Lab", "Dell Technologies India",
             1600, "RETIRED", 0, dict(Processor="Intel Core i7-7700", RAM_GB=16, Operating_System="Windows 10")),
            ("Network Simulation Server", "DL-SRV-0220", C, "Computing", "Computer Networks Lab",
             "Dell Technologies India", 900, "AVAILABLE", 4,
             dict(Processor="Intel Xeon Silver 4314", RAM_GB=256, Operating_System="Ubuntu 20.04")),
            ("Cisco Router Kit 1", "CS-RTR-4431", E, "Networking", "Computer Networks Lab", "Cisco Systems",
             1000, "AVAILABLE", 5, dict(Voltage_Rating="230 V AC", Power_Rating="250 W", Frequency_Range="—")),
            ("Cisco Switch Stack", "CS-SW-9300", E, "Networking", "Computer Networks Lab", "Cisco Systems",
             1000, "AVAILABLE", 3, dict(Voltage_Rating="230 V AC", Power_Rating="350 W", Frequency_Range="—")),
            ("USRP Software Defined Radio", "NI-USRP-2954", E, "Networking", "Signal Processing Lab", "Keysight Technologies",
             500, "AVAILABLE", 6, dict(Voltage_Rating="12 V DC", Power_Rating="45 W", Frequency_Range="10 MHz–6 GHz")),
            ("Function Generator", "KS-33522B-01", E, "Test & Measurement", "Embedded Systems Lab",
             "Keysight Technologies", 1300, "AVAILABLE", 4,
             dict(Voltage_Rating="230 V AC", Power_Rating="50 W", Frequency_Range="1 µHz–30 MHz")),
            ("DC Power Supply (Triple)", "KS-E36313-07", E, "Test & Measurement", "Embedded Systems Lab",
             "Keysight Technologies", 900, "AVAILABLE", 5,
             dict(Voltage_Rating="0–30 V / 0–6 V", Power_Rating="160 W", Frequency_Range="—")),
            ("FPGA Development Board", "XL-ZCU-0104", E, "Test & Measurement", "Embedded Systems Lab",
             "Keysight Technologies", 600, "UNDER_MAINTENANCE", 5,
             dict(Voltage_Rating="12 V DC", Power_Rating="60 W", Frequency_Range="up to 1.5 GHz")),
            ("Digital Oscilloscope 1", "TK-MSO54-001", I, "Test & Measurement", "Embedded Systems Lab",
             "Tektronix India", 800, "AVAILABLE", 8,
             dict(Measurement_Range="1 mV–10 V/div", Accuracy="±1.5%", Resolution="12-bit")),
            ("Digital Oscilloscope 2", "TK-MSO54-002", I, "Test & Measurement", "Signal Processing Lab",
             "Tektronix India", 800, "AVAILABLE", 6,
             dict(Measurement_Range="1 mV–10 V/div", Accuracy="±1.5%", Resolution="12-bit")),
            ("Spectrum Analyzer", "KS-N9020B-11", I, "Test & Measurement", "Signal Processing Lab",
             "Keysight Technologies", 1200, "UNDER_CALIBRATION", 4,
             dict(Measurement_Range="10 Hz–26.5 GHz", Accuracy="±0.19 dB", Resolution="1 Hz RBW")),
            ("Vector Network Analyzer", "KS-E5063A-04", I, "Test & Measurement", "Signal Processing Lab",
             "Keysight Technologies", 1500, "AVAILABLE", 2,
             dict(Measurement_Range="100 kHz–18 GHz", Accuracy="±0.1 dB", Resolution="1 Hz")),
            ("Digital Multimeter Bench", "KS-34465A-21", I, "Test & Measurement", "Embedded Systems Lab",
             "Keysight Technologies", 1000, "AVAILABLE", 3,
             dict(Measurement_Range="100 mV–1000 V", Accuracy="±0.003%", Resolution="6½ digit")),
            ("CNC Milling Machine", "HA-VF2-0091", M, "Fabrication", "Manufacturing Lab", "Haas Automation",
             1800, "AVAILABLE", 6, dict(Material="Cast iron frame", Load_Capacity="680 kg table",
                                        Dimensions="2.9 × 2.4 × 2.6 m")),
            ("CNC Lathe", "HA-ST10-0044", M, "Fabrication", "Manufacturing Lab", "Haas Automation",
             1800, "UNDER_MAINTENANCE", 4, dict(Material="Cast iron bed", Load_Capacity="300 kg chuck",
                                                Dimensions="2.6 × 1.8 × 2.0 m")),
            ("Industrial 3D Printer", "UM-S5-0712", M, "Fabrication", "Manufacturing Lab", "Haas Automation",
             500, "AVAILABLE", 9, dict(Material="Aluminium chassis", Load_Capacity="5 kg build",
                                       Dimensions="0.5 × 0.6 × 0.8 m")),
            ("Laser Cutter", "EP-FX-3300", M, "Fabrication", "Manufacturing Lab", "Haas Automation",
             1300, "AVAILABLE", 0, dict(Material="Steel enclosure", Load_Capacity="20 kg bed",
                                        Dimensions="1.4 × 1.0 × 1.1 m")),
            ("Universal Testing Machine", "IN-5982-0301", I, "Materials Testing", "Materials Testing Lab", "Instron",
             2000, "AVAILABLE", 5, dict(Measurement_Range="0–100 kN", Accuracy="±0.5%", Resolution="0.01 N")),
            ("Rockwell Hardness Tester", "IN-RH-2150", I, "Materials Testing", "Materials Testing Lab", "Instron",
             2200, "AVAILABLE", 1, dict(Measurement_Range="HRA–HRC", Accuracy="±0.5 HR", Resolution="0.1 HR")),
            ("Impact Tester (Charpy)", "IN-CH-9050", M, "Materials Testing", "Materials Testing Lab", "Instron",
             2500, "RETIRED", 0, dict(Material="Steel pendulum", Load_Capacity="300 J", Dimensions="1.5 × 0.8 × 2.1 m")),
            ("He-Ne Laser Setup", "TL-HNL-0050", E, "Optical", "Optics & Photonics Lab", "Thorlabs",
             1400, "AVAILABLE", 3, dict(Voltage_Rating="230 V AC", Power_Rating="5 mW optical",
                                        Frequency_Range="632.8 nm")),
            ("Optical Spectrometer", "TL-CCS-0200", I, "Optical", "Optics & Photonics Lab", "Thorlabs",
             600, "AVAILABLE", 4, dict(Measurement_Range="200–1000 nm", Accuracy="±0.5 nm", Resolution="0.5 nm")),
            ("Optical Power Meter", "TL-PM100-31", I, "Optical", "Optics & Photonics Lab", "Thorlabs",
             1000, "AVAILABLE", 0, dict(Measurement_Range="100 pW–200 mW", Accuracy="±3%", Resolution="1 pW")),
            ("Fibre Splicer", "TL-FS-0880", M, "Optical", "Optics & Photonics Lab", "Thorlabs",
             350, "AVAILABLE", 2, dict(Material="Polycarbonate housing", Load_Capacity="—",
                                       Dimensions="0.2 × 0.15 × 0.15 m")),
            ("12-Lead ECG Machine", "BM-ECG-1201", MD, "Biomedical", "Signal Processing Lab", "Keysight Technologies",
             450, "AVAILABLE", 3, dict(Device_Class="Class IIa", Sterilization_Method="Chemical disinfection",
                                       Regulatory_Approval="CDSCO, CE")),
            ("Multiparameter Patient Monitor", "BM-PM-0807", MD, "Biomedical", "Embedded Systems Lab",
             "Keysight Technologies", 300, "AVAILABLE", 2,
             dict(Device_Class="Class IIb", Sterilization_Method="Not required", Regulatory_Approval="FDA 510(k), CE")),
        ]
        equipment = []  # (id, name, type, status, popularity, purchase, lab_id, vendor_id)
        for name, serial, etype, cat, lab, vendor, age, status, pop, sub in catalog:
            purchase = d(-age)
            eid = insert(conn, "EQUIPMENT", dict(
                Equipment_Name=name, Purchase_Date=purchase, Serial_Number=serial, Equipment_Status=status,
                Equipment_Type=etype, Lab_ID=labs[lab], Category_ID=cats[cat], Vendor_ID=vendors[vendor]))
            insert(conn, sub_table[etype], dict(Equipment_ID=eid, **sub))
            equipment.append(dict(id=eid, name=name, type=etype, status=status, pop=pop, purchase=purchase,
                                  age=age, lab=labs[lab], vendor=vendors[vendor]))

        # ---------------- Warranty (1:1) ----------------
        for i, e in enumerate(equipment):
            if i % 7 == 6:
                continue  # a few items without warranty cover
            years = rng.choice([1, 2, 3, 3, 5])
            start = dt.date.fromisoformat(e["purchase"])
            end = start + dt.timedelta(days=365 * years)
            if e["name"] in ("Jetson Edge AI Kit", "Optical Spectrometer"):
                end = TODAY + dt.timedelta(days=rng.randint(12, 50))  # expiring soon
            insert(conn, "WARRANTY", dict(Equipment_ID=e["id"], Vendor_ID=e["vendor"],
                                          Warranty_Start_Date=start.isoformat(), Warranty_End_Date=end.isoformat(),
                                          Warranty_Status="ACTIVE" if end >= TODAY else "EXPIRED"))

        # ---------------- Bookings (no overlaps by construction) ----------------
        slots = [f"{h:02d}:00-{h + 1:02d}:00" for h in range(8, 18)]
        taken = set()
        bookable = [e for e in equipment if e["pop"] > 0]
        weights = [e["pop"] for e in bookable]
        for offset in range(-180, 15):
            day = TODAY + dt.timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            for _ in range(rng.randint(14, 26) if offset < 0 else rng.randint(4, 9)):
                e = rng.choices(bookable, weights)[0]
                if e["status"] == "RETIRED" or dt.date.fromisoformat(e["purchase"]) > day:
                    continue
                start = rng.randint(0, len(slots) - 2)
                length = rng.choice([1, 2, 2])
                chosen = slots[start:start + length]
                if any((e["id"], day, s) in taken for s in chosen):
                    continue
                if offset < 0:
                    status = rng.choices(["COMPLETED", "CANCELLED", "REJECTED"], [85, 9, 6])[0]
                elif offset == 0:
                    status = rng.choice(["APPROVED", "APPROVED", "COMPLETED"])
                else:
                    status = rng.choices(["APPROVED", "PENDING", "CANCELLED"], [55, 40, 5])[0]
                for s in chosen:
                    if status in ("PENDING", "APPROVED", "COMPLETED"):
                        taken.add((e["id"], day, s))
                slot = chosen[0] if length == 1 else f"{chosen[0][:5]}-{chosen[-1][6:]}"
                insert(conn, "EQUIPMENT_BOOKING", dict(Booking_Date=day.isoformat(), Time_Slot=slot,
                                                       Booking_Status=status, Equipment_ID=e["id"],
                                                       User_ID=rng.choice(bookers)))

        # ---------------- Maintenance ----------------
        mtypes = ["Preventive", "Preventive", "Inspection", "Repair"]
        cost_range = {"Preventive": (1500, 6000), "Inspection": (500, 2000), "Repair": (4000, 35000)}
        for e in equipment:
            for _ in range(rng.randint(1, 3)):
                mtype = rng.choice(mtypes)
                when = -rng.randint(5, min(360, e["age"]))
                insert(conn, "MAINTENANCE", dict(Maintenance_Date=d(when), Maintenance_Type=mtype,
                                                 Cost=round(rng.uniform(*cost_range[mtype]), 2),
                                                 Status="COMPLETED", Equipment_ID=e["id"]))
            if e["status"] == "UNDER_MAINTENANCE":
                insert(conn, "MAINTENANCE", dict(Maintenance_Date=d(-rng.randint(1, 6)), Maintenance_Type="Repair",
                                                 Cost=round(rng.uniform(5000, 20000), 2), Status="IN_PROGRESS",
                                                 Equipment_ID=e["id"]))
        active = [e for e in equipment if e["status"] not in ("RETIRED", "UNDER_MAINTENANCE")]
        for e in rng.sample(active, 3):  # overdue: scheduled in the past, never started
            insert(conn, "MAINTENANCE", dict(Maintenance_Date=d(-rng.randint(3, 25)), Maintenance_Type="Preventive",
                                             Cost=0, Status="SCHEDULED", Equipment_ID=e["id"]))
        for e in rng.sample(active, 6):  # upcoming
            insert(conn, "MAINTENANCE", dict(Maintenance_Date=d(rng.randint(2, 75)),
                                             Maintenance_Type=rng.choice(["Preventive", "Inspection"]),
                                             Cost=0, Status="SCHEDULED", Equipment_ID=e["id"]))

        # ---------------- Calibration (measuring + electronic items) ----------------
        calibrated = [e for e in equipment if e["type"] in (I, E) and e["status"] != "RETIRED"]
        plan = {}  # name -> days until next due (negative = overdue)
        for e, due in zip(calibrated, [-12, 9, 21, -4, 140, 200, 60, 95, 250, 18, 300, 45, 170, 220, 80]):
            plan[e["name"]] = due
        for e in calibrated:
            due = plan.get(e["name"], 180)
            interval = 365 if e["type"] == I else 180
            last = TODAY + dt.timedelta(days=due - interval)
            prev = last - dt.timedelta(days=interval)
            if dt.date.fromisoformat(e["purchase"]) < prev:
                insert(conn, "CALIBRATION", dict(Calibration_Date=prev.isoformat(), Next_Due_Date=last.isoformat(),
                                                 Technician_Name=rng.choice(technicians), Status="COMPLETED",
                                                 Equipment_ID=e["id"]))
            insert(conn, "CALIBRATION", dict(Calibration_Date=max(last, dt.date.fromisoformat(e["purchase"])).isoformat(),
                                             Next_Due_Date=d(due), Technician_Name=rng.choice(technicians),
                                             Status="COMPLETED", Equipment_ID=e["id"]))
            if e["status"] == "UNDER_CALIBRATION":
                insert(conn, "CALIBRATION", dict(Calibration_Date=d(-2), Next_Due_Date=d(363),
                                                 Technician_Name="Arjun Singh", Status="IN_PROGRESS",
                                                 Equipment_ID=e["id"]))

        # ---------------- Asset transfers (consistent with current lab) ----------------
        movable = [e for e in equipment if e["status"] not in ("RETIRED",)]
        for e in rng.sample(movable, 5):
            src = rng.choice([lab for lab in lab_ids if lab != e["lab"]])
            insert(conn, "ASSET_TRANSFER", dict(
                Equipment_ID=e["id"], From_Lab_ID=src, To_Lab_ID=e["lab"], Transfer_Date=d(-rng.randint(20, 300)),
                Reason=rng.choice(["Course requirement", "Research project allocation", "Lab consolidation",
                                   "Space optimisation"]),
                Approved_By=rng.choice(["Rahul Verma", "Sanjay Gupta"]), Technician_Name=rng.choice(technicians),
                Status="COMPLETED"))
        for e, status in zip(rng.sample(movable, 2), ["PENDING", "REJECTED"]):
            dst = rng.choice([lab for lab in lab_ids if lab != e["lab"]])
            insert(conn, "ASSET_TRANSFER", dict(
                Equipment_ID=e["id"], From_Lab_ID=e["lab"], To_Lab_ID=dst, Transfer_Date=d(rng.randint(-10, 10)),
                Reason="Requested for upcoming project work", Approved_By=None if status == "PENDING" else "Rahul Verma",
                Technician_Name=rng.choice(technicians), Status=status))

        # ---------------- Consumables ----------------
        for item, cat, unit, qty, reorder, lab in [
            ("Isopropyl Alcohol 99%", "Chemical", "L", 4, 5, "Embedded Systems Lab"),
            ("Solder Wire 0.8 mm", "Electronic Component", "roll", 12, 5, "Embedded Systems Lab"),
            ("Breadboards (full size)", "Electronic Component", "pcs", 45, 20, "Embedded Systems Lab"),
            ("Resistor Assortment Kit", "Electronic Component", "box", 3, 4, "Embedded Systems Lab"),
            ("Cat6 Patch Cables 2 m", "Cable", "pcs", 80, 30, "Computer Networks Lab"),
            ("RJ45 Connectors", "Cable", "pack", 6, 5, "Computer Networks Lab"),
            ("PLA Filament 1.75 mm", "Other", "kg", 2, 6, "Manufacturing Lab"),
            ("End Mill Set (HSS)", "Other", "box", 5, 2, "Manufacturing Lab"),
            ("Cutting Fluid", "Chemical", "L", 18, 10, "Manufacturing Lab"),
            ("Safety Goggles", "Safety Supply", "pcs", 25, 15, "Manufacturing Lab"),
            ("Nitrile Gloves (M)", "Safety Supply", "box", 9, 10, "Materials Testing Lab"),
            ("Tensile Test Specimens", "Other", "pcs", 60, 25, "Materials Testing Lab"),
            ("Lens Cleaning Tissue", "Stationery", "pack", 14, 5, "Optics & Photonics Lab"),
            ("Optical Fibre Patch Cords", "Cable", "pcs", 22, 10, "Optics & Photonics Lab"),
            ("Thermal Paste", "Electronic Component", "pcs", 7, 3, "AI & Data Science Lab"),
            ("Lab Notebooks", "Stationery", "pcs", 30, 10, "AI & Data Science Lab"),
        ]:
            insert(conn, "CONSUMABLE", dict(Item_Name=item, Category=cat, Unit=unit, Quantity=qty,
                                            Reorder_Level=reorder, Lab_ID=labs[lab]))

        # ---------------- Audit trail history ----------------
        conn.execute("INSERT INTO AUDIT_LOG (Action_Performed, Date_Time, IP_Address, Remarks, User_ID) "
                     "VALUES ('SEED DATABASE', ?, '127.0.0.1', 'Sample data loaded by seed.py', ?)",
                     (f"{d(-60)} 08:00:00", users["admin"]))
        for offset in range(-60, 0):
            for key in rng.sample(list(users), rng.randint(1, 4)):
                stamp = f"{d(offset)} {rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
                conn.execute("INSERT INTO AUDIT_LOG (Action_Performed, Date_Time, IP_Address, Remarks, User_ID) "
                             "VALUES ('LOGIN', ?, ?, 'User signed in', ?)",
                             (stamp, f"10.0.{rng.randint(1, 9)}.{rng.randint(2, 250)}", users[key]))
        conn.execute("UPDATE ADMINISTRATOR SET Last_Login = ?", (f"{d(-1)} 09:12:44",))

    import alerts  # imported late: alerts reads the freshly seeded tables

    alerts.generate_notifications()


def ensure_database():
    """Create schema + sample data if the database does not exist yet; otherwise apply pending migrations."""
    if db.schema_exists():
        db.migrate()
        return False
    db.create_schema()
    seed()
    return True


def rebuild():
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.create_schema()
    seed()


if __name__ == "__main__":
    rebuild()
    counts = {t: db.scalar(f"SELECT COUNT(*) FROM {t}") for t in [
        "ORGANIZATION", "DEPARTMENT", "LABORATORY", "ROLE", "LAB_USER", "ADMINISTRATOR", "LAB_MANAGER",
        "LAB_TECHNICIAN", "RESEARCHER", "FACULTY", "VENDOR", "EQUIPMENT_CATEGORY", "EQUIPMENT",
        "COMPUTING_EQUIPMENT", "ELECTRONIC_EQUIPMENT", "MECHANICAL_EQUIPMENT", "MEASURING_INSTRUMENT",
        "MEDICAL_EQUIPMENT",
        "CONSUMABLE", "EQUIPMENT_BOOKING", "CALIBRATION", "ASSET_TRANSFER", "MAINTENANCE", "WARRANTY",
        "AUDIT_LOG", "NOTIFICATION"]}
    print(f"Database rebuilt at {db.DB_PATH}")
    for table, n in counts.items():
        print(f"  {table:<22} {n:>5}")
    print(f"Sign in with admin@smartlab.edu / {DEMO_PASSWORD}")
