"""
General API routes — PathFinder Career Agent
Serves the main HTML page and provides misc endpoints.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from flask import Blueprint, render_template, jsonify, send_from_directory

api_bp = Blueprint("api", __name__)


# ─── Main page ────────────────────────────────────────────────────────────────
@api_bp.route("/")
def index():
    return render_template("index.html")


# ─── Static fallback ─────────────────────────────────────────────────────────
@api_bp.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "..", "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


# ─── System info ─────────────────────────────────────────────────────────────
@api_bp.route("/api/info")
def info():
    from app.watsonx_client import get_watsonx_client
    client = get_watsonx_client()
    return jsonify({
        "app": "PathFinder Career Agent",
        "version": "1.0.0",
        "powered_by": "IBM Watsonx.ai + Granite",
        "model": os.getenv("GRANITE_CHAT_MODEL", "ibm/granite-3-3-8b-instruct"),
        "demo_mode": client.is_demo,
    })
