"""
Credit Follow-Up Server
=======================
Flask API that serves the credit follow-up dashboard
and exposes endpoints for invoice processing.

Start with:  python server.py
Then open:   http://localhost:5000
"""

from flask import Flask, jsonify, request, send_from_directory, abort
import pandas as pd
from datetime import datetime
import os
import sys
import subprocess

# ---- Ensure project root is on the path ----
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.engine import EscalationEngine
from src.audit import AuditLogger

# ---- Flask App ----
app = Flask(__name__, static_folder='frontend', static_url_path='')

DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'invoices.csv')
ENV_PATH = os.path.join(PROJECT_ROOT, '.env')

# ---- Shared instances ----
audit_logger = AuditLogger()
_engine_instance = None


def get_engine():
    """Lazily initialize the engine so the server can start without an API key."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = EscalationEngine()
    return _engine_instance


# =============================================
#  Static Frontend
# =============================================

@app.route('/')
def serve_index():
    return send_from_directory('frontend', 'index.html')


# =============================================
#  API — Configuration
# =============================================

@app.route('/api/config', methods=['GET'])
def get_config():
    """Check whether an API key is configured."""
    configured = False
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('OPENAI_API_KEY='):
                    value = line.split('=', 1)[1].strip()
                    if value and value != 'your_openai_api_key_here':
                        configured = True
    return jsonify({'configured': configured})


@app.route('/api/config', methods=['POST'])
def save_config():
    """Save the API key to .env file."""
    data = request.get_json()
    api_key = data.get('api_key', '').strip()
    if not api_key:
        return jsonify({'error': 'API key is required'}), 400

    # Write .env file
    lines = []
    key_found = False
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r') as f:
            for line in f:
                if line.strip().startswith('OPENAI_API_KEY='):
                    lines.append(f'OPENAI_API_KEY={api_key}\n')
                    key_found = True
                else:
                    lines.append(line)
    if not key_found:
        lines.append(f'OPENAI_API_KEY={api_key}\n')

    with open(ENV_PATH, 'w') as f:
        f.writelines(lines)

    # Reset engine so it picks up the new key
    global _engine_instance
    _engine_instance = None

    # Reload dotenv in the current process
    from dotenv import load_dotenv
    load_dotenv(override=True)

    return jsonify({'success': True})


# =============================================
#  API — Invoices
# =============================================

@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    """Read invoices.csv and return JSON with computed stage info."""
    if not os.path.exists(CSV_PATH):
        return jsonify({'invoices': []})

    df = pd.read_csv(CSV_PATH)
    engine = EscalationEngine()  # lightweight, no LLM init needed

    invoices = []
    for _, row in df.iterrows():
        days_overdue = engine.calculate_days_overdue(row['due_date'])
        stage, tone_name, tone_desc = engine.get_stage(days_overdue)
        invoices.append({
            'client': row['client'],
            'contact_email': row['contact_email'],
            'amount': float(row['amount']),
            'due_date': row['due_date'],
            'invoice_no': row['invoice_no'],
            'follow_up_count': int(row.get('follow_up_count', 0)),
            'days_overdue': days_overdue,
            'stage': stage,
            'tone_name': tone_name or '',
            'tone_desc': tone_desc or ''
        })

    return jsonify({'invoices': invoices})


# =============================================
#  API — Email Generation
# =============================================

@app.route('/api/generate', methods=['POST'])
def generate_single():
    """Generate an email for a single invoice by invoice_no."""
    data = request.get_json()
    invoice_no = data.get('invoice_no')
    if not invoice_no:
        return jsonify({'error': 'invoice_no is required'}), 400

    if not os.path.exists(CSV_PATH):
        return jsonify({'error': 'No invoice data found'}), 404

    df = pd.read_csv(CSV_PATH)
    row = df[df['invoice_no'] == invoice_no]
    if row.empty:
        return jsonify({'error': f'Invoice {invoice_no} not found'}), 404

    row = row.iloc[0]
    engine = get_engine()
    days_overdue = engine.calculate_days_overdue(row['due_date'])
    stage, tone_name, tone_desc = engine.get_stage(days_overdue)

    if stage == 0:
        return jsonify({'status': 'not_due', 'invoice_no': invoice_no})

    if stage == 5:
        audit_logger.log_action(
            invoice_no=row['invoice_no'],
            client_name=row['client'],
            action_taken='Flagged for manual review (30+ days overdue)',
            tone_used='Escalation Flag'
        )
        return jsonify({'status': 'escalated', 'invoice_no': invoice_no})

    # Initialize agent inside engine
    engine._init_agent()

    email_output = engine.agent.generate_email(
        client_name=row['client'],
        invoice_no=row['invoice_no'],
        amount=f"₹{row['amount']}",
        due_date=row['due_date'],
        days_overdue=days_overdue,
        tone_instruction=f"Tone: {tone_name}. Message: {tone_desc}"
    )

    if email_output:
        audit_logger.log_action(
            invoice_no=row['invoice_no'],
            client_name=row['client'],
            action_taken=f'Sent Stage {stage} Email',
            tone_used=tone_name,
            email_subject=email_output.subject,
            email_body=email_output.body
        )
        return jsonify({
            'status': 'sent',
            'invoice_no': invoice_no,
            'stage': stage,
            'tone': tone_name,
            'invoice': {
                'client': row['client'],
                'contact_email': row['contact_email'],
                'amount': float(row['amount']),
                'due_date': row['due_date'],
                'days_overdue': days_overdue
            },
            'email': {
                'subject': email_output.subject,
                'body': email_output.body
            }
        })
    else:
        return jsonify({'error': 'Failed to generate email'}), 500


@app.route('/api/generate-all', methods=['POST'])
def generate_all():
    """Process all invoices and return results."""
    if not os.path.exists(CSV_PATH):
        return jsonify({'error': 'No invoice data found'}), 404

    df = pd.read_csv(CSV_PATH)
    engine = get_engine()
    results = []

    for _, row in df.iterrows():
        days_overdue = engine.calculate_days_overdue(row['due_date'])
        stage, tone_name, tone_desc = engine.get_stage(days_overdue)

        if stage == 0:
            results.append({'invoice_no': row['invoice_no'], 'status': 'not_due'})
            continue

        if stage == 5:
            audit_logger.log_action(
                invoice_no=row['invoice_no'],
                client_name=row['client'],
                action_taken='Flagged for manual review (30+ days overdue)',
                tone_used='Escalation Flag'
            )
            results.append({'invoice_no': row['invoice_no'], 'status': 'escalated'})
            continue

        try:
            engine._init_agent()
            email_output = engine.agent.generate_email(
                client_name=row['client'],
                invoice_no=row['invoice_no'],
                amount=f"₹{row['amount']}",
                due_date=row['due_date'],
                days_overdue=days_overdue,
                tone_instruction=f"Tone: {tone_name}. Message: {tone_desc}"
            )

            if email_output:
                audit_logger.log_action(
                    invoice_no=row['invoice_no'],
                    client_name=row['client'],
                    action_taken=f'Sent Stage {stage} Email',
                    tone_used=tone_name,
                    email_subject=email_output.subject,
                    email_body=email_output.body
                )
                results.append({'invoice_no': row['invoice_no'], 'status': 'sent', 'stage': stage})
            else:
                results.append({'invoice_no': row['invoice_no'], 'status': 'error', 'detail': 'Generation failed'})
        except Exception as e:
            results.append({'invoice_no': row['invoice_no'], 'status': 'error', 'detail': str(e)})

    return jsonify({'results': results})


# =============================================
#  API — Audit Logs
# =============================================

@app.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    """Return all audit log entries."""
    logs = audit_logger.get_logs()
    return jsonify({'logs': logs})


# =============================================
#  API — Data Management
# =============================================

@app.route('/api/upload-csv', methods=['POST'])
def upload_csv():
    """Upload a new invoices CSV file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Only .csv files are accepted'}), 400

    # Validate the CSV has required columns
    try:
        df = pd.read_csv(file)
        required = {'client', 'contact_email', 'amount', 'due_date', 'invoice_no'}
        missing = required - set(df.columns)
        if missing:
            return jsonify({'error': f'CSV is missing columns: {", ".join(missing)}'}), 400

        # Save
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(CSV_PATH, index=False)
        return jsonify({'success': True, 'rows': len(df)})

    except Exception as e:
        return jsonify({'error': f'Invalid CSV: {str(e)}'}), 400


@app.route('/api/regenerate-data', methods=['POST'])
def regenerate_data():
    """Run the mock data generator to create fresh sample data."""
    generator_path = os.path.join(DATA_DIR, 'mock_data_generator.py')
    if not os.path.exists(generator_path):
        return jsonify({'error': 'Mock data generator not found'}), 404

    try:
        subprocess.run(
            [sys.executable, generator_path],
            check=True,
            capture_output=True,
            text=True
        )
        return jsonify({'success': True})
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'Generator failed: {e.stderr}'}), 500


# =============================================
#  Main
# =============================================

if __name__ == '__main__':
    print("Server running at http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
