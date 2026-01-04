import os
import smtplib
from email.message import EmailMessage
from cs50 import SQL
from datetime import datetime, timedelta

# 1. Setup Database 
# We use the same 'FORCE-FIX' logic here to ensure it never fails
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    database_url = "postgresql://neondb_owner:npg_wEKqG5s9jnlY@ep-wandering-tree-adanengq-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

db = SQL(database_url)

# 2. Email Credentials (These MUST be set in GitHub Secrets later)
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

def send_email(to_email, subject, body):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Error: Email credentials not found in environment variables.")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
            print(f"Email sent successfully to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def check_and_send():
    # Calculate tomorrow's date string
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Checking for assignments due on: {tomorrow}")
    
    # This query finds the student and the parent linked to the student
    reminders = db.execute("""
        SELECT a.title, a.subject, u_child.email AS student_email, u_parent.email AS parent_email
        FROM assignments a
        JOIN users u_child ON a.user_id = u_child.id
        LEFT JOIN relationships r ON u_child.id = r.child_id
        LEFT JOIN users u_parent ON r.parent_id = u_parent.id
        WHERE a.due_date = ? AND a.status != 'Completed'
    """, tomorrow)

    if not reminders:
        print("No reminders to send for tomorrow.")
        return

    for r in reminders:
        # Email for the student
        student_sub = f"🔔 Due Tomorrow: {r['title']}"
        student_body = f"Hi! Just a reminder that your {r['subject']} assignment '{r['title']}' is due tomorrow ({tomorrow})."
        
        # Send to student
        send_email(r['student_email'], student_sub, student_body)
        
        # Send to parent if linked
        if r['parent_email']:
            parent_sub = f"Child Reminder: {r['title']} is due tomorrow"
            parent_body = f"Hello, this is an automated update. Your child has an assignment '{r['title']}' for {r['subject']} due tomorrow."
            send_email(r['parent_email'], parent_sub, parent_body)

if __name__ == "__main__":
    check_and_send()
