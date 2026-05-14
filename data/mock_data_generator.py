import pandas as pd
from datetime import datetime, timedelta
import os

def generate_mock_data():
    today = datetime.now()
    
    # Define scenarios
    scenarios = [
        # Not overdue (negative days overdue)
        {"client": "TechCorp Solutions", "contact_email": "billing@techcorp.example.com", "amount": 15000.0, "due_date": (today + timedelta(days=5)).strftime('%Y-%m-%d'), "invoice_no": "INV-2024-001", "follow_up_count": 0},
        # Stage 1: 1-7 days overdue
        {"client": "Rajesh Kapoor", "contact_email": "rajesh@example.com", "amount": 45000.0, "due_date": (today - timedelta(days=4)).strftime('%Y-%m-%d'), "invoice_no": "INV-2024-002", "follow_up_count": 0},
        # Stage 2: 8-14 days overdue
        {"client": "Global Logistics", "contact_email": "accounts@globallogistics.example.com", "amount": 8200.0, "due_date": (today - timedelta(days=10)).strftime('%Y-%m-%d'), "invoice_no": "INV-2024-003", "follow_up_count": 1},
        # Stage 3: 15-21 days overdue
        {"client": "Sunrise Retail", "contact_email": "finance@sunriseretail.example.com", "amount": 12500.0, "due_date": (today - timedelta(days=18)).strftime('%Y-%m-%d'), "invoice_no": "INV-2024-004", "follow_up_count": 2},
        # Stage 4: 22-30 days overdue
        {"client": "Apex Manufacturing", "contact_email": "payables@apex.example.com", "amount": 67000.0, "due_date": (today - timedelta(days=28)).strftime('%Y-%m-%d'), "invoice_no": "INV-2024-005", "follow_up_count": 3},
        # Escalation: 30+ days overdue
        {"client": "Defunct Co.", "contact_email": "admin@defunct.example.com", "amount": 5400.0, "due_date": (today - timedelta(days=45)).strftime('%Y-%m-%d'), "invoice_no": "INV-2024-006", "follow_up_count": 4},
    ]
    
    df = pd.DataFrame(scenarios)
    
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(__file__), exist_ok=True)
    
    # Save to CSV
    output_path = os.path.join(os.path.dirname(__file__), 'invoices.csv')
    df.to_csv(output_path, index=False)
    print(f"Mock data generated successfully at {output_path}")

if __name__ == "__main__":
    generate_mock_data()
