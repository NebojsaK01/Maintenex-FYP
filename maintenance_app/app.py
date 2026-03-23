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
from datetime import datetime, timedelta


app = Flask(__name__)
app.secret_key = "your_secret_key_here"







def send_reset_email(to_email, temp_password):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SMTP_USER = "nebojsakukic2@gmail.com"
    SMTP_PASSWORD = "dxxr hdrq pkfu hcxg"  # App password for my Gmail -->

    # Extract name from email (before @)
    name = to_email.split('@')[0]

    subject = "Your Temporary Password"
    body = f"""
            Hello {name},

            Your temporary password is: {temp_password}

            Please login using this password and change it immediately.

            Kind regards,
            The Maintenex Team
            """

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_email

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        server.quit()
        print(f"Temporary password sent to {to_email}")
    except Exception as e:
        print("Error sending email:", e)










# Connect to MySQL -> (XAMPP)
def get_db():
    return mysql.connector.connect(
        host="localhost", # simple 4 now.
        user="root",
        password="",
        database="maintenance_app",
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






# Dashboard route
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

    # --- Fetch asset service summary ---
    today = date.today()

    # Count overdue services
    cursor.execute("""
        SELECT COUNT(*) AS overdue_count 
        FROM assets 
        WHERE next_service_date IS NOT NULL AND next_service_date <= %s
    """, (today,))
    overdue_count = cursor.fetchone()["overdue_count"]

    # Count upcoming services (next 7 days)
    cursor.execute("""
        SELECT COUNT(*) AS upcoming_count 
        FROM assets 
        WHERE next_service_date > %s AND next_service_date <= %s
    """, (today, today.replace(day=today.day+7)))  # next 7 days
    upcoming_count = cursor.fetchone()["upcoming_count"]

    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",
        full_name=full_name,
        overdue_count=overdue_count,
        upcoming_count=upcoming_count
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

        if days_diff < 0:
            priority = "High"
        elif days_diff <= 7:
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



# Assets route with search 
@app.route("/assets")
def assets():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    search_query = request.args.get("q")  # Get the search term

    if search_query:
        like_term = f"%{search_query}%"
        # Search all main columns
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
        """, (like_term, like_term, like_term, like_term, like_term, like_term, like_term, like_term, like_term))
    else:
        cursor.execute("SELECT * FROM assets")

    assets_list = cursor.fetchall()

    # Check for service due / overdue
    today = date.today()
    for asset in assets_list:
        asset["is_overdue"] = False
        asset["is_due_soon"] = False

        next_service = asset.get("next_service_date")
        if next_service:
            if isinstance(next_service, str):
                next_service = date.fromisoformat(next_service)
            if next_service <= today:
                asset["is_overdue"] = True
            elif today < next_service <= today + timedelta(days=7):
                asset["is_due_soon"] = True

    cursor.close()
    db.close()
    return render_template("assets.html", assets=assets_list)




# Add Asset
@app.route("/add-asset", methods=["POST"])
def add_asset():
    if "user_id" not in session:
        return redirect(url_for("login"))

    asset_type = request.form.get("asset_type")
    name = request.form.get("name")
    serial_number = request.form.get("serial_number")
    identifier = request.form.get("identifier")
    location = request.form.get("location")
    manufacturer = request.form.get("manufacturer")
    model = request.form.get("model")
    purchase_date = request.form.get("purchase_date")
    status = request.form.get("status")
    last_service_date = request.form.get("last_service_date") or None
    next_service_date = request.form.get("next_service_date") or None


    if not name or not asset_type:
        return redirect(url_for("assets"))

    db = get_db()
    cursor = db.cursor()

    # ------ Auto-generate asset_code ----------
    from datetime import datetime
    current_year = datetime.now().year

    # Get last asset_code for this year
    cursor.execute("""
        SELECT asset_code FROM assets 
        WHERE asset_code LIKE %s 
        ORDER BY asset_code DESC 
        LIMIT 1
    """, (f"{current_year}-%",))
    last = cursor.fetchone()

    if last and last[0]:
        # Extract the number part and increment
        last_number = int(last[0].split("-")[1])
        next_number = last_number + 1
    else:
        next_number = 1

    asset_code = f"{current_year}-{next_number:08d}"  # 2026-00000001

    # ---------- Insert new asset -----------
    cursor.execute("""
        INSERT INTO assets 
        (asset_code, asset_type, name, serial_number, identifier, location, manufacturer, model, purchase_date, status, last_service_date, next_service_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (asset_code, asset_type, name, serial_number, identifier, location, manufacturer, model, purchase_date, status, last_service_date, next_service_date))

    # ------- Log creation in asset_history ----------
    try:
        cursor.execute("""
            INSERT INTO asset_history (asset_id, changed_by, action)
            VALUES (%s, %s, 'Created')
        """, (cursor.lastrowid, session["full_name"]))
    except Exception as e:
        print("Error inserting into asset_history:", e)


    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("assets"))




