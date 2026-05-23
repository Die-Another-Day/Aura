"""
Text-to-speech using pyttsx3.

Generates WAV files for the web client to play, since browser cannot
use the server's speakers directly in a remote deployment.
"""

import logging
import os
import uuid
from pathlib import Path

import pyttsx3

logger = logging.getLogger(__name__)

# Long Gemini replies make huge WAV files; cap spoken length (full text stays in chat)
TTS_MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "450"))


def truncate_for_tts(text: str, max_chars: int | None = None) -> str:
    """Shorten text for speech only; chat UI still shows the full reply."""
    limit = max_chars if max_chars is not None else TTS_MAX_CHARS
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit].rsplit(" ", 1)[0]
    return f"{cut}… Full answer is in the chat."

# Directory for generated speech files (served by Flask)
AUDIO_DIR = Path(__file__).resolve().parent.parent / "data" / "audio"

_engine: pyttsx3.Engine | None = None


def _get_engine() -> pyttsx3.Engine:
    """Lazy-init TTS engine (pyttsx3 is not thread-safe; use one instance)."""
    global _engine
    if _engine is None:
        _engine = pyttsx3.init()
        # Slightly slower rate for clearer voice assistant speech
        rate = _engine.getProperty("rate")
        _engine.setProperty("rate", max(150, int(rate * 0.9)))
        voices = _engine.getProperty("voices")
        # Prefer a female voice if available (common assistant convention)
        for voice in voices:
            if "female" in voice.name.lower() or "zira" in voice.id.lower():
                _engine.setProperty("voice", voice.id)
                break
    return _engine


def speak_to_file(text: str) -> str:
    """
    Convert text to speech and save as a WAV file.

    Args:
        text: Text to speak.

    Returns:
        Filename (not full path) of the generated audio in data/audio/.
    """
    if not text or not text.strip():
        raise ValueError("No text provided for speech synthesis.")

    text = truncate_for_tts(text)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"tts_{uuid.uuid4().hex[:12]}.wav"
    filepath = AUDIO_DIR / filename

    try:
        engine = _get_engine()
        engine.save_to_file(text.strip(), str(filepath))
        engine.runAndWait()
        if not filepath.exists():
            raise RuntimeError("TTS file was not created.")
        return filename
    except Exception as exc:
        logger.exception("TTS error")
        raise RuntimeError(f"Text-to-speech failed: {exc}") from exc


def speak_locally(text: str) -> None:
    """
    Speak text through the server's speakers (local use only).

    Args:
        text: Text to speak aloud.
    """
    if not text or not text.strip():
        return
    try:
        engine = _get_engine()
        engine.say(text.strip())
        engine.runAndWait()
    except Exception as exc:
        logger.exception("Local TTS error: %s", exc)
