"""
Dashboard routes — PathFinder Career Agent
Handles:
  GET  /api/dashboard/overview        — full dashboard data
  POST /api/dashboard/skill-gap       — skill gap analysis for a target role
  GET  /api/dashboard/roles           — all available career roles
  GET  /api/dashboard/trending        — trending skills
  GET  /api/dashboard/outlook         — industry hiring outlook
  POST /api/dashboard/roadmap         — generate a roadmap for a student profile
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from flask import Blueprint, jsonify, request

from app.rag_engine import get_rag_engine
from app.watsonx_client import get_watsonx_client
from config.agent_instructions import build_system_prompt

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


# ─── GET /api/dashboard/overview ─────────────────────────────────────────────
@dashboard_bp.route("/overview", methods=["GET"])
def overview():
    rag = get_rag_engine()
    client = get_watsonx_client()
    return jsonify({
        "roles": rag.get_all_roles(),
        "trending_skills": rag.get_trending_skills(),
        "industry_outlook": rag.get_industry_outlook(),
        "demo_mode": client.is_demo,
    })


# ─── POST /api/dashboard/skill-gap ───────────────────────────────────────────
@dashboard_bp.route("/skill-gap", methods=["POST"])
def skill_gap():
    body = request.get_json(silent=True) or {}
    user_skills: list[str] = body.get("skills", [])
    target_role_id: str = body.get("role_id", "")

    if not target_role_id:
        return jsonify({"error": "role_id is required."}), 400

    if isinstance(user_skills, str):
        user_skills = [s.strip() for s in user_skills.split(",") if s.strip()]

    rag = get_rag_engine()
    result = rag.skill_gap_analysis(user_skills, target_role_id)
    return jsonify(result)


# ─── POST /api/dashboard/skill-gap/multi ─────────────────────────────────────
@dashboard_bp.route("/skill-gap/multi", methods=["POST"])
def skill_gap_multi():
    """Return skill-gap scores for all roles given user skills."""
    body = request.get_json(silent=True) or {}
    user_skills: list[str] = body.get("skills", [])

    if isinstance(user_skills, str):
        user_skills = [s.strip() for s in user_skills.split(",") if s.strip()]

    rag = get_rag_engine()
    results = []
    for role in rag.get_all_roles():
        gap = rag.skill_gap_analysis(user_skills, role["id"])
        if "error" not in gap:
            results.append(gap)

    # Sort by match score descending
    results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return jsonify({"results": results, "user_skills": user_skills})


# ─── GET /api/dashboard/roles ────────────────────────────────────────────────
@dashboard_bp.route("/roles", methods=["GET"])
def get_roles():
    rag = get_rag_engine()
    return jsonify({"roles": rag.get_all_roles()})


# ─── GET /api/dashboard/trending ────────────────────────────────────────────
@dashboard_bp.route("/trending", methods=["GET"])
def trending():
    rag = get_rag_engine()
    return jsonify({"trending_skills": rag.get_trending_skills()})


# ─── GET /api/dashboard/outlook ─────────────────────────────────────────────
@dashboard_bp.route("/outlook", methods=["GET"])
def outlook():
    rag = get_rag_engine()
    return jsonify({"industry_outlook": rag.get_industry_outlook()})


# ─── POST /api/dashboard/roadmap ────────────────────────────────────────────
@dashboard_bp.route("/roadmap", methods=["POST"])
def generate_roadmap():
    """Ask the AI to generate a structured 6-month roadmap for a student profile."""
    body = request.get_json(silent=True) or {}
    profile = body.get("profile", {})

    if not profile:
        return jsonify({"error": "A student profile is required."}), 400

    rag = get_rag_engine()
    client = get_watsonx_client()

    # Build a descriptive query
    name = profile.get("name", "the student")
    edu = profile.get("education", "unspecified field")
    skills = profile.get("skills", [])
    interests = profile.get("interests", "")

    if isinstance(skills, list):
        skills_str = ", ".join(skills)
    else:
        skills_str = str(skills)

    query = (
        f"Generate a detailed 6-month career roadmap for {name}, "
        f"studying {edu}, with skills: {skills_str}, interested in: {interests}. "
        "Include monthly milestones, specific resources, and measurable goals."
    )

    context = rag.build_context(query)
    system_prompt = build_system_prompt()
    system_prompt += f"\n\n## CURRENT LABOR MARKET CONTEXT\n{context}"

    roadmap_prompt = (
        f"Create a structured 6-month career roadmap for the following student profile:\n"
        f"- Name: {name}\n"
        f"- Education/Field: {edu}\n"
        f"- Current Skills: {skills_str}\n"
        f"- Interests: {interests}\n\n"
        "Format the roadmap with clear monthly phases (Month 1-2, Month 3-4, Month 5-6), "
        "each with specific actions, resources, and success metrics. "
        "Base recommendations on the provided labor market context."
    )

    roadmap = client.complete(system_prompt, roadmap_prompt)

    return jsonify({
        "roadmap": roadmap,
        "profile": profile,
        "demo_mode": client.is_demo,
    })
