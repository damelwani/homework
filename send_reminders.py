import os
import smtplib
from email.message import EmailMessage
from cs50 import SQL
from datetime import datetime, timedelta

# --- Configuration ---
# Your database URL from Neon
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    database_url = "postgresql://neondb_owner:npg_wEKqG5s9jnlY@ep-wandering-tree-adanengq-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

db = SQL(database_url)

# Environment variables for your Porkbun Email
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
APP_URL = "https://www.trackhw.com"

def send_email(to_email, subject, html_body):
    msg = EmailMessage()
    msg['Subject'] = subject
    # This makes the email look professional in the inbox
    msg['From'] = f"TrackHW Reminders <{EMAIL_ADDRESS}>"
    msg['To'] = to_email
    
    msg.set_content("Please enable HTML to view this assignment reminder.")
    msg.add_alternative(html_body, subtype='html')

    try:
        # Porkbun SMTP settings (Using Port 465 for SSL)
        with smtplib.SMTP_SSL('smtp.porkbun.com', 465, timeout=10) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
            print(f"✅ EMAIL SENT to {to_email}")
    except Exception as e:
        print(f"❌ SMTP ERROR: {e}")

def check_and_send():
    # 1. Define dates for checking
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    three_days_out = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    
    print(f"--- LOG: Checking Today's Reminders (T+1: {tomorrow}, T+3: {three_days_out}) ---")
    
    # 2. Get Homework due tomorrow that isn't completed
    homework_reminders = db.execute("""
        SELECT * FROM assignments 
        WHERE due_date = ? AND status != 'Completed' AND type = 'Homework'
    """, tomorrow)

    # 3. Get Exams due in 3 days
    exam_reminders = db.execute("""
        SELECT * FROM assignments 
        WHERE due_date = ? AND type = 'Exam'
    """, three_days_out)

    # 4. Combine into a single processing list with specific themes
    reminders_to_process = []
    
    for h in homework_reminders:
        reminders_to_process.append({
            'data': h, 
            'days_left': 1, 
            'color': '#4f46e5',  # Indigo for HW
            'label': 'Homework Deadline'
        })
        
    for e in exam_reminders:
        reminders_to_process.append({
            'data': e, 
            'days_left': 3, 
            'color': '#6f42c1',  # Purple for Exams
            'label': 'Exam Reminder'
        })

    if not reminders_to_process:
        print("--- LOG: No assignments or exams requiring reminders today. ---")
        return

    # 5. Send the emails
    for item in reminders_to_process:
        r = item['data']
        
        # Get user info for this specific assignment
        user_rows = db.execute("SELECT username, email FROM users WHERE id = ?", r['user_id'])
        if not user_rows:
            continue
        
        user = user_rows[0]
        target_email = user['email'] if user.get('email') else user['username']
        student_name = user['username']

        html_content = f"""
        <html>
            <body style="font-family: 'Inter', Helvetica, Arial, sans-serif; background-color: #f3f4f6; padding: 20px; margin: 0;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                    <div style="background-color: {item['color']}; padding: 30px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700;">{item['label']}</h1>
                    </div>
                    
                    <div style="padding: 40px;">
                        <p style="font-size: 16px; color: #374151;">Hi <strong>{student_name}</strong>,</p>
                        <p style="font-size: 16px; color: #6b7280; line-height: 1.6;">
                            This is a courtesy reminder that you have a <strong>{r['type']}</strong> coming up in <strong>{item['days_left']} day(s)</strong>.
                        </p>
                        
                        <div style="margin: 30px 0; padding: 25px; border-radius: 10px; background-color: #f9fafb; border-left: 5px solid {item['color']};">
                            <h3 style="margin: 0 0 5px 0; color: #111827; font-size: 18px;">{r['title']}</h3>
                            <p style="margin: 0; color: {item['color']}; font-weight: 600; text-transform: uppercase; font-size: 13px;">{r['subject']}</p>
                            <p style="margin: 10px 0 0 0; color: #ef4444; font-weight: 600;">Due Date: {r['due_date']}</p>
                        </div>
                        
                        <div style="text-align: center; margin-top: 35px;">
                            <a href="{APP_URL}" 
                               style="background-color: {item['color']}; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">
                               View My Dashboard
                            </a>
                        </div>
                    </div>
                    
                    <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                        <p style="font-size: 12px; color: #9ca3af; margin: 0;">
                            <strong>TrackHW</strong> - Stay on top of your studies.
                        </p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        subject_line = f"🔔 {r['type']} Reminder: {r['title']}"
        send_email(target_email, subject_line, html_content)

if __name__ == "__main__":
    check_and_send()
