"""
IBM Watsonx.ai Client — PathFinder Career Agent
Wraps the ibm-watsonx-ai SDK for chat completions with Granite models.
Falls back to a mock response when credentials are missing (dev mode).
"""

from __future__ import annotations

import os
from typing import Any, Generator

# ─── Optional SDK import (graceful fallback) ──────────────────────────────────
try:
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


# ─── Config ───────────────────────────────────────────────────────────────────
IBM_API_KEY = os.getenv("IBM_API_KEY", "")
IBM_PROJECT_ID = os.getenv("IBM_PROJECT_ID", "")
IBM_WATSONX_URL = os.getenv("IBM_WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
GRANITE_CHAT_MODEL = os.getenv("GRANITE_CHAT_MODEL", "ibm/granite-3-3-8b-instruct")

# Generation hyper-parameters
DEFAULT_PARAMS: dict[str, Any] = {
    "max_new_tokens": 1024,
    "min_new_tokens": 50,
    "temperature": 0.7,
    "top_p": 0.9,
    "repetition_penalty": 1.1,
    "stop_sequences": ["<|endoftext|>", "Human:", "User:"],
}


# ─── Mock response (dev / no-credentials mode) ────────────────────────────────
_MOCK_RESPONSE = """
## 🎯 Career Roadmap — Demo Mode

> **Note:** PathFinder is running in **demo mode** (no IBM API credentials configured).
> Once you add your `IBM_API_KEY` and `IBM_PROJECT_ID` to the `.env` file, you'll get
> real AI-powered recommendations from IBM Granite models.

### Sample Career Paths

**1. Software Engineer**
- Required skills: Python, JavaScript, Data Structures, Git
- Salary range: $80K–$195K USD
- First step: Build a portfolio project on GitHub this week.

**2. Data Scientist**
- Required skills: Python, SQL, Machine Learning, Statistics
- Salary range: $85K–$185K USD
- First step: Complete the IBM Data Science Professional Certificate on Coursera.

**3. Cloud Solutions Architect**
- Required skills: AWS/Azure/GCP, Terraform, Kubernetes
- Salary range: $105K–$230K USD
- First step: Earn your first cloud associate certification (AWS or Azure).

*Your potential is limitless — keep exploring!* 🚀
"""


# ─── Response cleaning helpers ────────────────────────────────────────────────
import re as _re

# All Granite / instruct-format special tokens that should never reach the UI.
_SPECIAL_TOKEN_RE = _re.compile(
    r"<\|(?:system|user|assistant|endoftext|pad|eos|bos|sep|cls|mask|"
    r"end_of_turn|start_of_turn|im_start|im_end|EOT|eot_id|"
    r"begin_of_text|end_of_text)\|>",
    _re.IGNORECASE,
)


def _clean_response(text: str) -> str:
    """
    Strip Granite special tokens and tidy up the text for display.

    Removes:
      • Any <|token|> sentinel (user, assistant, system, endoftext, …)
      • Leading/trailing whitespace left behind after removal
    """
    cleaned = _SPECIAL_TOKEN_RE.sub("", text)
    # Collapse runs of 3+ blank lines down to 2 (one paragraph break)
    cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _split_safe(buf: str) -> tuple[str, str]:
    """
    Split *buf* into (safe_to_yield, remainder).

    We hold back a small tail so that a special token straddling two chunks
    is never emitted half-cleaned.  A special token is at most ~30 chars,
    so holding back 32 characters is sufficient.
    """
    cleaned = _clean_response(buf)
    if len(cleaned) <= 32:
        # Too short to safely split — hold everything
        return "", cleaned
    safe = cleaned[:-32]
    remainder = cleaned[-32:]
    return safe, remainder


# ─── Watsonx client ───────────────────────────────────────────────────────────
class WatsonxClient:
    """
    Thin wrapper around ibm-watsonx-ai for single-turn and streaming generation.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._demo_mode = False
        self._init_model()

    def _init_model(self) -> None:
        if not SDK_AVAILABLE:
            print("[WatsonxClient] ibm-watsonx-ai SDK not installed — running in demo mode.")
            self._demo_mode = True
            return

        if not IBM_API_KEY or not IBM_PROJECT_ID:
            print("[WatsonxClient] IBM_API_KEY or IBM_PROJECT_ID not set — running in demo mode.")
            self._demo_mode = True
            return

        try:
            credentials = Credentials(url=IBM_WATSONX_URL, api_key=IBM_API_KEY)
            self._model = ModelInference(
                model_id=GRANITE_CHAT_MODEL,
                credentials=credentials,
                project_id=IBM_PROJECT_ID,
            )
            print(f"[WatsonxClient] Connected to model: {GRANITE_CHAT_MODEL}")
        except Exception as exc:
            print(f"[WatsonxClient] Failed to initialise model — demo mode. Error: {exc}")
            self._demo_mode = True

    # ── Single-turn completion ────────────────────────────────────────────────
    def complete(self, system_prompt: str, user_message: str, history: list[dict] | None = None) -> str:
        """Return a complete response string."""
        if self._demo_mode:
            return _MOCK_RESPONSE

        prompt = self._build_prompt(system_prompt, user_message, history)
        try:
            response = self._model.generate_text(
                prompt=prompt,
                params=DEFAULT_PARAMS,
            )
            return response.strip() if isinstance(response, str) else str(response)
        except Exception as exc:
            return f"⚠️ Generation error: {exc}\n\nPlease check your IBM credentials and try again."

    # ── Streaming completion ──────────────────────────────────────────────────
    def stream(self, system_prompt: str, user_message: str, history: list[dict] | None = None) -> Generator[str, None, None]:
        """Yield response tokens one at a time (SSE-compatible)."""
        if self._demo_mode:
            # Simulate streaming in demo mode
            for word in _MOCK_RESPONSE.split(" "):
                yield word + " "
            return

        prompt = self._build_prompt(system_prompt, user_message, history)
        try:
            for chunk in self._model.generate_text_stream(prompt=prompt, params=DEFAULT_PARAMS):
                if chunk:
                    yield chunk
        except Exception as exc:
            yield f"\n\n⚠️ Streaming error: {exc}"

    # ── Response cleaner ─────────────────────────────────────────────────────
    # (see module-level _clean_response / _split_safe helpers below)

    # ── Prompt formatter ─────────────────────────────────────────────────────
    def _build_prompt(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Format a Granite-compatible prompt.
        Granite uses: <|system|>\n...\n<|user|>\n...\n<|assistant|>
        """
        parts: list[str] = [f"<|system|>\n{system_prompt}\n"]

        if history:
            for turn in history[-6:]:  # last 3 pairs
                role = turn.get("role", "user")
                content = turn.get("content", "")
                parts.append(f"<|{role}|>\n{content}\n")

        parts.append(f"<|user|>\n{user_message}\n<|assistant|>\n")
        return "".join(parts)

    @property
    def is_demo(self) -> bool:
        return self._demo_mode


# ─── Singleton ────────────────────────────────────────────────────────────────
_client_instance: WatsonxClient | None = None


def get_watsonx_client() -> WatsonxClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = WatsonxClient()
    return _client_instance
