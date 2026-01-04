import os
import smtplib
from email.message import EmailMessage
from cs50 import SQL
from datetime import datetime, timedelta

# --- Database & Config Setup ---
# It will try to use the environment variable, but has your specific URL as a fallback
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    database_url = "postgresql://neondb_owner:npg_wEKqG5s9jnlY@ep-wandering-tree-adanengq-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

db = SQL(database_url)
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

def send_email(to_email, subject, html_body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    
    # Text fallback for older email clients
    msg.set_content("Please enable HTML to view this assignment reminder.")
    # Styled HTML content
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
            print(f"✅ EMAIL SENT to {to_email}")
    except Exception as e:
        print(f"❌ SMTP ERROR: {e}")

def check_and_send():
    # 1. Determine "Tomorrow"
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"--- LOG: Checking assignments due {tomorrow} ---")
    
    # 2. Query assignments due tomorrow that aren't finished
    reminders = db.execute("SELECT * FROM assignments WHERE due_date = ? AND status != 'Completed'", tomorrow)
    print(f"--- LOG: Found {len(reminders)} assignments to process ---")

    for r in reminders:
        # 3. Get the user's details
        user_rows = db.execute("SELECT username, email FROM users WHERE id = ?", r['user_id'])
        if not user_rows:
            print(f"--- LOG: Skipping '{r['title']}' (User ID {r['user_id']} not found) ---")
            continue
        
        user
