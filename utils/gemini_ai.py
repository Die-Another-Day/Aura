"""
Google Gemini AI integration.

Handles conversational responses with optional chat history context.
"""

import os
import logging
from typing import Any

import google.generativeai as genai

logger = logging.getLogger(__name__)

# System prompt keeps the assistant helpful and concise for voice UI
SYSTEM_INSTRUCTION = """You are AURA, a friendly and intelligent AI voice assistant.
Keep responses concise (2-4 sentences) unless the user asks for detail.
Be conversational, helpful, and clear. You can help with general knowledge,
coding, explanations, and everyday questions. If you don't know something, say so honestly."""


_PLACEHOLDER_KEYS = frozenset(
    {
        "your_gemini_api_key_here",
        "paste_your_key_from_aistudio_here",
        "paste_your_key_here",
        "api_key_here",
        "your_api_key",
    }
)


def normalize_gemini_api_key(raw: str | None) -> str:
    """Strip whitespace and surrounding quotes from .env values."""
    if not raw:
        return ""
    return raw.strip().strip('"').strip("'")


def is_gemini_key_configured() -> bool:
    """
    True only if .env has a non-placeholder Gemini key.

    A common mistake is leaving the template value `your_gemini_api_key_here`,
    which makes /api/chat return HTTP 400 from Google.
    """
    key = normalize_gemini_api_key(os.getenv("GEMINI_API_KEY"))
    if not key or len(key) < 20:
        return False
    if key.lower() in {p.lower() for p in _PLACEHOLDER_KEYS}:
        return False
    return True


def _configure_client() -> None:
    """Configure the Gemini client with the API key from environment."""
    api_key = normalize_gemini_api_key(os.getenv("GEMINI_API_KEY"))
    if not is_gemini_key_configured():
        raise ValueError(
            "GEMINI_API_KEY is missing or still the template placeholder. "
            "Open https://aistudio.google.com/apikey , create a key, and paste it into .env "
            "as GEMINI_API_KEY=... (no quotes). Then restart the Flask server."
        )
    genai.configure(api_key=api_key)


def get_gemini_response(
    user_message: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    """
    Generate an AI response using Google Gemini.

    Args:
        user_message: The user's latest message.
        history: Optional list of prior turns [{"role": "user"|"assistant", "content": "..."}].

    Returns:
        The assistant's text response.

    Raises:
        ValueError: If API key is missing.
        Exception: On API or network errors (logged and re-raised with friendly message).
    """
    _configure_client()
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    try:
        model = genai.GenerativeModel(
            model_name,
            system_instruction=SYSTEM_INSTRUCTION,
        )

        # Build multi-turn chat if history exists
        if history:
            chat = model.start_chat(history=_format_history(history))
            response = chat.send_message(user_message)
        else:
            response = model.generate_content(user_message)

        text = response.text.strip() if response.text else ""
        if not text:
            return "I'm sorry, I couldn't generate a response. Please try again."
        return text

    except ValueError:
        raise
    except Exception as exc:
        logger.exception("Gemini API error: %s", exc)
        err_txt = str(exc)
        if "API_KEY_INVALID" in err_txt or "API key not valid" in err_txt:
            raise RuntimeError(
                "Invalid Gemini API key. Get a new key at https://aistudio.google.com/apikey "
                "and set GEMINI_API_KEY in .env (no quotes, no spaces). Restart the server."
            ) from exc
        raise RuntimeError(
            f"AI service error: {exc}. Check your API key and network connection."
        ) from exc


def _format_history(history: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Convert frontend history format to Gemini chat history format.

    Gemini expects: {"role": "user"|"model", "parts": ["text"]}
    """
    formatted = []
    for turn in history[-20:]:  # Limit context window
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if not content:
            continue
        gemini_role = "model" if role == "assistant" else "user"
        formatted.append({"role": gemini_role, "parts": [content]})
    return formatted
