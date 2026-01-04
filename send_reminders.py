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

def send_email(to_email, subject, html_body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email

    # This allows the email to have a "fallback" for old phones, 
    # but show the pretty HTML on Gmail/Outlook
    msg.set_content("Please enable HTML to view this reminder.") 
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Error: {e}")

def check_and_send():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    reminders = db.execute("""
        SELECT a.title, a.subject, u_child.username AS student_name, u_child.email AS student_email 
        FROM assignments a
        JOIN users u_child ON a.user_id = u_child.id
        WHERE a.due_date = ? AND a.status != 'Completed'
    """, tomorrow)

    for r in reminders:
        # The HTML "Template"
        html_content = f"""
        <html>
            <body style="font-family: sans-serif; background-color: #f4f7f6; padding: 20px;">
                <div style="max-width: 500px; margin: auto; background: white; padding: 30px; border-radius: 15px; border: 1px solid #e0e0e0; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                    <h2 style="color: #4f46e5; margin-top: 0;">🔔 Due Tomorrow</h2>
                    <p style="color: #666; font-size: 16px;">Hi {r['student_name']}, you have an assignment coming up:</p>
                    
                    <div style="background: #f9fafb; border-left: 4px solid #4f46e5; padding: 15px; margin: 20px 0;">
                        <strong style="display: block; font-size: 18px; color: #111;">{r['title']}</strong>
                        <span style="color: #666;">Subject: {r['subject']}</span>
                    </div>

                    <a href="https://your-app-link.vercel.app" 
                       style="display: inline-block; background: #4f46e5; color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                       View Dashboard
                    </a>
                    
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
                    <p style="font-size: 12px; color: #999; text-align: center;">Sent by Homework Tracker</p>
                </div>
            </body>
        </html>
        """
        
        send_email(r['student_email'], f"🔔 Reminder: {r['title']} is due!", html_content)
