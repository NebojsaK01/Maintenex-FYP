from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector # for connect to the mySQL DB
from werkzeug.security import generate_password_hash, check_password_hash
# for hashing the password and changing passwords.
import smtplib
import string
import random
from email.mime.text import MIMEText
from flask import request, flash
from datetime import date # neeeded for dashboard to check service dates, and for service asset to set last/next service dates.
from datetime import datetime, timedelta # also for service asset to set last/next service dates, and for asset history to log change dates.

import os
import joblib # for loading model but not  using anymore after experimentation.
import pandas as pd
import math
from flask import jsonify

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Load model


@app.route("/synthetic-machine")
def synthetic_machine():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("synthetic_machine.html")


def smooth_score(value, low_start, high_end):
    """
    Returns a smooth 0..1 score.
    - below low_start => near 0
    - above high_end => near 1
    - between => gradual rise
    """
    if value <= low_start:
        return 0.0
    if value >= high_end:
        return 1.0

    x = (value - low_start) / (high_end - low_start)
    # Smoothstep curve: softer than a hard threshold
    return x * x * (3 - 2 * x)


def rpm_risk_score(rpm):
    """
    Low risk near ideal center.
    Gradually rises as rpm moves away from safe band.
    """
    ideal_low = 1420
    ideal_high = 1480
    critical_low = 1380
    critical_high = 1500

    if ideal_low <= rpm <= ideal_high:
        return 0.0

    if rpm < ideal_low:
        return smooth_score(ideal_low - rpm, 0, ideal_low - critical_low)

    return smooth_score(rpm - ideal_high, 0, critical_high - ideal_high)


@app.route("/api/synthetic-machine-predict", methods=["POST"])
def synthetic_machine_predict():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}

    try:
        temperature = float(data.get("temperature", 65))
        vibration = float(data.get("vibration", 0.10))
        rpm = float(data.get("rpm", 1450))
        load = float(data.get("load", 70))
        days_since_service = int(data.get("days_since_service", 30))
    except ValueError:
        return jsonify({"error": "Invalid input values"}), 400

    # Individual smooth risk components (0..1)
    temp_score = smooth_score(temperature, 65, 90)
    vib_score = smooth_score(vibration, 0.10, 0.40)
    load_score = smooth_score(load, 60, 98)
    days_score = smooth_score(days_since_service, 20, 180)
    rpm_score = rpm_risk_score(rpm)

    # Weighted blend
    weighted = (
        temp_score * 0.24 +
        vib_score * 0.30 +
        rpm_score * 0.16 +
        load_score * 0.18 +
        days_score * 0.12
    )

    # Interaction bonus: risky combinations should matter more
    combo_bonus = 0.0

    if temperature > 75 and vibration > 0.18:
        combo_bonus += 0.08
    if load > 85 and days_since_service > 120:
        combo_bonus += 0.07
    if vibration > 0.25 and rpm_score > 0.5:
        combo_bonus += 0.08
    if temperature > 82 and load > 90:
        combo_bonus += 0.07

    raw_risk = min(1.0, weighted + combo_bonus)

    # Gentle curve so the UI feels more responsive without becoming a switch
    risk_probability = min(1.0, math.pow(raw_risk, 0.85))

    if risk_probability >= 0.75:
        status = "High Risk"
    elif risk_probability >= 0.40:
        status = "Warning"
    else:
        status = "Healthy"

    reasons = []

    if temperature >= 82:
        reasons.append("Temperature is critically high")
    elif temperature >= 75:
        reasons.append("Temperature is elevated")

    if vibration >= 0.25:
        reasons.append("Vibration is critically high")
    elif vibration >= 0.18:
        reasons.append("Vibration is elevated")

    if rpm < 1380 or rpm > 1500:
        reasons.append("RPM is in a critical range")
    elif rpm < 1420 or rpm > 1480:
        reasons.append("RPM is outside the ideal range")

    if load >= 95:
        reasons.append("Load is critically high")
    elif load >= 85:
        reasons.append("Load is elevated")

    if days_since_service >= 160:
        reasons.append("Machine is long overdue for service")
    elif days_since_service >= 120:
        reasons.append("Machine has been running a long time since last service")

    if not reasons:
        reasons.append("Machine is operating within normal conditions")

    return jsonify({
        "risk_probability": round(risk_probability * 100, 2),
        "status": status,
        "reasons": reasons,
        "component_scores": {
            "temperature": round(temp_score * 100, 1),
            "vibration": round(vib_score * 100, 1),
            "rpm": round(rpm_score * 100, 1),
            "load": round(load_score * 100, 1),
            "days_since_service": round(days_score * 100, 1),
        }
    })






