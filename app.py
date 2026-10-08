from flask import Flask, jsonify, request, render_template
import sqlite3
import csv
import io
from datetime import datetime

app = Flask(__name__, static_folder="static", template_folder="templates")

DATABASE = "healthinsight.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            age INTEGER,
            gender TEXT,
            department TEXT,
            diagnosis TEXT,
            admission_date TEXT,
            discharge_date TEXT,
            admission_type TEXT,
            length_of_stay INTEGER,
            previous_visits INTEGER,
            insurance_type TEXT,
            treatment_cost REAL,
            readmission INTEGER
        )
    """)

    count = conn.execute(
        "SELECT COUNT(*) FROM health_records"
    ).fetchone()[0]

    if count == 0:
        departments = [
            "General Medicine",
            "Cardiology",
            "Orthopedics",
            "Pediatrics",
            "Neurology",
            "Emergency"
        ]

        diagnoses = [
            "Hypertension",
            "Diabetes",
            "Respiratory Infection",
            "Fracture",
            "Heart Disease",
            "Migraine",
            "Asthma",
            "Gastrointestinal"
        ]

        admissions = ["Emergency", "Elective", "Urgent"]
        insurance = ["Private", "Government", "Employer", "Self Pay"]

        for g in range(1, 1201):
            age = 18 + ((g * 17) % 68)

            gender = "Female" if g % 2 == 0 else "Male"

            department = departments[g % 6]

            diagnosis = diagnoses[g % 8]

            admission_type = admissions[g % 3]

            insurance_type = insurance[g % 4]

            length_of_stay = 2 + ((g * 7) % 13)

            previous_visits = (g * 3) % 9

            treatment_cost = (
                3500
                + ((g * 941) % 42000)
                + ((g % 6) * 725)
            )

            admission_date = (
                datetime(2023, 1, 1).date()
            )

            day_offset = (g * 11) % 1095

            from datetime import timedelta

            admission_date = admission_date + timedelta(
                days=day_offset
            )

            discharge_date = admission_date + timedelta(
                days=length_of_stay
            )

            readmission = 1 if ((g * 13) % 100) < (8 + (g % 7)) else 0

            conn.execute("""
                INSERT INTO health_records
                (
                    patient_id,
                    age,
                    gender,
                    department,
                    diagnosis,
                    admission_date,
                    discharge_date,
                    admission_type,
                    length_of_stay,
                    previous_visits,
                    insurance_type,
                    treatment_cost,
                    readmission
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"SYN-{g:06d}",
                age,
                gender,
                department,
                diagnosis,
                admission_date.isoformat(),
                discharge_date.isoformat(),
                admission_type,
                length_of_stay,
                previous_visits,
                insurance_type,
                treatment_cost,
                readmission
            ))

    conn.commit()
    conn.close()
@app.route("/")
def home():
    return render_template("index.html")
    

