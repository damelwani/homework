import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify, abort, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from helpers import login_required
from datetime import datetime, timedelta, date
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from google.auth.transport import requests
import smtplib
import pytz
from groq import Groq

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.config["SECRET_KEY"] = "longHomeworkSecretKey"

CLIENT_SECRETS_FILE = "credentials.json"

database_url = "postgresql://neondb_owner:npg_wEKqG5s9jnlY@ep-wandering-tree-adanengq-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Log to the Vercel console so we can see what is happening
print(f"Connecting to: {database_url}")

try:
    db = SQL(database_url)
except Exception as e:
    print(f"Database connection error: {e}")


GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    client = None
    print("WARNING: GROQ_API_KEY is not set!")

# Setup Email credentials (for the reminder script)
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

app.config["SESSION_PERMANENT"] = False

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "student":
            abort(403) # This triggers the error handler below
        return f(*args, **kwargs)
    return decorated_function

def parent_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "parent":
            abort(403) # This triggers the error handler below
        return f(*args, **kwargs)
    return decorated_function

@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403

def parse_time(time_val):
    if not time_val:
        return None
    # If it's already a time object (from some databases), just return it
    if isinstance(time_val, datetime):
        return time_val.time()
    if not isinstance(time_val, str):
        return time_val
        
    try:
        # Try HH:MM:SS format
        return datetime.strptime(time_val, '%H:%M:%S').time()
    except ValueError:
        try:
            # Try HH:MM format
            return datetime.strptime(time_val, '%H:%M').time()
        except ValueError:
            return time_val

# Route to serve the manifest at the root
@app.route('/site.webmanifest')
def manifest():
    return send_from_directory('static', 'site.webmanifest')

# Route to serve favicon.ico at the root (keeps browser logs clean)
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

#From AI
def format_date(value):
    if not value:
        return ""
    
    # If the value is already a date object (not a string)
    if isinstance(value, (date, datetime)):
        return value.strftime('%B %d, %Y')
        
    # If it's a string, convert it first
    try:
        date_obj = datetime.strptime(value, '%Y-%m-%d')
        return date_obj.strftime('%B %d, %Y')
    except (ValueError, TypeError):
        return value

app.jinja_env.filters['pretty_date'] = format_date

@app.route("/landing")
def landing():
    # If they are already logged in, send them away from the marketing page
    if session.get("user_id"):
        return redirect("/")
    
    return render_template("landing.html")

@app.route("/google_login")
def google_login():  # Removed @login_required
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri="https://www.trackhw.com/google_callback" # Use the verified URI
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session["google_state"] = state
    return redirect(authorization_url)

@app.route("/google_callback")
def google_callback(): # Removed @login_required
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=session.get("google_state"),
        redirect_uri="https://www.trackhw.com/google_callback"
    )
    
    # Finish the handshake
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    # Verify who this person is using the ID Token
    token_request = requests.Request()
    user_info = id_token.verify_oauth2_token(
        creds.id_token, 
        token_request, 
        flow.client_config['client_id']
    )

    google_id = user_info.get("sub")
    email = user_info.get("email")
    # Extract prefix (e.g., 'jsmith26' from 'jsmith26@school.edu')
    username_from_email = email.split('@')[0]

    # Check if user exists by Google ID
    user = db.execute("SELECT * FROM users WHERE google_id = ?", google_id)

    if not user:
        # Create new user if they don't exist
        db.execute("""
            INSERT INTO users (username, email, google_id, google_creds, notifications_enabled, role) 
            VALUES (?, ?, ?, ?, TRUE, 'student')
        """, username_from_email, email, google_id, creds.to_json())
        # Fetch the new user
        user = db.execute("SELECT * FROM users WHERE google_id = ?", google_id)
    else:
        # Update existing user's credentials
        db.execute("UPDATE users SET google_creds = ? WHERE google_id = ?", 
                   creds.to_json(), google_id)

    # LOG THE USER IN (The most important part)
    session.clear()
    session["user_id"] = user[0]["id"]

    session["role"] = user[0]["role"] 
    session["notifications"] = user[0]["notifications_enabled"]
    
    flash(f"Welcome back, {user[0]['username']}!")
    return redirect("/")