# Delete Asset
@app.route("/delete-asset/<int:asset_id>", methods=["POST"])
def delete_asset(asset_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("assets"))

# Edit Asset
@app.route('/edit-asset/<int:asset_id>', methods=['POST'])
def edit_asset(asset_id):

    if session.get("role") not in ["admin", "supervisor"]:
        return "Unauthorized", 403

    type = request.form.get("asset_type")
    name = request.form.get("name")
    serial_number = request.form.get("serial_number")
    identifier = request.form.get("identifier")
    location = request.form.get("location")
    manufacturer = request.form.get("manufacturer")
    model = request.form.get("model")
    status = request.form.get("status")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE assets
        SET asset_type=%s,
            name=%s,
            serial_number=%s,   
            identifier=%s,
            location=%s,
            manufacturer=%s,
            model=%s,
            status=%s
        WHERE id=%s
    """, 
    (type, name, serial_number, identifier,
          location, manufacturer, model,
          status, asset_id))

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("assets"))

# Update Asset (Admin/Supervisor only)
@app.route("/update-asset/<int:asset_id>", methods=["POST"])
def update_asset(asset_id):
    # Only admin or supervisor can edit
    if "role" not in session or session["role"] not in ["admin", "supervisor"]:
        return "Unauthorized", 403

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # --- Fetch current asset values ---
    cursor.execute("SELECT * FROM assets WHERE id = %s", (asset_id,))
    old_asset = cursor.fetchone()

    # --- Get new values from form ---
    asset_type = request.form.get("asset_type")
    name = request.form.get("name")
    serial_number = request.form.get("serial_number")
    identifier = request.form.get("identifier")
    location = request.form.get("location")
    manufacturer = request.form.get("manufacturer")
    model = request.form.get("model")
    purchase_date = request.form.get("purchase_date")
    status = request.form.get("status")

    # --- Update asset ---
    cursor.execute("""
        UPDATE assets
        SET asset_type=%s, name=%s, serial_number=%s, identifier=%s,
            location=%s, manufacturer=%s, model=%s, purchase_date=%s, status=%s
        WHERE id=%s
    """, (asset_type, name, serial_number, identifier, location,
          manufacturer, model, purchase_date, status, asset_id))

    # --- Log changes in asset_history ---
    
    fields = ['asset_type', 'name', 'serial_number', 'identifier', 'location', 'manufacturer', 'model', 'purchase_date', 'status']

    for field in fields:
        old_value = old_asset[field]
        new_value = request.form.get(field)
        if old_value != new_value:
            cursor.execute("""
                INSERT INTO asset_history (asset_id, changed_by, action, field_changed, old_value, new_value)
                VALUES (%s, %s, 'Edited', %s, %s, %s)
            """, (asset_id, session["full_name"], field, old_value, new_value))


    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("assets"))


# View Asset History (JSON for frontend)
@app.route("/asset-history/<int:asset_id>")
def asset_history(asset_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM asset_history WHERE asset_id = %s ORDER BY change_date DESC", (asset_id,))
    history = cursor.fetchall()
    cursor.close()
    db.close()
    return {"history": history}  # JSON for frontend






# Service Asset (update service dates)
@app.route("/service-asset/<int:asset_id>", methods=["POST"])
def service_asset(asset_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch current asset
    cursor.execute("SELECT * FROM assets WHERE id = %s", (asset_id,))
    asset = cursor.fetchone()

    if not asset:
        cursor.close()
        db.close()
        return "Asset not found", 404

    # Get number of days for next service from form
    try:
        interval_days = int(request.form.get("interval_days", 30))
    except ValueError:
        interval_days = 30  # default 30 days

    today = datetime.today().date()
    next_service = today + timedelta(days=interval_days)

    # Update DB
    cursor.execute("""
        UPDATE assets
        SET last_service_date = %s, next_service_date = %s
        WHERE id = %s
    """, (today, next_service, asset_id))

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















# Logout route
@app.route("/logout")
def logout():
    session.clear() # clear the session.
    return redirect(url_for("login"))















if __name__ == "__main__":
    app.run(debug=True) 
