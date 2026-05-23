"""
AURA AI Voice Assistant — Flask application entry point.

REST API routes:
  GET  /              — Main UI
  GET  /api/health    — Health check
  POST /api/chat      — Process message (commands + Gemini AI)
  POST /api/listen    — Server microphone STT
  POST /api/transcribe — Upload audio STT
  POST /api/speak     — TTS → audio file URL
  GET  /api/audio/<filename> — Serve generated TTS files
  GET  /api/history   — Load chat history
  POST /api/history   — Save chat history
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

from utils.commands import detect_command, execute_command
from utils.gemini_ai import get_gemini_response, is_gemini_key_configured
from utils.speech_to_text import listen_from_microphone, transcribe_audio_file
from utils.text_to_speech import speak_to_file

# Load environment variables from .env
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "chat_history.json"
AUDIO_DIR = DATA_DIR / "audio"

# Flask app
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
CORS(app)


def _error(message: str, status: int = 400):
    """Standard JSON error response."""
    return jsonify({"success": False, "error": message}), status


def _success(data: dict, status: int = 200):
    """Standard JSON success response."""
    return jsonify({"success": True, **data}), status


# ---------------------------------------------------------------------------
# Routes: UI
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Serve the main voice assistant interface."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes: Health
# ---------------------------------------------------------------------------


@app.route("/api/health")
def health():
    """Health check for monitoring and frontend connectivity."""
    ok = is_gemini_key_configured()
    return _success({
        "status": "ok",
        "service": "AURA Voice Assistant",
        "gemini_configured": ok,
        "gemini_setup_hint": (
            None
            if ok
            else "Open https://aistudio.google.com/apikey — paste the key into .env as GEMINI_API_KEY=... and restart Flask (not the placeholder text)."
        ),
    })


# ---------------------------------------------------------------------------
# Routes: Chat & AI
# ---------------------------------------------------------------------------


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Process a user message.

    Body JSON: { "message": "...", "history": [...], "speak": true|false }
    """
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        history = data.get("history") or []
        speak = data.get("speak", False)

        if not message:
            return _error("Message is required.", 400)

        # Check built-in voice commands first
        command_handler = detect_command(message)
        if command_handler:
            result = execute_command(command_handler, message)
            response_text = result.get("response", "")
            payload = {
                "response": response_text,
                "source": "command",
                "action": result.get("action"),
                "url": result.get("url"),
            }
        else:
            # General conversation via Gemini
            if not is_gemini_key_configured():
                return _error(
                    "Replace GEMINI_API_KEY in .env with a real key from "
                    "https://aistudio.google.com/apikey (remove the placeholder), then restart Flask.",
                    503,
                )
            response_text = get_gemini_response(message, history=history)
            payload = {
                "response": response_text,
                "source": "gemini",
            }

        # Optional TTS
        if speak and response_text:
            try:
                filename = speak_to_file(response_text)
                payload["audio_url"] = f"/api/audio/{filename}"
            except Exception as exc:
                logger.warning("TTS failed: %s", exc)
                payload["tts_error"] = str(exc)

        return _success(payload)

    except ValueError as exc:
        return _error(str(exc), 400)
    except RuntimeError as exc:
        return _error(str(exc), 502)
    except Exception as exc:
        logger.exception("Chat error")
        return _error(f"An unexpected error occurred: {exc}", 500)


# ---------------------------------------------------------------------------
# Routes: Speech-to-text
# ---------------------------------------------------------------------------


@app.route("/api/listen", methods=["POST"])
def listen():
    """Capture speech from server microphone and return transcription."""
    try:
        data = request.get_json(silent=True) or {}
        timeout = int(data.get("timeout", 5))
        phrase_limit = int(data.get("phrase_limit", 10))
        text = listen_from_microphone(timeout=timeout, phrase_limit=phrase_limit)
        return _success({"text": text})
    except RuntimeError as exc:
        return _error(str(exc), 422)
    except Exception as exc:
        logger.exception("Listen error")
        return _error(str(exc), 500)


@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    """
    Transcribe uploaded audio file.

    Form field: audio (file)
    """
    if "audio" not in request.files:
        return _error("No audio file provided. Use form field 'audio'.", 400)

    audio_file = request.files["audio"]
    if not audio_file.filename:
        return _error("Empty audio file.", 400)

    suffix = Path(audio_file.filename).suffix or ".wav"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            audio_file.save(tmp_path)
            text = transcribe_audio_file(tmp_path)
        return _success({"text": text})
    except RuntimeError as exc:
        return _error(str(exc), 422)
    except Exception as exc:
        logger.exception("Transcribe error")
        return _error(str(exc), 500)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Routes: Text-to-speech
# ---------------------------------------------------------------------------


@app.route("/api/speak", methods=["POST"])
def speak():
    """
    Convert text to speech and return audio URL.

    Body JSON: { "text": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        if not text:
            return _error("Text is required.", 400)
        filename = speak_to_file(text)
        return _success({"audio_url": f"/api/audio/{filename}"})
    except ValueError as exc:
        return _error(str(exc), 400)
    except RuntimeError as exc:
        return _error(str(exc), 502)
    except Exception as exc:
        logger.exception("Speak error")
        return _error(str(exc), 500)


@app.route("/api/audio/<filename>")
def serve_audio(filename):
    """Serve generated TTS audio files."""
    # Prevent path traversal
    safe_name = Path(filename).name
    if safe_name != filename:
        return _error("Invalid filename.", 400)
    return send_from_directory(AUDIO_DIR, safe_name, mimetype="audio/wav")


# ---------------------------------------------------------------------------
# Routes: Chat history persistence
# ---------------------------------------------------------------------------


@app.route("/api/history", methods=["GET"])
def get_history():
    """Load persisted chat history from server (optional sync)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        return _success({"history": []})
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)
        return _success({"history": history})
    except Exception as exc:
        logger.exception("History read error")
        return _error(str(exc), 500)


@app.route("/api/history", methods=["POST"])
def save_history():
    """
    Save chat history to server.

    Body JSON: { "history": [...] }
    """
    try:
        data = request.get_json(silent=True) or {}
        history = data.get("history", [])
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        return _success({"saved": len(history)})
    except Exception as exc:
        logger.exception("History save error")
        return _error(str(exc), 500)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("1", "true", "yes")
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug)
