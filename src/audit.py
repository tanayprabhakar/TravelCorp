import sqlite3
import os
import json
from datetime import datetime

class AuditLogger:
    def __init__(self, db_path='data/audit.db'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    invoice_no TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    action_taken TEXT NOT NULL,
                    tone_used TEXT,
                    email_subject TEXT,
                    email_body TEXT
                )
            ''')
            conn.commit()

    def log_action(self, invoice_no, client_name, action_taken, tone_used=None, email_subject=None, email_body=None):
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO email_audit (timestamp, invoice_no, client_name, action_taken, tone_used, email_subject, email_body)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, invoice_no, client_name, action_taken, tone_used, email_subject, email_body))
            conn.commit()

    def get_logs(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM email_audit ORDER BY timestamp DESC')
            return [dict(row) for row in cursor.fetchall()]