# for hosting
def get_db():
    return mysql.connector.connect(
        host="Nebojsa.mysql.pythonanywhere-services.com",
        user="Nebojsa",
        password="Password123",
        database="Nebojsa$maintenance_app"
    )






# Home route
@app.route("/")
def home():
    return redirect(url_for("login"))

# for the login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_email = request.form.get("user_email")
        password = request.form.get("password")

        if not user_email or not password:
            return render_template("login.html", error="Please enter email and password")

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_email = %s", (user_email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["password"], password):
            # Store full_name in session
            session["user_id"] = user["id"]
            session["user_email"] = user["user_email"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"] # 4 privileges: admin, technician, supervisor
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")



@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        if not email:
            flash("Please enter your email.")
            return redirect(url_for("forgot_password"))

        # Connect to DB
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            flash("Email not found.")
            cursor.close()
            db.close()
            return redirect(url_for("forgot_password"))

        # Generate a random temporary password
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        hashed_password = generate_password_hash(temp_password)

        # Update user's password in DB
        cursor.execute(
            "UPDATE users SET password = %s WHERE user_email = %s",
            (hashed_password, email)
        )
        db.commit()
        cursor.close()
        db.close()

        # Try to send the email
        try:
            send_reset_email(email, temp_password)
            flash("A temporary password has been sent to your email.")
        except Exception as e:
            print("SMTP error:", e)
            flash("Could not send email. Please contact support.")

        return redirect(url_for("login"))

    return render_template("forgot_password.html")








@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch user info
    cursor.execute("SELECT full_name FROM users WHERE id = %s", (session["user_id"],))
    user = cursor.fetchone()
    full_name = user["full_name"] if user else "User"

    today = date.today()
    next_7_days = today + timedelta(days=7)

    # Total assets
    cursor.execute("SELECT COUNT(*) AS total_assets FROM assets")
    total_assets = cursor.fetchone()["total_assets"]

    # Overdue services
    cursor.execute("""
        SELECT COUNT(*) AS overdue_count
        FROM assets
        WHERE next_service_date IS NOT NULL
          AND next_service_date < %s
    """, (today,))
    overdue_count = cursor.fetchone()["overdue_count"]

    # Upcoming services (next 7 days)
    cursor.execute("""
        SELECT COUNT(*) AS upcoming_count
        FROM assets
        WHERE next_service_date IS NOT NULL
          AND next_service_date >= %s
          AND next_service_date <= %s
    """, (today, next_7_days))
    upcoming_count = cursor.fetchone()["upcoming_count"]

    # Asset status counts
    cursor.execute("""
        SELECT
            SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active_assets,
            SUM(CASE WHEN status = 'Maintenance' THEN 1 ELSE 0 END) AS maintenance_assets,
            SUM(CASE WHEN status = 'Inactive' THEN 1 ELSE 0 END) AS inactive_assets,
            SUM(CASE WHEN status = 'Retired' THEN 1 ELSE 0 END) AS retired_assets,
            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending_assets
        FROM assets
    """)
    status_counts = cursor.fetchone()

    active_assets = status_counts["active_assets"] or 0
    maintenance_assets = status_counts["maintenance_assets"] or 0
    inactive_assets = status_counts["inactive_assets"] or 0
    retired_assets = status_counts["retired_assets"] or 0
    pending_assets = status_counts["pending_assets"] or 0

    # Asset type breakdown
    cursor.execute("""
        SELECT asset_type, COUNT(*) AS count
        FROM assets
        GROUP BY asset_type
        ORDER BY count DESC
    """)
    asset_type_counts = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",
        full_name=full_name,
        total_assets=total_assets,
        overdue_count=overdue_count,
        upcoming_count=upcoming_count,
        active_assets=active_assets,
        maintenance_assets=maintenance_assets,
        inactive_assets=inactive_assets,
        retired_assets=retired_assets,
        pending_assets=pending_assets,
        asset_type_counts=asset_type_counts
    )






