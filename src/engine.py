import pandas as pd
from datetime import datetime
from src.agent import EmailAgent
from src.audit import AuditLogger
import os
import smtplib
from email.message import EmailMessage

class EscalationEngine:
    def __init__(self, data_path='data/invoices.csv'):
        self.data_path = data_path
        self.audit_logger = AuditLogger()
        self.agent = None

    def _init_agent(self):
        if not self.agent:
            self.agent = EmailAgent()

    def calculate_days_overdue(self, due_date_str):
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        today = datetime.now()
        delta = today - due_date
        return delta.days

    def get_stage(self, days_overdue):
        if days_overdue < 1:
            return 0, None, None
        elif 1 <= days_overdue <= 7:
            return 1, "Warm & Friendly", "Gentle reminder, assume oversight. CTA: Pay now link / bank details"
        elif 8 <= days_overdue <= 14:
            return 2, "Polite but Firm", "Payment still pending; request confirmation. CTA: Confirm payment date"
        elif 15 <= days_overdue <= 21:
            return 3, "Formal & Serious", "Escalating concern; mention impact. CTA: Respond within 48 hrs"
        elif 22 <= days_overdue <= 30:
            return 4, "Stern & Urgent", "Final reminder before escalation. CTA: Pay immediately or call us"
        else:
            return 5, "Escalation Flag", "Flag for Legal. Human review required; no auto email. CTA: Assign to finance manager"

    def send_email(self, to_email, subject, body):
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = os.getenv("SMTP_PORT")
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        sender_email = os.getenv("SENDER_EMAIL")

        if not all([smtp_server, smtp_port, smtp_username, smtp_password, sender_email]):
            print(f"\n--- DRY RUN: SENDING EMAIL (SMTP not configured) ---")
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print(f"Body:\n{body}")
            print(f"----------------------------------------------------\n")
            return True, "dry-run"

        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = to_email

        try:
            with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            return True, "sent"
        except Exception as e:
            print(f"SMTP Error: {e}")
            return False, str(e)

    def process_invoices(self):
        if not os.path.exists(self.data_path):
            print(f"Data file {self.data_path} not found.")
            return

        df = pd.read_csv(self.data_path)
        
        for index, row in df.iterrows():
            days_overdue = self.calculate_days_overdue(row['due_date'])
            stage, tone_name, tone_desc = self.get_stage(days_overdue)

            if stage == 0:
                print(f"Invoice {row['invoice_no']} for {row['client']} is not yet overdue.")
                continue

            if stage == 5:
                print(f"[ESCALATION] Invoice {row['invoice_no']} for {row['client']} is {days_overdue} days overdue. Flagging for manual review.")
                self.audit_logger.log_action(
                    invoice_no=row['invoice_no'],
                    client_name=row['client'],
                    action_taken="Flagged for manual review (30+ days overdue)",
                    tone_used="Escalation Flag"
                )
                continue

            # Generate email
            print(f"Processing Invoice {row['invoice_no']} for {row['client']} (Stage {stage}, {days_overdue} days overdue)")
            try:
                self._init_agent()
            except ValueError as e:
                print(f"Agent Initialization Error: {e}")
                return

            email_output = self.agent.generate_email(
                client_name=row['client'],
                invoice_no=row['invoice_no'],
                amount=f"■{row['amount']}",
                due_date=row['due_date'],
                days_overdue=days_overdue,
                tone_instruction=f"Tone: {tone_name}. Message: {tone_desc}"
            )

            if email_output:
                success, status = self.send_email(row['contact_email'], email_output.subject, email_output.body)
                
                if success:
                    # Log action
                    action_str = f"Sent Stage {stage} Email ({status})"
                    self.audit_logger.log_action(
                        invoice_no=row['invoice_no'],
                        client_name=row['client'],
                        action_taken=action_str,
                        tone_used=tone_name,
                        email_subject=email_output.subject,
                        email_body=email_output.body
                    )
                else:
                    print(f"Failed to send email for {row['invoice_no']}: {status}")
            else:
                print(f"Failed to generate email for {row['invoice_no']}")

if __name__ == "__main__":
    engine = EscalationEngine()
    engine.process_invoices()
