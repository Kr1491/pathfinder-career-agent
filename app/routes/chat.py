"""
Chat routes — PathFinder Career Agent
Handles:
  POST /api/chat          — full response
  POST /api/chat/stream   — Server-Sent Events streaming
  GET  /api/chat/session  — session info
  DELETE /api/chat/session — clear history
"""

from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from flask import Blueprint, Response, jsonify, request, session, stream_with_context

from app.rag_engine import get_rag_engine
from app.watsonx_client import get_watsonx_client

# Load agent instructions from config (project root /config)
from config.agent_instructions import build_system_prompt

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

# ─── Session helpers ──────────────────────────────────────────────────────────
_MAX_HISTORY = 20  # messages kept per session


def _get_history() -> list[dict]:
    return session.get("chat_history", [])


def _save_history(history: list[dict]) -> None:
    session["chat_history"] = history[-_MAX_HISTORY:]


# ─── POST /api/chat ──────────────────────────────────────────────────────────
@chat_bp.route("", methods=["POST"])
def chat():
    """Full (non-streaming) chat completion."""
    body = request.get_json(silent=True) or {}
    user_msg: str = (body.get("message") or "").strip()
    profile: dict = body.get("profile", {})  # optional student profile

    if not user_msg:
        return jsonify({"error": "Message is required."}), 400

    history = _get_history()
    rag = get_rag_engine()
    client = get_watsonx_client()

    # Build enriched query using profile context
    enriched_query = _enrich_query(user_msg, profile)

    # RAG retrieval
    context = rag.build_context(enriched_query)

    # Build system prompt with RAG context injected
    system_prompt = build_system_prompt()
    system_prompt += f"\n\n## CURRENT LABOR MARKET CONTEXT\n{context}"

    # Generate response
    assistant_msg = client.complete(system_prompt, enriched_query, history)

    # Persist history
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})
    _save_history(history)

    return jsonify({
        "response": assistant_msg,
        "demo_mode": client.is_demo,
        "context_docs_used": len(rag.retrieve(enriched_query)),
    })


# ─── POST /api/chat/stream ───────────────────────────────────────────────────
@chat_bp.route("/stream", methods=["POST"])
def chat_stream():
    """Server-Sent Events streaming chat."""
    body = request.get_json(silent=True) or {}
    user_msg: str = (body.get("message") or "").strip()
    profile: dict = body.get("profile", {})

    if not user_msg:
        return jsonify({"error": "Message is required."}), 400

    history = _get_history()
    rag = get_rag_engine()
    client = get_watsonx_client()

    enriched_query = _enrich_query(user_msg, profile)
    context = rag.build_context(enriched_query)

    system_prompt = build_system_prompt()
    system_prompt += f"\n\n## CURRENT LABOR MARKET CONTEXT\n{context}"

    # Buffer tokens to also save complete response to history
    full_response: list[str] = []

    def event_generator():
        for token in client.stream(system_prompt, enriched_query, history):
            full_response.append(token)
            data = json.dumps({"token": token})
            yield f"data: {data}\n\n"

        # Signal completion
        yield "data: [DONE]\n\n"

        # Persist to session
        complete = "".join(full_response)
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": complete})
        _save_history(history)

    return Response(
        stream_with_context(event_generator()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── GET /api/chat/session ───────────────────────────────────────────────────
@chat_bp.route("/session", methods=["GET"])
def get_session():
    return jsonify({
        "history": _get_history(),
        "message_count": len(_get_history()),
    })


# ─── DELETE /api/chat/session ────────────────────────────────────────────────
@chat_bp.route("/session", methods=["DELETE"])
def clear_session():
    session.pop("chat_history", None)
    return jsonify({"status": "cleared"})


# ─── Internal helpers ─────────────────────────────────────────────────────────
def _enrich_query(user_msg: str, profile: dict) -> str:
    """Prepend relevant profile info to the raw message for better RAG hits."""
    if not profile:
        return user_msg
    parts = [user_msg]
    if profile.get("education"):
        parts.append(f"(Student education: {profile['education']})")
    if profile.get("skills"):
        skills = profile["skills"] if isinstance(profile["skills"], str) else ", ".join(profile["skills"])
        parts.append(f"(Current skills: {skills})")
    if profile.get("interests"):
        parts.append(f"(Interests: {profile['interests']})")
    return " ".join(parts)
