"""
RAG Engine — PathFinder Career Agent
Loads the labor market JSON corpus, builds TF-IDF vectors for retrieval,
and optionally upgrades to IBM Watsonx embeddings when available.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

# ─── Data paths ───────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
CORPUS_FILE = DATA_DIR / "labor_market.json"


# ─── Corpus loader ────────────────────────────────────────────────────────────
def _load_corpus() -> dict[str, Any]:
    with open(CORPUS_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ─── Document builder ─────────────────────────────────────────────────────────
def _build_documents(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the JSON corpus into a list of text chunks for retrieval."""
    docs: list[dict[str, Any]] = []

    for role in corpus.get("roles", []):
        salary = role.get("salary_usd", {})
        skills_str = ", ".join(role.get("required_skills", []))
        nh_str = ", ".join(role.get("nice_to_have", []))
        certs_str = ", ".join(role.get("certifications", []))
        paths_str = "; ".join(role.get("entry_paths", []))
        edu_str = ", ".join(role.get("education", []))

        text = (
            f"Role: {role['title']}. "
            f"Category: {role.get('category', '')}. "
            f"Demand: {role.get('demand', '')}. "
            f"Year-over-year growth: {role.get('yoy_growth_pct', 0)}%. "
            f"Salary range (USD): Entry ${salary.get('entry', 0):,} — "
            f"Mid ${salary.get('mid', 0):,} — Senior ${salary.get('senior', 0):,}. "
            f"Required skills: {skills_str}. "
            f"Nice to have: {nh_str}. "
            f"Recommended certifications: {certs_str}. "
            f"Relevant education: {edu_str}. "
            f"Entry paths: {paths_str}. "
            f"Description: {role.get('description', '')}"
        )
        docs.append({"id": role["id"], "type": "role", "title": role["title"], "text": text, "raw": role})

    # Trending skills chunk
    trending = corpus.get("trending_skills_2025", [])
    if trending:
        parts = []
        for item in trending:
            ind = ", ".join(item.get("industries", []))
            parts.append(f"{item['skill']} (demand score {item['demand_score']}/100, industries: {ind})")
        docs.append({
            "id": "trending_skills",
            "type": "trends",
            "title": "Trending Skills 2025",
            "text": "Top in-demand skills in 2025: " + "; ".join(parts),
            "raw": trending,
        })

    # Education map chunk
    edu_map = corpus.get("education_to_career_map", {})
    if edu_map:
        parts = [f"{edu}: {', '.join(roles)}" for edu, roles in edu_map.items()]
        docs.append({
            "id": "edu_map",
            "type": "education",
            "title": "Education to Career Pathways",
            "text": "Education to career pathways: " + "; ".join(parts),
            "raw": edu_map,
        })

    # Industry outlook chunk
    outlook = corpus.get("industry_outlook_2025", {})
    if outlook:
        parts = [
            f"{industry}: {data['outlook']} (hiring index {data['hiring_index']}/100)"
            for industry, data in outlook.items()
        ]
        docs.append({
            "id": "industry_outlook",
            "type": "outlook",
            "title": "Industry Outlook 2025",
            "text": "Industry hiring outlook for 2025: " + "; ".join(parts),
            "raw": outlook,
        })

    return docs


# ─── TF-IDF retriever (no external dependencies) ─────────────────────────────
def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_tfidf_index(docs: list[dict]) -> tuple[list[dict], list[dict[str, float]]]:
    """Returns (docs, tf_idf_vectors) — parallel lists."""
    N = len(docs)
    # Term frequency per doc
    tf_list: list[dict[str, float]] = []
    df: dict[str, int] = {}
    for doc in docs:
        tokens = _tokenize(doc["text"])
        tf: dict[str, float] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        total = max(len(tokens), 1)
        tf = {t: c / total for t, c in tf.items()}
        tf_list.append(tf)
        for t in tf:
            df[t] = df.get(t, 0) + 1

    # IDF
    idf: dict[str, float] = {t: math.log((N + 1) / (cnt + 1)) + 1 for t, cnt in df.items()}

    # TF-IDF vectors
    vectors: list[dict[str, float]] = []
    for tf in tf_list:
        vec = {t: v * idf.get(t, 1) for t, v in tf.items()}
        # L2-normalise
        norm = math.sqrt(sum(v ** 2 for v in vec.values())) or 1.0
        vec = {t: v / norm for t, v in vec.items()}
        vectors.append(vec)

    return docs, vectors


