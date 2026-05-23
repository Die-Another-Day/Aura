"""
Speech-to-text using SpeechRecognition library.

Supports:
  - Server microphone capture (local dev)
  - Transcription from uploaded audio (web client)
"""

import io
import logging
import tempfile
from pathlib import Path

import speech_recognition as sr

logger = logging.getLogger(__name__)

# Google Web Speech API is free and works without extra keys for STT fallback
RECOGNIZER = sr.Recognizer()


def listen_from_microphone(timeout: int = 5, phrase_limit: int = 10) -> str:
    """
    Capture audio from the server's default microphone and transcribe.

    Args:
        timeout: Seconds to wait for speech to start.
        phrase_limit: Max seconds of speech to record.

    Returns:
        Transcribed text.

    Raises:
        RuntimeError: On mic or recognition failure.
    """
    try:
        with sr.Microphone() as source:
            logger.info("Adjusting for ambient noise...")
            RECOGNIZER.adjust_for_ambient_noise(source, duration=0.5)
            logger.info("Listening...")
            audio = RECOGNIZER.listen(
                source, timeout=timeout, phrase_time_limit=phrase_limit
            )
        return _recognize_audio(audio)
    except sr.WaitTimeoutError:
        raise RuntimeError("No speech detected. Please try again.") from None
    except OSError as exc:
        raise RuntimeError(
            f"Microphone not available: {exc}. "
            "On Windows, install PyAudio or use browser voice input."
        ) from exc
    except Exception as exc:
        logger.exception("Microphone listen error")
        raise RuntimeError(f"Speech recognition failed: {exc}") from exc


def transcribe_audio_file(file_path: str | Path) -> str:
    """
    Transcribe audio from a file (WAV, FLAC, etc.).

    Args:
        file_path: Path to the audio file.

    Returns:
        Transcribed text.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    with sr.AudioFile(str(path)) as source:
        audio = RECOGNIZER.record(source)
    return _recognize_audio(audio)


def transcribe_audio_bytes(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    """
    Transcribe raw audio bytes (e.g. from browser upload).

    Args:
        audio_bytes: Raw PCM or WAV bytes.
        sample_rate: Sample rate if raw PCM.

    Returns:
        Transcribed text.
    """
    try:
        # Try as WAV first
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = RECOGNIZER.record(source)
        return _recognize_audio(audio)
    except Exception:
        # Fallback: treat as AudioData if needed
        audio = sr.AudioData(audio_bytes, sample_rate, 2)
        return _recognize_audio(audio)


def _recognize_audio(audio: sr.AudioData) -> str:
    """Run recognition with Google Web Speech API, fallback to Sphinx if offline."""
    try:
        text = RECOGNIZER.recognize_google(audio)
        return text.strip()
    except sr.UnknownValueError:
        raise RuntimeError("Could not understand audio. Please speak clearly.") from None
    except sr.RequestError as exc:
        logger.warning("Google STT unavailable: %s", exc)
        try:
            text = RECOGNIZER.recognize_sphinx(audio)
            return text.strip()
        except Exception:
            raise RuntimeError(
                "Speech service unavailable. Check your internet connection."
            ) from exc