# Profile route
@app.route("/profile", methods=["GET", "POST"])
def profile():
    # Must be logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch user info including password
    cursor.execute(
        "SELECT full_name, user_email, password FROM users WHERE id = %s",
        (session["user_id"],)
    )
    user = cursor.fetchone()

    # Initialize messages
    error = None
    message = None

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Validation
        if not current_password or not new_password or not confirm_password:
            error = "All fields are required."
        elif new_password != confirm_password:
            error = "New passwords do not match."
        elif not check_password_hash(user["password"], current_password):
            error = "Current password is incorrect."
        else:
            # Update password
            new_hashed = generate_password_hash(new_password)
            cursor.execute(
                "UPDATE users SET password = %s WHERE id = %s",
                (new_hashed, session["user_id"])
            )
            db.commit()
            message = "Password updated successfully!"

    cursor.close()
    db.close()

    return render_template("profile.html", user=user, error=error, message=message)


@app.route("/alerts")
def alerts():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch assets that are due soon or overdue
    cursor.execute("""
        SELECT id, asset_code, name, next_service_date, last_service_date
        FROM assets
        WHERE next_service_date <= CURDATE() + INTERVAL 7 DAY
        ORDER BY next_service_date ASC
    """)
    assets_due = cursor.fetchall()
    cursor.close()
    db.close()

    # Assign priority based on how overdue it is
    alerts_list = []
    from datetime import datetime, date

    for asset in assets_due:
        next_service = asset["next_service_date"]
        if isinstance(next_service, str):
            next_service = datetime.strptime(next_service, "%Y-%m-%d").date()
        
        today = date.today()
        days_diff = (next_service - today).days

        if days_diff < 0: # if it's already overdue, it's high priority
            priority = "High"
        elif days_diff <= 7: # if it's due within the next week, it's medium priority
            priority = "Medium"
        else:
            priority = "Low"

        alerts_list.append({
            "asset_code": asset["asset_code"],
            "priority": priority,
            "next_service_date": next_service.strftime("%Y-%m-%d")
        })

    return render_template("alerts.html", alerts=alerts_list)





# Technicians route
@app.route("/technicians")
def technicians():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM technicians")
    technicians = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("technicians.html", technicians=technicians)

@app.route("/add-technician", methods=["POST"])
def add_technician():
    if "user_id" not in session:
        return redirect(url_for("login"))

    name = request.form.get("name")
    email = request.form.get("email")

    if not name or not email:
        return redirect(url_for("technicians"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "INSERT INTO technicians (name, email) VALUES (%s, %s)",
        (name, email)
    )

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("technicians"))

@app.route("/delete-technician/<int:tech_id>", methods=["POST"])
def delete_technician(tech_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM technicians WHERE id = %s", (tech_id,))
    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for("technicians"))







# Helper: get current user's display name for history
def get_current_user_name():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT full_name FROM users WHERE id = %s", (session["user_id"],))
    user = cursor.fetchone()
    cursor.close()
    db.close()
    return user["full_name"] if user and user.get("full_name") else "Unknown User"



