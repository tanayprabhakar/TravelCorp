from src.engine import EscalationEngine
import sys

def main():
    print("Credit Follow-Up — Processing invoices")
    print("-" * 50)
    
    try:
        engine = EscalationEngine()
        engine.process_invoices()
        print("-" * 50)
        print("Done. Check data/audit.db for logs.")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("Make sure .env contains a valid OPENAI_API_KEY.")
        sys.exit(1)

if __name__ == "__main__":
    main()
