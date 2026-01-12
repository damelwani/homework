import os
from cs50 import SQL
import smtplib
from email.message import EmailMessage

# Connection to your Neon Database
db = SQL("postgresql://neondb_owner:npg_wEKqG5s9jnlY@ep-wandering-tree-adanengq-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require")

def send_reminders():
    # Only fetch assignments for users who have notifications turned ON
    tasks = db.execute("""
        SELECT assignments.*, users.email, users.username, users.id as u_id
        FROM assignments 
        JOIN users ON assignments.user_id = users.id 
        WHERE users.notifications_enabled = TRUE 
        AND assignments.status != 'Completed'
        AND assignments.due_date = CURRENT_DATE + INTERVAL '1 day'
    """)

    for task in tasks:
        msg = EmailMessage()
        msg['Subject'] = f"Reminder: {task['title']} is due tomorrow!"
        msg['From'] = os.environ.get("EMAIL_ADDRESS")
        msg['To'] = task['email']
        
        # Adding an unsubscribe link at the bottom for convenience
        content = f"""
        Hi {task['username']},

        This is a reminder that your assignment '{task['title']}' for {task['subject']} is due tomorrow.

        View your calendar: https://trackhw.com/

        ---
        Stop receiving these? https://trackhw.com/unsubscribe/{task['u_id']}
        """
        msg.set_content(content)

        try:
            with smtplib.SMTP_SSL('smtp.porkbun.com', 465) as smtp:
                smtp.login(os.environ.get("EMAIL_ADDRESS"), os.environ.get("EMAIL_PASSWORD"))
                smtp.send_message(msg)
            print(f"Sent reminder to {task['email']}")
        except Exception as e:
            print(f"Error sending to {task['email']}: {e}")

if __name__ == "__main__":
    send_reminders()
