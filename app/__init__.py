"""
Flask Application — PathFinder Career Agent
Main entry point: registers all blueprints and initialises extensions.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# Load .env before any other imports that read environment variables
load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS

# Ensure the project root is on the path so sibling packages resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.routes.chat import chat_bp
from app.routes.dashboard import dashboard_bp
from app.routes.api import api_bp


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

    # CORS for local dev / external frontends
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ── Register blueprints ───────────────────────────────────────────────────
    app.register_blueprint(chat_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)

    # ── Health endpoint ───────────────────────────────────────────────────────
    @app.route("/health")
    def health():
        from app.watsonx_client import get_watsonx_client
        client = get_watsonx_client()
        return jsonify({
            "status": "ok",
            "demo_mode": client.is_demo,
            "model": os.getenv("GRANITE_CHAT_MODEL", "ibm/granite-3-3-8b-instruct"),
        })

    # ── Error handlers ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app