@app.route("/api/analytics")
def analytics():

    conn = get_db()

    gender = request.args.get("gender")
    department = request.args.get("department")
    diagnosis = request.args.get("diagnosis")
    insurance = request.args.get("insurance")
    admission_type = request.args.get("admissionType")
    age_group = request.args.get("ageGroup")
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")

    conditions = []
    values = []

    if gender and gender != "All":
        conditions.append("gender = ?")
        values.append(gender)

    if department and department != "All":
        conditions.append("department = ?")
        values.append(department)

    if diagnosis and diagnosis != "All":
        conditions.append("diagnosis = ?")
        values.append(diagnosis)

    if insurance and insurance != "All":
        conditions.append("insurance_type = ?")
        values.append(insurance)

    if admission_type and admission_type != "All":
        conditions.append("admission_type = ?")
        values.append(admission_type)

    age_ranges = {
        "18–29": (18, 29),
        "30–44": (30, 44),
        "45–59": (45, 59),
        "60–74": (60, 74),
        "75+": (75, 150)
    }

    if age_group in age_ranges:
        low, high = age_ranges[age_group]
        conditions.append("age BETWEEN ? AND ?")
        values.extend([low, high])

    if start_date:
        conditions.append("admission_date >= ?")
        values.append(start_date)

    if end_date:
        conditions.append("admission_date <= ?")
        values.append(end_date)

    where = ""

    if conditions:
        where = " WHERE " + " AND ".join(conditions)

    kpi = conn.execute(f"""
        SELECT
            COUNT(*) AS total_patients,
            ROUND(AVG(age), 1) AS avg_age,
            ROUND(AVG(length_of_stay), 1) AS avg_los,
            COUNT(*) AS total_visits,
            ROUND(
                100.0 * AVG(readmission),
                1
            ) AS readmission_rate,
            ROUND(AVG(treatment_cost), 0) AS avg_cost
        FROM health_records
        {where}
    """, values).fetchone()

    age_groups = conn.execute(f"""
        SELECT
            CASE
                WHEN age < 30 THEN '18–29'
                WHEN age < 45 THEN '30–44'
                WHEN age < 60 THEN '45–59'
                WHEN age < 75 THEN '60–74'
                ELSE '75+'
            END AS age_group,
            COUNT(*) AS value
        FROM health_records
        {where}
        GROUP BY age_group
        ORDER BY MIN(age)
    """, values).fetchall()

    departments = conn.execute(f"""
        SELECT
            department,
            COUNT(*) AS visits,
            ROUND(AVG(length_of_stay), 1) AS avg_los,
            ROUND(AVG(treatment_cost), 0) AS avg_cost
        FROM health_records
        {where}
        GROUP BY department
        ORDER BY visits DESC
    """, values).fetchall()

    diagnoses = conn.execute(f"""
        SELECT
            diagnosis,
            COUNT(*) AS value
        FROM health_records
        {where}
        GROUP BY diagnosis
        ORDER BY value DESC
    """, values).fetchall()

    monthly = conn.execute(f"""
        SELECT
            substr(admission_date, 1, 7) AS month_label,
            COUNT(*) AS visits,
            ROUND(AVG(treatment_cost), 0) AS avg_cost
        FROM health_records
        {where}
        GROUP BY month_label
        ORDER BY month_label
    """, values).fetchall()

    options = {}

    for column, key in [
        ("gender", "genders"),
        ("department", "departments"),
        ("diagnosis", "diagnoses"),
        ("insurance_type", "insurance"),
        ("admission_type", "admission_types")
    ]:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM health_records ORDER BY {column}"
        ).fetchall()

        options[key] = [row[0] for row in rows]

    gender_data = conn.execute(f"""
        SELECT gender, COUNT(*) AS value
        FROM health_records
        {where}
        GROUP BY gender
        ORDER BY gender
    """, values).fetchall()

    admission_data = conn.execute(f"""
        SELECT admission_type, COUNT(*) AS value
        FROM health_records
        {where}
        GROUP BY admission_type
        ORDER BY admission_type
    """, values).fetchall()

    insurance_data = conn.execute(f"""
        SELECT insurance_type, COUNT(*) AS value
        FROM health_records
        {where}
        GROUP BY insurance_type
        ORDER BY insurance_type
    """, values).fetchall()

    conn.close()

    return jsonify({
        "kpis": dict(kpi),
        "ageGroups": [dict(x) for x in age_groups],
        "departments": [dict(x) for x in departments],
        "diagnoses": [dict(x) for x in diagnoses],
        "monthly": [dict(x) for x in monthly],
        "options": options,
        "genderData": [dict(x) for x in gender_data],
        "admissionData": [dict(x) for x in admission_data],
        "insuranceData": [dict(x) for x in insurance_data],
        "disclaimer": (
            "For educational and demonstration purposes only. "
            "This application does not provide medical diagnosis "
            "or treatment advice."
        )
    })


@app.route("/api/upload", methods=["POST"])
def upload():

    data = request.get_json()

    rows = data.get("rows", []) if data else []

    if not rows:
        return jsonify({"error": "No rows supplied"}), 400

    required = [
        "Patient_ID",
        "Age",
        "Gender",
        "Department",
        "Diagnosis",
        "Admission_Date",
        "Discharge_Date",
        "Admission_Type",
        "Length_of_Stay",
        "Previous_Visits",
        "Insurance_Type",
        "Treatment_Cost",
        "Readmission"
    ]

    missing = [
        column for column in required
        if column not in rows[0]
    ]

    if missing:
        return jsonify({
            "error": "Missing columns",
            "missing": missing
        }), 400

    conn = get_db()

    inserted = 0
    invalid = 0

    for row in rows[:5000]:

        try:
            age = int(row["Age"])
            los = int(row["Length_of_Stay"])
            previous = int(row.get("Previous_Visits", 0))
            cost = float(row["Treatment_Cost"])

            if (
                not row["Patient_ID"]
                or not row["Admission_Date"]
                or not row["Discharge_Date"]
            ):
                invalid += 1
                continue

            readmission = str(
                row["Readmission"]
            ).lower() in ["true", "1", "yes"]

            conn.execute("""
                INSERT INTO health_records
                (
                    patient_id,
                    age,
                    gender,
                    department,
                    diagnosis,
                    admission_date,
                    discharge_date,
                    admission_type,
                    length_of_stay,
                    previous_visits,
                    insurance_type,
                    treatment_cost,
                    readmission
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row["Patient_ID"]),
                age,
                str(row["Gender"]),
                str(row["Department"]),
                str(row["Diagnosis"]),
                row["Admission_Date"],
                row["Discharge_Date"],
                str(row["Admission_Type"]),
                los,
                previous,
                str(row["Insurance_Type"]),
                cost,
                readmission
            ))

            inserted += 1

        except (ValueError, TypeError, KeyError):
            invalid += 1

    conn.commit()
    conn.close()

    return jsonify({
        "inserted": inserted,
        "invalid": invalid,
        "received": len(rows)
    })


initialize_database()

if __name__ == "__main__":

    print("\nHealthInsight is starting...")
    print("Open: http://127.0.0.1:5000\n")

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )