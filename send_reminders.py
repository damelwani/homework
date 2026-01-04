import os
import smtplib
from email.message import EmailMessage
from cs50 import SQL
from datetime import datetime, timedelta

# --- Configuration ---
# Uses environment variable for security, with your Neon URL as a backup
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    database_url = "postgresql://neondb_owner:npg_wEKqG5s9jnlY@ep-wandering-tree-adanengq-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

db = SQL(database_url)
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
APP_URL = "https://homework-damelwanis-projects.vercel.app"

def send_email(to_email, subject, html_body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f"Homework Tracker <{EMAIL_ADDRESS}>"
    msg['To'] = to_email
    
    msg.set_content("Please enable HTML to view this assignment reminder.")
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
            print(f"✅ EMAIL SENT to {to_email}")
    except Exception as e:
        print(f"❌ SMTP ERROR: {e}")

def check_and_send():
    # 1. Get tomorrow's date
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"--- LOG: Checking assignments due {tomorrow} ---")
    
    # 2. Find assignments due tomorrow that aren't completed
    reminders = db.execute("SELECT * FROM assignments WHERE due_date = ? AND status != 'Completed'", tomorrow)
    
    if len(reminders) == 0:
        print(f"--- LOG: No assignments due on {tomorrow}. Finishing task. ---")
        return

    print(f"--- LOG: Found {len(reminders)} assignments. Starting email loop. ---")

    for r in reminders:
        # 3. Get user info
        user_rows =