# Helper: insert asset history row
def log_asset_history(cursor, asset_id, changed_by, action, field_changed=None, old_value=None, new_value=None):
    cursor.execute("""
        INSERT INTO asset_history (
            asset_id,
            changed_by,
            action,
            field_changed,
            old_value,
            new_value
        )
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        asset_id,
        changed_by,
        action,
        field_changed,
        str(old_value) if old_value is not None else None,
        str(new_value) if new_value is not None else None
    ))



# Assets route with search
@app.route("/assets")
def assets():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    search_query = request.args.get("q", "").strip()

    if search_query:
        like_term = f"%{search_query}%"
        cursor.execute("""
            SELECT * FROM assets
            WHERE asset_code LIKE %s
               OR name LIKE %s
               OR asset_type LIKE %s
               OR serial_number LIKE %s
               OR identifier LIKE %s
               OR location LIKE %s
               OR manufacturer LIKE %s
               OR model LIKE %s
               OR status LIKE %s
            ORDER BY id DESC
        """, (
            like_term, like_term, like_term, like_term, like_term,
            like_term, like_term, like_term, like_term
        ))
    else:
        cursor.execute("SELECT * FROM assets ORDER BY id DESC")

    assets_list = cursor.fetchall()

    today = date.today()
    for asset in assets_list:
        asset["is_overdue"] = False
        asset["is_due_soon"] = False

        next_service = asset.get("next_service_date")
        if next_service:
            if isinstance(next_service, str):
                next_service = date.fromisoformat(next_service)

            if next_service < today:
                asset["is_overdue"] = True
            elif today <= next_service <= today + timedelta(days=7):
                asset["is_due_soon"] = True

    cursor.close()
    db.close()

    return render_template("assets.html", assets=assets_list)


# Add Asset
@app.route("/add-asset", methods=["POST"])
def add_asset():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") not in ["admin", "supervisor"]:
        return "Unauthorized", 403

    asset_type = request.form.get("asset_type")
    name = request.form.get("name")
    serial_number = request.form.get("serial_number")
    identifier = request.form.get("identifier")
    location = request.form.get("location")
    manufacturer = request.form.get("manufacturer")
    model = request.form.get("model")
    purchase_date = request.form.get("purchase_date") or None
    status = request.form.get("status")
    last_service_date = request.form.get("last_service_date") or None
    next_service_date = request.form.get("next_service_date") or None

    if not name or not asset_type:
        return redirect(url_for("assets"))

    db = get_db()
    cursor = db.cursor()

    current_year = datetime.now().year

    cursor.execute("""
        SELECT asset_code FROM assets
        WHERE asset_code LIKE %s
        ORDER BY asset_code DESC
        LIMIT 1
    """, (f"{current_year}-%",))
    last = cursor.fetchone()

    if last and last[0]:
        last_number = int(last[0].split("-")[1])
        next_number = last_number + 1
    else:
        next_number = 1

    asset_code = f"{current_year}-{next_number:08d}"

    cursor.execute("""
        INSERT INTO assets (
            asset_code, asset_type, name, serial_number, identifier,
            location, manufacturer, model, purchase_date, status,
            last_service_date, next_service_date
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        asset_code, asset_type, name, serial_number, identifier,
        location, manufacturer, model, purchase_date, status,
        last_service_date, next_service_date
    ))

    new_asset_id = cursor.lastrowid
    changed_by = get_current_user_name()

    log_asset_history(
        cursor=cursor,
        asset_id=new_asset_id,
        changed_by=changed_by,
        action="Created",
        field_changed="asset",
        old_value="",
        new_value=f"Asset {asset_code} created"
    )

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("assets"))



# Delete Asset
@app.route("/delete-asset/<int:asset_id>", methods=["POST"])
def delete_asset(asset_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") not in ["admin", "supervisor"]:
        return "Unauthorized", 403

    changed_by = get_current_user_name()

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM assets WHERE id = %s", (asset_id,))
    asset = cursor.fetchone()

    if not asset:
        cursor.close()
        db.close()
        return redirect(url_for("assets"))

    # Log deletion before deleting asset
    log_asset_history(
        cursor=cursor,
        asset_id=asset_id,
        changed_by=changed_by,
        action="Deleted",
        field_changed="asset",
        old_value=asset.get("name"),
        new_value="Asset removed"
    )

    cursor.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for("assets"))



