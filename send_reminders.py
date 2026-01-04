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
        user_rows = db.execute("SELECT username, email FROM users WHERE id = ?", r['user_id'])
        if not user_rows:
            continue
        
        user = user_rows[0]
        # Use email column if available, otherwise fallback to username
        target_email = user['email'] if user.get('email') else user['username']
        student_name = user['username']

        # 4. Styled HTML Template
        html_content = f"""
        <html>
            <body style="font-family: 'Inter', Helvetica, Arial, sans-serif; background-color: #f3f4f6; padding: 20px; margin: 0;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border: 1px solid #e5e7eb;">
                    <div style="background-color: #4f46e5; padding: 30px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 26px; font-weight: 700;">Upcoming Deadline</h1>
                    </div>
                    
                    <div style="padding: 40px;">
                        <p style="font-size: 16px; color: #374151; margin-bottom: 10px;">Hi <strong>{student_name}</strong>,</p>
                        <p style="font-size: 16px; color: #6b7280; line-height: 1.6;">You have an assignment coming up for <strong>{r['subject']}</strong>. Don't forget to turn it in!</p>
                        
                        <div style="margin: 30px 0; padding: 25px; border-radius: 10px; background-color: #f9fafb; border-left: 5px solid #4f46e5;">
                            <h3 style="margin: 0 0 8px 0; color: #111827; font-size: 18px; font-weight: 600;">{r['title']}</h3>
                            <p style="margin: 0; color: #4f46e5; font-size: 14px; font-weight: 500; text-transform: uppercase;">{r['subject']}</p>
                            <p style="margin: 10px 0 0 0; color: #ef4444; font-size: 14px; font-weight: 600;">Due Date: {tomorrow}</p>
                        </div>
                        
                        <div style="text-align: center; margin-top: 35px;">
                            <a href="{APP_URL}" 
                               style="background-color: #4f46e5; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; font-size: 16px;">
                               View My Dashboard
                            </a>
                        </div>
                    </div>
                    
                    <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                        <p style="font-size: 12px; color: #9ca3af; margin: 0;">
                            <strong>Homework Tracker</strong> by Trivia with Mom
                        </p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        send_email(target_email, f"🔔 Tomorrow: {r['title']} is due!", html_content)

if __name__ == "__main__":
    check_and_send()
