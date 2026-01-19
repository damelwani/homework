import os
from cs50 import SQL
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

# Connection to your Neon Database
db = SQL("postgresql://neondb_owner:npg_wEKqG5s9jnlY@ep-wandering-tree-adanengq-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require")

def send_reminders():
    # Logic: 
    # 1. Homework due tomorrow (1 day interval)
    # 2. Tests/Exams due in 3 days (3 day interval)
    tasks = db.execute("""
        SELECT assignments.*, users.email, users.username, users.id as u_id
        FROM assignments 
        JOIN users ON assignments.user_id = users.id 
        WHERE users.notifications_enabled = TRUE 
        AND assignments.status != 'Completed'
        AND (
            (assignments.type ILIKE 'Exam' AND assignments.due_date = CURRENT_DATE + INTERVAL '3 days')
            OR 
            (assignments.type ILIKE 'Homework' AND assignments.due_date = CURRENT_DATE + INTERVAL '1 day')
        )
    """)

    for task in tasks:
        msg = EmailMessage()
        sender_name = "TrackHW Reminders"
        sender_email = os.environ.get("EMAIL_ADDRESS")
        # Dynamic Subject line based on type
        due_text = "in 3 days" if task['type'].lower() == "exam" else "tomorrow"
        msg['Subject'] = f"Reminder: {task['title']} is due {due_text}!"
        msg['From'] = formataddr((sender_name, sender_email))        
        msg['To'] = task['email']
        
        # HTML Styling
        html_content = f"""
        <html>
            <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; border: 1px solid #e0e0e0;">
                    <div style="background-color: #4a90e2; padding: 20px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 24px;">Upcoming Deadline</h1>
                    </div>
                    <div style="padding: 30px;">
                        <p style="font-size: 16px; color: #333;">Hi {task['username']},</p>
                        <p style="font-size: 16px; color: #555;">You have an upcoming <strong>{task['type']}</strong> due {due_text}:</p>
                        
                        <div style="background-color: #f9f9f9; border-left: 4px solid #4a90e2; padding: 15px; margin: 20px 0;">
                            <h2 style="margin: 0 0 10px 0; color: #333; font-size: 18px;">{task['title']}</h2>
                            <p style="margin: 5px 0; color: #666;"><strong>Subject:</strong> {task['subject']}</p>
                            <p style="margin: 5px 0; color: #666;"><strong>Due Date:</strong> {task['due_date']}</p>
                        </div>

                        <div style="text-align: center; margin-top: 30px;">
                            <a href="https://trackhw.com/" style="background-color: #4a90e2; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">View on TrackHW</a>
                        </div>
                    </div>
                    <div style="background-color: #f4f7f6; padding: 15px; text-align: center; font-size: 12px; color: #999;">
                        <p>TrackHW - Your Student Productivity Dashboard</p>
                        <p><a href="https://trackhw.com/unsubscribe/{task['u_id']}" style="color: #999;">Unsubscribe from these alerts</a></p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        # Add both plain text and HTML versions
        msg.set_content(f"Hi {task['username']}, your {task['type']} '{task['title']}' is due {due_text}. View more at https://trackhw.com/")
        msg.add_alternative(html_content, subtype='html')

        try:
            with smtplib.SMTP_SSL('smtp.porkbun.com', 465) as smtp:
                smtp.login(os.environ.get("EMAIL_ADDRESS"), os.environ.get("EMAIL_PASSWORD"))
                smtp.send_message(msg)
            print(f"Sent {task['type']} reminder to {task['email']}")
        except Exception as e:
            print(f"Error sending to {task['email']}: {e}")

if __name__ == "__main__":
    send_reminders()
