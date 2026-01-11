import os
import smtplib
from email.message import EmailMessage
from cs50 import SQL
from datetime import datetime, timedelta

# --- Configuration ---
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
    # Dates for checking
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    three_days_out = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    
    print(f"--- LOG: Running Daily Check (Tomorrow: {tomorrow}, 3-Days: {three_days_out}) ---")
    
    # 1. FIND HOMEWORK DUE TOMORROW
    homework_reminders = db.execute("""
        SELECT * FROM assignments 
        WHERE due_date = ? AND status != 'Completed' AND type = 'Homework'
    """, tomorrow)

    # 2. FIND EXAMS DUE IN 3 DAYS
    exam_reminders = db.execute("""
        SELECT * FROM assignments 
        WHERE due_date = ? AND type = 'Exam'
    """, three_days_out)

    # COMBINE LISTS
    all_reminders = []
    for h in homework_reminders:
        all_reminders.append({'data': h, 'days_left': 1, 'color': '#4f46e5'}) # Indigo for HW
    for e in exam_reminders:
        all_reminders.append({'data': e, 'days_left': 3, 'color': '#6f42c1'}) # Purple for Exams

    if not all_reminders:
        print("--- LOG: No reminders to send today. ---")
        return

    for item in all_reminders:
        r = item['data']
        days = item['days_left']
        theme_color = item['color']
        
        user_rows = db.execute("SELECT username, email FROM users WHERE id = ?", r['user_id'])
        if not user_rows:
            continue
        
        user = user_rows[0]
        target_email = user['email'] if user.get('email') else user['username']
        student_name = user['username']
        
        # Determine the heading
        heading = "Exam Reminder" if r['type'] == 'Exam' else "Assignment Deadline"

        html_content = f"""
        <html>
            <body style="font-family: 'Inter', Arial, sans-serif; background-color: #f3f4f6; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb;">
                    <div style="background-color: {theme_color}; padding: 30px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 24px;">{heading}</h1>
                    </div>
                    <div style="padding: 40px;">
                        <p>Hi <strong>{student_name}</strong>,</p>
                        <p>This is a reminder that you have a <strong>{r['type']}</strong> coming up in <strong>{days} day(s)</strong>.</p>
                        
                        <div style="margin: 30px 0; padding: 25px; border-radius: 10px; background-color: #f9fafb; border-left: 5px solid {theme_color};">
                            <h3 style="margin: 0;">{r['title']}</h3>
                            <p style="margin: 5px 0; color: {theme_color}; font-weight: bold;">{r['subject']}</p>
                            <p style="margin: 10px 0 0 0; color: #ef4444;">Due Date: {r['due_date']}</p>
                        </div>
                        
                        <div style="text-align: center; margin-top: 30px;">
                            <a href="{APP_URL}" style="background-color: {theme_color}; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">View Dashboard</a>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        subject_line = f"🔔 {r['type']} Reminder: {r['title']}"
        send_email(target_email, subject_line, html_content)

if __name__ == "__main__":
    check_and_send()
