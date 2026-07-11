"""
PathFinder Career Agent — Application entry point
Run with: python run.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    print(f"\n🧭 PathFinder Career Agent starting on http://localhost:{port}")
    print(f"   Debug mode: {debug}")
    print(f"   Demo mode: {os.getenv('IBM_API_KEY', '') == ''}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
