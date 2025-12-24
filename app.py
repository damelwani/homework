import os

from cs50 import SQL
from flask import Flask, app, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from helpers import login_required
from datetime import datetime, timedelta, date

app = Flask(__name__)
app.config["SECRET_KEY"] = "longHomeworkSecretKey" 

app.config["SESSION_PERMANENT"] = False

database_url=os.environ.get("psql 'postgresql://neondb_owner:npg_wEKqG5s9jnlY@ep-wandering-tree-adanengq-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'")
db = SQL("postgresql://neondb_owner:npg_wEKqG5s9jnlY@ep-wandering-tree-adanengq-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

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

#Partially taken from Finance problem set
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        role = request.form.get("role")

        if not username or not password or password != confirmation or not role:
            flash("Check all fields and ensure passwords match")
            return render_template("register.html")

        hash = generate_password_hash(password)

        existing_user = db.execute("SELECT * FROM users WHERE username = ?", username)
        if existing_user:
            flash("Username already exists")
            return render_template("register.html")

        try:
            new_user_id = db.execute(
                "INSERT INTO users (username, hash, role) VALUES (?, ?, ?)",
                username, hash, role
            )
            session["user_id"] = new_user_id
            session["role"] = role
            return redirect("/")
        except Exception as e:
            print(f"Error: {e}")
            flash("An internal error occurred.")
            return render_template("register.html")

    return render_template("register.html")


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        name = request.form.get("name")
        if not name:
            flash("Name is required")
            return render_template("add.html")

        due_date = request.form.get("due_date")
        if not due_date:
            flash("Due date is required")
            return render_template("add.html")

        db.execute(
            "INSERT INTO assignments (user_id, title, due_date) VALUES (?, ?, ?)",
            session["user_id"], name, due_date
        )

        return redirect()

    else:
        return render_template("add.html")


@app.route("/")
@login_required
def index():
    # 1. Fetch the username
    user_row = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
    username = user_row[0]["username"] if user_row else "User"

    # 2. Fetch the assignments (your existing code)
    rows = db.execute("SELECT * FROM assignments WHERE user_id = ?", session["user_id"])
    
    assignments = []
    for row in rows:
        if isinstance(row["due_date"], str):
            row["due_date"] = datetime.strptime(row["due_date"], '%Y-%m-%d').date()
        assignments.append(row)

    today = date.today()
    today_plus_2 = today + timedelta(days=2)
    
    # 3. Pass 'username' into the template
    return render_template("index.html", 
                           username=username, 
                           assignments=assignments, 
                           today=today, 
                           today_plus_2=today_plus_2)
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

        session["user_id"] = rows[0]["id"]
        session["role"] = rows[0]["role"]

        return redirect("/")

    else:
        return render_template("login.html")

@app.route("/delete", methods=["POST"])
@login_required
def delete():
    id_to_delete = request.form.get("id")

    if id_to_delete:
        db.execute("DELETE FROM assignments WHERE id = ? AND user_id = ?",
                   id_to_delete, session["user_id"])
        flash("Assignment deleted!")

    return redirect("/")

@app.route("/update", methods=["POST"])
@login_required
def update():
    target_id = request.form.get("id")
    new_status = request.form.get("status")

    db.execute(
        "UPDATE assignments SET status = ? WHERE id = ? AND user_id = ?",
        new_status, target_id, session["user_id"]
    )

    flash("Status updated!")
    return redirect("/")

@app.route("/logout")
def logout():
    """Log user out"""

    session.clear()

    return redirect("/")
#Parent code partially from AI@app.route("/parent")
@login_required
def parent_view():
    # 1. Use 'links' table and 'student_id' column (matching your Neon setup)
    children = db.execute("""
        SELECT id, username FROM users
        WHERE id IN (SELECT student_id FROM links WHERE parent_id = ?)
    """, session["user_id"])

    family_work = db.execute("""
        SELECT assignments.*, users.username
        FROM assignments
        JOIN users ON assignments.user_id = users.id
        WHERE user_id IN (SELECT student_id FROM links WHERE parent_id = ?)
        ORDER BY users.username, due_date ASC
    """, session["user_id"])

    # 2. Convert database strings to Python date objects for the template comparison
    for task in family_work:
        if isinstance(task["due_date"], str):
            task["due_date"] = datetime.strptime(task["due_date"], '%Y-%m-%d').date()

    # 3. Use date objects (not strftime strings)
    today = date.today()
    two_days_out = today + timedelta(days=2)

    return render_template("parent.html",
                           family_work=family_work,
                           children=children,
                           today=today,
                           today_plus_2=two_days_out)
#Parent link code partially from AI
@app.route("/link", methods=["GET", "POST"])
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
