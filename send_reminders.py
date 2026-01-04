import os
import smtplib
from email.message import EmailMessage
from cs50 import SQL
from datetime import datetime, timedelta

# Database Setup
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
    msg.set_content("Please enable HTML to view this reminder.")
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
            print(f"✅ EMAIL SENT to {to_email}")
    except Exception as e:
        print(f"❌ EMAIL ERROR: {e}")

def check_and_send():
    # checkpoint 1
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"--- STEP 1: Checking for assignments due {tomorrow} ---")
    
    # checkpoint 2: Simplified query (No JOINS for now to ensure results)
    reminders = db.execute("SELECT * FROM assignments WHERE due_date = ? AND status != 'Completed'", tomorrow)
    print(f"--- STEP 2: Found {len(reminders)} assignments in DB ---")

    for r in reminders:
        # checkpoint 3: Get user email
        user = db.execute("SELECT username, email FROM users WHERE id = ?", r['user_id'])
        if not user:
            print(f"--- STEP 3: Skipping {r['title']} (User not found) ---")
            continue
        
        target_email = user[0]['email'] if user[0]['email'] else user[0]['username']
        print(f"--- STEP 4: Attempting to email {target_email} for '{r['title']}' ---")

        html_content = f"<html><body><h2>Reminder: {r['title']}</h2><p>Due tomorrow!</p></body></html>"
        send_email(target_email, f"Reminder: {r['title']}", html_content)

if __name__ == "__main__":
    check_and_send()