# Edit Asset
@app.route("/edit-asset/<int:asset_id>", methods=["POST"])
def edit_asset(asset_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") not in ["admin", "supervisor"]:
        return "Unauthorized", 403

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM assets WHERE id = %s", (asset_id,))
    old_asset = cursor.fetchone()

    if not old_asset:
        cursor.close()
        db.close()
        return "Asset not found", 404

    changed_by = get_current_user_name()

    new_data = {
        "asset_type": request.form.get("asset_type"),
        "name": request.form.get("name"),
        "serial_number": request.form.get("serial_number"),
        "identifier": request.form.get("identifier"),
        "location": request.form.get("location"),
        "manufacturer": request.form.get("manufacturer"),
        "model": request.form.get("model"),
        "purchase_date": request.form.get("purchase_date") or None,
        "status": request.form.get("status"),
        "last_service_date": request.form.get("last_service_date") or None,
        "next_service_date": request.form.get("next_service_date") or None
    }

    cursor.execute("""
        UPDATE assets
        SET asset_type = %s,
            name = %s,
            serial_number = %s,
            identifier = %s,
            location = %s,
            manufacturer = %s,
            model = %s,
            purchase_date = %s,
            status = %s,
            last_service_date = %s,
            next_service_date = %s
        WHERE id = %s
    """, (
        new_data["asset_type"],
        new_data["name"],
        new_data["serial_number"],
        new_data["identifier"],
        new_data["location"],
        new_data["manufacturer"],
        new_data["model"],
        new_data["purchase_date"],
        new_data["status"],
        new_data["last_service_date"],
        new_data["next_service_date"],
        asset_id
    ))

    tracked_fields = [
        "asset_type",
        "name",
        "serial_number",
        "identifier",
        "location",
        "manufacturer",
        "model",
        "purchase_date",
        "status",
        "last_service_date",
        "next_service_date"
    ]

    for field in tracked_fields:
        old_value = old_asset.get(field)
        new_value = new_data.get(field)

        old_str = "" if old_value is None else str(old_value)
        new_str = "" if new_value is None else str(new_value)

        if old_str != new_str:
            log_asset_history(
                cursor=cursor,
                asset_id=asset_id,
                changed_by=changed_by,
                action="Edited",
                field_changed=field,
                old_value=old_str,
                new_value=new_str
            )

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("assets"))



# View Asset History (JSON for frontend)
@app.route("/asset-history/<int:asset_id>")
def asset_history(asset_id):
    if "user_id" not in session:
        return jsonify({"history": []}), 401

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
    SELECT
        id,
        asset_id,
        changed_by,
        action,
        field_changed,
        old_value,
        new_value,
        DATE_FORMAT(change_date, '%Y-%m-%d %H:%i') AS change_date
        FROM asset_history
        WHERE asset_id = %s
        ORDER BY change_date DESC, id DESC
    """, (asset_id,))

    history = cursor.fetchall()

    cursor.close()
    db.close()

    return jsonify({"history": history})



# Service Asset
@app.route("/service-asset/<int:asset_id>", methods=["POST"])
def service_asset(asset_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM assets WHERE id = %s", (asset_id,))
    asset = cursor.fetchone()

    if not asset:
        cursor.close()
        db.close()
        return "Asset not found", 404

    try:
        interval_days = int(request.form.get("interval_days", 30))
    except ValueError:
        interval_days = 30

    today = datetime.today().date()
    next_service = today + timedelta(days=interval_days)
    changed_by = get_current_user_name()

    old_last_service = asset.get("last_service_date")
    old_next_service = asset.get("next_service_date")
    old_status = asset.get("status")

    cursor.execute("""
        UPDATE assets
        SET last_service_date = %s,
            next_service_date = %s,
            status = %s
        WHERE id = %s
    """, (today, next_service, "Active", asset_id))

    if str(old_last_service or "") != str(today):
        log_asset_history(
            cursor=cursor,
            asset_id=asset_id,
            changed_by=changed_by,
            action="Serviced",
            field_changed="last_service_date",
            old_value=old_last_service,
            new_value=today
        )

    if str(old_next_service or "") != str(next_service):
        log_asset_history(
            cursor=cursor,
            asset_id=asset_id,
            changed_by=changed_by,
            action="Serviced",
            field_changed="next_service_date",
            old_value=old_next_service,
            new_value=next_service
        )

    if str(old_status or "") != "Active":
        log_asset_history(
            cursor=cursor,
            asset_id=asset_id,
            changed_by=changed_by,
            action="Serviced",
            field_changed="status",
            old_value=old_status,
            new_value="Active"
        )

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("assets"))









@app.route("/employees")
def employees():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT full_name, user_email, phone, role FROM users ORDER BY role, full_name")
    users = cursor.fetchall()
    cursor.close()
    db.close()

    # Segment users by role
    segmented = {
        "admin": [],
        "supervisor": [],
        "technician": []
    }

    for user in users:
        role = user["role"].lower()
        if role == "admin":
            segmented["admin"].append(user)
        elif role == "supervisor":
            segmented["supervisor"].append(user)
        elif role == "technician":
            segmented["technician"].append(user)

    return render_template("employees.html", segmented=segmented)



# Employee management routes (Admin only)

@app.route("/employee-management")
def employee_management():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied. Admins only.")
        return redirect(url_for("dashboard"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, full_name, user_email, phone, role
        FROM users
        ORDER BY full_name
    """)
    users = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("employee_management.html", users=users)