def _cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    shared = set(v1) & set(v2)
    return sum(v1[t] * v2[t] for t in shared)


# ─── Public RAG Engine class ──────────────────────────────────────────────────
class RAGEngine:
    """Simple TF-IDF retrieval engine over the labor market corpus."""

    def __init__(self) -> None:
        corpus = _load_corpus()
        self._corpus = corpus
        raw_docs = _build_documents(corpus)
        self._docs, self._vectors = _build_tfidf_index(raw_docs)
        self._top_k: int = int(os.getenv("RAG_TOP_K", "5"))
        self._threshold: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.30"))

    # ── Core retrieve ─────────────────────────────────────────────────────────
    def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Return top-k most relevant document chunks for a query."""
        k = top_k or self._top_k
        query_tf: dict[str, float] = {}
        tokens = _tokenize(query)
        for t in tokens:
            query_tf[t] = query_tf.get(t, 0) + 1
        total = max(len(tokens), 1)
        query_tf = {t: c / total for t, c in query_tf.items()}
        # Normalise query vector
        norm = math.sqrt(sum(v ** 2 for v in query_tf.values())) or 1.0
        q_vec = {t: v / norm for t, v in query_tf.items()}

        scores = [(_cosine(q_vec, v), i) for i, v in enumerate(self._vectors)]
        scores.sort(reverse=True)

        results: list[dict[str, Any]] = []
        for score, idx in scores[:k]:
            if score >= self._threshold:
                doc = dict(self._docs[idx])
                doc["score"] = round(score, 4)
                results.append(doc)
        return results

    # ── Context builder for LLM prompt ───────────────────────────────────────
    def build_context(self, query: str) -> str:
        """Return a formatted context string to inject into the LLM prompt."""
        docs = self.retrieve(query)
        if not docs:
            return "No specific labor market data found for this query."
        parts = []
        for doc in docs:
            parts.append(f"[{doc['title']}]\n{doc['text']}")
        return "\n\n---\n\n".join(parts)

    # ── Skill-gap analysis ────────────────────────────────────────────────────
    def skill_gap_analysis(self, user_skills: list[str], target_role_id: str) -> dict[str, Any]:
        """Return missing skills and match score for a target role."""
        role_doc = next((d for d in self._docs if d.get("id") == target_role_id and d.get("type") == "role"), None)
        if not role_doc:
            return {"error": f"Role '{target_role_id}' not found in corpus."}

        role_raw = role_doc["raw"]
        required: list[str] = [s.lower() for s in role_raw.get("required_skills", [])]
        nice_to_have: list[str] = [s.lower() for s in role_raw.get("nice_to_have", [])]
        user_lower = [s.lower() for s in user_skills]

        matched = [s for s in required if any(s in u or u in s for u in user_lower)]
        missing = [s for s in required if s not in matched]
        bonus = [s for s in nice_to_have if any(s in u or u in s for u in user_lower)]

        match_score = round(len(matched) / max(len(required), 1) * 100)

        return {
            "role_id": target_role_id,
            "role_title": role_raw["title"],
            "required_skills": role_raw.get("required_skills", []),
            "matched_skills": matched,
            "missing_skills": missing,
            "bonus_skills": bonus,
            "match_score": match_score,
            "salary_range": role_raw.get("salary_usd", {}),
            "certifications": role_raw.get("certifications", []),
            "entry_paths": role_raw.get("entry_paths", []),
        }

    # ── All roles summary ─────────────────────────────────────────────────────
    def get_all_roles(self) -> list[dict[str, Any]]:
        return [d["raw"] for d in self._docs if d.get("type") == "role"]

    def get_trending_skills(self) -> list[dict[str, Any]]:
        doc = next((d for d in self._docs if d.get("id") == "trending_skills"), None)
        return doc["raw"] if doc else []

    def get_industry_outlook(self) -> dict[str, Any]:
        doc = next((d for d in self._docs if d.get("id") == "industry_outlook"), None)
        return doc["raw"] if doc else {}


# ─── Singleton ────────────────────────────────────────────────────────────────
_engine_instance: RAGEngine | None = None


def get_rag_engine() -> RAGEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RAGEngine()
    return _engine_instance