#Partially taken from Finance problem set
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email") # New field
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        role = request.form.get("role")

        if not username or not email or not password or not role:
            flash("Check all fields")
            return render_template("register.html")

        if password != confirmation:
            flash("Passwords do not match")
            return render_template("register.html")

        hash = generate_password_hash(password)

        try:
            # Add email to the INSERT statement
            db.execute(
                "INSERT INTO users (username, email, hash, role) VALUES (?, ?, ?, ?)",
                username, email, hash, role
            )
            return redirect("/login")
        except Exception as e:
            flash("Username already exists or error occurred")
            return render_template("register.html")

    return render_template("register.html")


@app.route("/schedule", methods=["GET", "POST"])
@login_required
def schedule():
    if request.method == "POST":
        # Only students can add classes
        if session.get("role") != "student":
            return redirect("/schedule")
            
        subject = request.form.get("subject")
        period = request.form.get("period")
        cycle_day = request.form.get("cycle_day")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        room_number = request.form.get("room_number")

        db.execute("""
            INSERT INTO schedule (user_id, subject_name, period, cycle_day, start_time, end_time, room_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, session["user_id"], subject, period, cycle_day, start_time, end_time, room_number)
        return redirect("/schedule")

    # --- GET REQUEST ---
    user_role = session.get("role")

    if user_role == "parent":
        # Indent this whole block one more level
        students = db.execute("""
            SELECT id, username FROM users 
            WHERE id IN (SELECT child_id FROM relationships WHERE parent_id = ?)
        """, session["user_id"])

        grouped_classes = {}
        for s in students:
            rows = db.execute("SELECT * FROM schedule WHERE user_id = ? ORDER BY cycle_day, period", s["id"])
            for r in rows:
                r["start_time"] = parse_time(r["start_time"])
                r["end_time"] = parse_time(r["end_time"])
            grouped_classes[s["username"]] = rows
        
        # ADD THIS RETURN: Without this, parents get a blank screen or error
        return render_template("schedule.html", grouped_classes=grouped_classes)

    else:
        # Student View logic
        rows = db.execute("SELECT * FROM schedule WHERE user_id = ? ORDER BY cycle_day, period", session["user_id"])
        for r in rows:
            r["start_time"] = parse_time(r["start_time"])
            r["end_time"] = parse_time(r["end_time"])
            
        return render_template("schedule.html", schedule=rows)

@app.route("/edit_schedule/<int:id>", methods=["POST"])
@login_required
def edit_schedule(id):
    # Security: Ensure user owns the record
    subject = request.form.get("subject")
    room = request.form.get("room_number")
    start = request.form.get("start_time")
    end = request.form.get("end_time")
    
    db.execute("""
        UPDATE schedule 
        SET subject_name = ?, room_number = ?, start_time = ?, end_time = ? 
        WHERE id = ? AND user_id = ?
    """, subject, room, start, end, id, session["user_id"])
    return redirect("/schedule")

@app.route("/delete_schedule/<int:id>", methods=["POST"])
def delete_schedule(id):
    db.execute("DELETE FROM schedule WHERE id = ? AND user_id = ?", id, session["user_id"])
    return redirect("/schedule")

@app.route("/clear_schedule", methods=["POST"])
def clear_schedule():
    db.execute("DELETE FROM schedule WHERE user_id = ?", session["user_id"])
    return redirect("/schedule")

@app.route("/add", methods=["GET", "POST"])
@login_required
@student_required
def add_assignment():
    print(f"DEBUG: Current Session User ID is {session.get('user_id')}")
    print(f"DEBUG: Request Method is {request.method}")
    if not session.get("user_id"):
        return redirect("/login")

    if request.method == "POST":
        title = request.form.get("title")
        subject = request.form.get("subject")
        due_date = request.form.get("due_date")
        assignment_type = request.form.get("type")
        
        db.execute("INSERT INTO assignments (user_id, title, subject, due_date, type) VALUES (?, ?, ?, ?, ?)",
                   session["user_id"], title, subject, due_date, assignment_type)
        return redirect("/")

    # Fetch unique subjects for the dropdown
    subjects = db.execute("SELECT DISTINCT subject_name FROM schedule WHERE user_id = ? ORDER BY subject_name", 
                          session["user_id"])
    return render_template("add.html", subjects=subjects)

@app.route("/")
@login_required
def index():

    if session.get("role") == "parent":
        return redirect("/parent")
        
    user_data = db.execute("SELECT google_creds FROM users WHERE id = ?", session["user_id"])
    google_connected = True if user_data[0]["google_creds"] else False
    # 1. Fetch the username from the database
    user_row = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
    
    # Check if the user exists, otherwise default to "User"
    if not user_row:
        username = "User"
    else:
        username = user_row[0]["username"]
    current_time = (datetime.utcnow() - timedelta(hours=5)).time()
    
    
    # 2. Get the sorting preference from the URL (?sort=...)
    sort_by = request.args.get("sort", "date")
    valid_sorts = {"date": "due_date", "subject": "subject", "title": "title"}
    secondary_sort = valid_sorts.get(sort_by, "due_date")

    # 3. Fetch assignments (Filtering out completed ones older than 5 days)
    rows = db.execute(f"""
        SELECT * FROM assignments 
        WHERE user_id = ? 
        AND (status != 'Completed' OR completed_at >= CURRENT_DATE - INTERVAL '5 days')
        ORDER BY status DESC, {secondary_sort} ASC
    """, session["user_id"])
    
    # 4. Process dates so they don't crash the template
    assignments = []
    for row in rows:
        task = dict(row)
        if isinstance(task["due_date"], str):
            task["due_date"] = datetime.strptime(task["due_date"], '%Y-%m-%d').date()
        assignments.append(task)

    # 5. Define timing variables for color-coding
    user_tz = pytz.timezone('US/Eastern') 
    today = datetime.now(user_tz).date()
    today_plus_2 = today + timedelta(days=2)
    overdue_count = sum(1 for t in assignments if t['due_date'] < today and t['status'] != 'Completed')
    today_count = sum(1 for t in assignments if t['due_date'] == today and t['status'] != 'Completed')
    completed_this_week = sum(1 for t in assignments if t['status'] == 'Completed')
    
    # 6. Return the template with ALL required variables
    return render_template(
        "index.html", 
        username=username, 
        assignments=assignments, 
        today=today, 
        today_plus_2=today_plus_2,
        current_sort=sort_by,
        google_connected=google_connected,
        overdue_count=overdue_count,
        today_count=today_count,
        completed_this_week=completed_this_week
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            flash("Username is required")
            return render_template("login.html")
        elif not request.form.get("password"):
            flash("Password is required")
            return render_template("login.html")

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            flash("Invalid username and/or password")
            return render_template("login.html")

        # ... after password verification ...
        session["user_id"] = rows[0]["id"]
        session["role"] = rows[0]["role"]
        session["notifications"] = rows[0]["notifications_enabled"]

        # Redirect based on role
        if session["role"] == "parent":
            return redirect("/parent")
        else:
            return redirect("/")

    else:
        return render_template("login.html")

@app.route("/delete", methods=["POST"])
@login_required
@student_required
def delete():
    id_to_delete = request.form.get("id")

    if id_to_delete:
        db.execute("DELETE FROM assignments WHERE id = ? AND user_id = ?",
                   id_to_delete, session["user_id"])
        flash("Assignment deleted!")

    return redirect("/")

@app.route("/update", methods=["POST"])
@login_required
@student_required
def update():
    user_row = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
    username = user_row[0]["username"] if user_row else "User"
    
    target_id = request.form.get("id")
    new_status = request.form.get("status")
    
    if new_status == "Completed":
        db.execute("UPDATE assignments SET status = ?, completed_at = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                   new_status, target_id)
    else:
        db.execute("UPDATE assignments SET status = ?, completed_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                   new_status, target_id)
    return redirect("/")

@app.route("/logout")
def logout():
    """Log user out"""

    session.clear()

    return redirect("/")
#Parent code partially from AI
@app.route("/parent")
@login_required
@parent_required
def parent_view():
    user_tz = pytz.timezone('US/Eastern') 
    today = datetime.now(user_tz).date()
    today_plus_2 = today + timedelta(days=2)
    # Get the sorting preference (default to 'child')
    sort_by = request.args.get("sort", "child")
    
    # Map choices to SQL columns
    # We include 'username' in most so work stays grouped by child
    valid_sorts = {
        "child": "users.username ASC, status DESC",
        "date": "due_date ASC, users.username ASC",
        "subject": "subject ASC, users.username ASC",
        "name": "title ASC, users.username ASC"
    }
    sql_order = valid_sorts.get(sort_by, "users.username ASC, status DESC")

    # Fetch linked students' assignments with the 5-day rule
    # This query says: "Find assignments for students who are LINKED to this parent"
    raw_tasks = db.execute("""
        SELECT assignments.*, users.username 
        FROM assignments 
        JOIN relationships ON assignments.user_id = relationships.child_id 
        JOIN users ON assignments.user_id = users.id
        WHERE relationships.parent_id = ?
        AND (status != 'Completed' OR completed_at >= CURRENT_DATE - INTERVAL '5 days')
        ORDER BY status DESC, users.username ASC
    """, session["user_id"])

    # Process dates for display
    family_work = []
    for row in raw_tasks:
        task = dict(row)
        if isinstance(task["due_date"], str):
            task["due_date"] = datetime.strptime(task["due_date"], '%Y-%m-%d').date()
        family_work.append(task)
        
    overdue_count = sum(1 for t in family_work if t['due_date'] < today and t['status'] != 'Completed')
    today_count = sum(1 for t in family_work if t['due_date'] == today and t['status'] != 'Completed')
    completed_count = sum(1 for t in family_work if t['status'] == 'Completed')

    return render_template("parent.html", 
        family_work=family_work, 
        overdue_count=overdue_count, 
        today_count=today_count, 
        completed_count=completed_count,
        today=today,
        today_plus_2=today_plus_2)
#Parent link code partially from AI
@app.route("/link", methods=["GET", "POST"])
@parent_required
@login_required
def link_child():
    if request.method == "POST":
        child_username = request.form.get("child_username")

        child = db.execute("SELECT id FROM users WHERE username = ?", child_username)

        if not child:
            flash("User not found.")
            return redirect("/link")

        child_id = child[0]["id"]

        existing = db.execute("SELECT * FROM relationships WHERE parent_id = ? AND child_id = ?",
                              session["user_id"], child_id)

        if existing:
            flash("You are already linked to this student.")
        elif child_id == session["user_id"]:
            flash("You cannot link to yourself!")
        else:
            db.execute("INSERT INTO relationships (parent_id, child_id) VALUES (?, ?)",
                       session["user_id"], child_id)
            flash(f"Successfully linked to {child_username}!")

        return redirect("/parent")

    return render_template("link.html")

@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
@student_required
def edit(task_id):
    if request.method == "POST":
        # Get data from the form
        title = request.form.get("title")
        subject = request.form.get("subject")
        due_date = request.form.get("due_date")

        # Update the database
        db.execute("""
            UPDATE assignments 
            SET title = ?, subject = ?, due_date = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ? AND user_id = ?
        """, title, subject, due_date, task_id, session["user_id"])

        flash("Assignment updated!")
        return redirect("/")

    # GET request: Fetch the existing data to pre-fill the form
    task = db.execute("SELECT * FROM assignments WHERE id = ? AND user_id = ?", 
                      task_id, session["user_id"])
    
    if not task:
        return "Assignment not found", 404
        
    return render_template("edit.html", task=task[0])

@app.route("/sync_classroom")
@login_required
@student_required
def sync_classroom():
    user_row = db.execute("SELECT google_creds FROM users WHERE id = ?", session["user_id"])
    if not user_row or not user_row[0]["google_creds"]:
        flash("Please connect Google first.")
        return redirect("/google_login")

    creds_data = json.loads(user_row[0]["google_creds"])
    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
    service = build('classroom', 'v1', credentials=creds)

    try:
        courses = service.courses().list().execute().get('courses', [])
        
        if not courses:
            flash("No Google Classroom courses found.")
            return redirect("/")

        count = 0
        for course in courses:
            if course.get('courseState') != 'ACTIVE':
                print(f"Skipping {course.get('name')} because it is {course.get('courseState')}")
                continue
            try:
                
            # ---------------------------

                # Fetch coursework for this specific course
                cw_data = service.courses().courseWork().list(courseId=course['id']).execute()
                coursework = cw_data.get('courseWork', [])

                # ... inside the sync_classroom loop after fetching coursework ...
                for item in coursework:
                    title = item.get('title')
                    due = item.get('dueDate')
                    item_id = item.get('id')
                    
                    # NEW: Check if the student has already turned this in
                    submissions = service.courses().courseWork().studentSubmissions().list(
                        courseId=course['id'], 
                        courseWorkId=item_id
                    ).execute().get('studentSubmissions', [])
                
                    # If there's a submission, check the state
                    is_completed = False
                    if submissions:
                        state = submissions[0].get('state')
                        # States like 'TURNED_IN' or 'RETURNED' mean the work is done
                        if state in ['TURNED_IN', 'RETURNED']:
                            is_completed = True
                
                    # Only add to our DB if it's NOT completed and has a due date
                    if not is_completed and due and title:
                        due_date = f"{due['year']}-{due['month']:02d}-{due['day']:02d}"
                        
                        existing = db.execute("SELECT id FROM assignments WHERE user_id = ? AND title = ?", 
                                              session["user_id"], title)
                        
                        if not existing:
                            db.execute("INSERT INTO assignments (user_id, title, due_date, subject) VALUES (?, ?, ?, ?)",
                                       session["user_id"], title, due_date, course['name'])
                            count += 1
            except Exception as course_error:
                print(f"Skipping course {course.get('name')} due to error: {course_error}")
                continue # This moves to the next course if one fails

        flash(f"Successfully synced! {count} assignments added.")
        
    except Exception as e:
        import traceback
        print(traceback.format_exc()) 
        flash(f"Sync failed: {e}")
        return redirect("/")

    return redirect("/")

from flask import jsonify

@app.route("/api/assignments")
@login_required
def api_assignments():
    user_id = session["user_id"]
    user_role = session.get("role")
    
    # 1. Fetch the data based on Role
    if user_role == "parent":
        # Get assignments for all students linked to this parent
        rows = db.execute("""
            SELECT title, due_date 
            FROM assignments 
            WHERE user_id IN (SELECT student_id FROM links WHERE parent_id = ?)
        """, user_id)
    else:
        # Get assignments for the logged-in student
        rows = db.execute("""
            SELECT title, due_date 
            FROM assignments 
            WHERE user_id = ?
        """, user_id)

    # 2. Format the data for FullCalendar
    # FullCalendar MUST have 'title' and 'start' as YYYY-MM-DD strings
    events = []
    for row in rows:
        # Convert the date object/string to a clean YYYY-MM-DD format
        date_val = row["due_date"]
        
        if hasattr(date_val, 'strftime'):
            # If it's a datetime object from the DB
            clean_date = date_val.strftime('%Y-%m-%d')
        else:
            # If it's a string, take only the first 10 characters (YYYY-MM-DD)
            clean_date = str(date_val)[:10]

        events.append({
            "title": row["title"],
            "start": clean_date,
            "allDay": True,
            "color": "#0d6efd" # Sets the blue color directly from the server
        })
        
    return jsonify(events)

@app.route("/calendar")
@login_required
def calendar_view():
    return render_template("calendar.html")

@app.route("/update_notifications", methods=["POST"])
@login_required
def update_notifications():
    data = request.get_json()
    enabled = data.get("enabled")
    
    db.execute("UPDATE users SET notifications_enabled = ? WHERE id = ?", 
               enabled, session["user_id"])
    
    session["notifications"] = enabled
    
    return jsonify({"success": True})

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.errorhandler(404)
def internal_error(error):
    return render_template('404.html'), 404

@app.route("/unsubscribe/<int:user_id>")
def unsubscribe(user_id):
    db.execute("UPDATE users SET notifications_enabled = FALSE WHERE id = ?", user_id)
    return render_template("message.html", message="You have been unsubscribed from email alerts.")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/tutor", methods=["GET", "POST"])
def tutor():
    # 1. Initialize chat history in the session if it doesn't exist
    if "chat_history" not in session:
        session["chat_history"] = [
            {"role": "system", "content": (
                "You are the TrackHW Tutor, a Socratic assistant. "
                "Your goal is to help students learn concepts. "
                "CRITICAL RULE: Never provide the direct answer or full solution. "
                "Instead, ask guiding questions, give small hints, and use analogies. "
                "Always encourage the student to think through the next step."
            )}
        ]

    if request.method == "POST":

        if client is None:
            print("ERROR: Groq client is None. Check your Environment Variables.")
            return jsonify({"reply": "System Error: The AI engine is not configured. Please check the GROQ_API_KEY."}), 500
        user_input = request.json.get("message")
        
        # 2. Add the user's new message to the history
        session["chat_history"].append({"role": "user", "content": user_input})
        
        try:
            # 3. Call Groq with the FULL history (so it remembers the conversation)
            completion = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=session["chat_history"],
                temperature=0.6,
            )
            
            ai_reply = completion.choices[0].message.content
            
            # 4. Add the AI's reply to the history and save the session
            session["chat_history"].append({"role": "assistant", "content": ai_reply})
            session.modified = True # Tells Flask the session data changed
            
            return jsonify({"reply": ai_reply})
            
        except Exception as e:
            print(f"Groq Error: {e}")
            return jsonify({"reply": "I'm having a bit of trouble thinking. Try again?"}), 500

    return render_template("tutor.html")

@app.route("/tutor/clear", methods=["POST"])
def clear_tutor():
    """Route to reset the conversation"""
    session.pop("chat_history", None)
    return jsonify({"status": "cleared"})