@app.route("/add-employee", methods=["POST"])
def add_employee():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied. Admins only.")
        return redirect(url_for("dashboard"))

    full_name = request.form.get("full_name", "").strip()
    user_email = request.form.get("user_email", "").strip()
    phone = request.form.get("phone", "").strip()
    role = request.form.get("role", "").strip()
    password = request.form.get("password", "").strip()

    if not full_name or not user_email or not role or not password:
        flash("Please fill in all required fields.")
        return redirect(url_for("employee_management"))

    hashed_password = generate_password_hash(password)

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT id FROM users WHERE user_email = %s", (user_email,))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        db.close()
        flash("A user with that email already exists.")
        return redirect(url_for("employee_management"))

    cursor.execute("""
        INSERT INTO users (full_name, user_email, phone, role, password)
        VALUES (%s, %s, %s, %s, %s)
    """, (full_name, user_email, phone, role, hashed_password))

    db.commit()
    cursor.close()
    db.close()

    flash("Employee added successfully.")
    return redirect(url_for("employee_management"))


@app.route("/edit-employee/<int:user_id>", methods=["POST"])
def edit_employee(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied. Admins only.")
        return redirect(url_for("dashboard"))

    full_name = request.form.get("full_name", "").strip()
    user_email = request.form.get("user_email", "").strip()
    phone = request.form.get("phone", "").strip()
    role = request.form.get("role", "").strip()

    if not full_name or not user_email or not role:
        flash("Please fill in all required fields.")
        return redirect(url_for("employee_management"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id FROM users
        WHERE user_email = %s AND id != %s
    """, (user_email, user_id))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        db.close()
        flash("Another user already has that email.")
        return redirect(url_for("employee_management"))

    cursor.execute("""
        UPDATE users
        SET full_name = %s,
            user_email = %s,
            phone = %s,
            role = %s
        WHERE id = %s
    """, (full_name, user_email, phone, role, user_id))

    db.commit()
    cursor.close()
    db.close()

    flash("Employee updated successfully.")
    return redirect(url_for("employee_management"))


@app.route("/delete-employee/<int:user_id>", methods=["POST"])
def delete_employee(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied. Admins only.")
        return redirect(url_for("dashboard"))

    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.")
        return redirect(url_for("employee_management"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()

    cursor.close()
    db.close()

    flash("Employee removed successfully.")
    return redirect(url_for("employee_management"))









# Logout route
@app.route("/logout")
def logout():
    session.clear() # clear the session.
    return redirect(url_for("login"))















if __name__ == "__main__":
    app.run(debug=True) 
