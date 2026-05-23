# AURA — AI Voice Assistant

A production-ready AI voice assistant web app built with **Flask**, **Google Gemini**, **SpeechRecognition**, and **pyttsx3**. Features a futuristic dark UI with glassmorphism, voice input, text-to-speech, chat history, and built-in voice commands.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange)

## Features

| Feature | Description |
|---------|-------------|
| Voice input | Browser Web Speech API + server microphone STT |
| Speech-to-text | Google Web Speech API via SpeechRecognition (needs **internet**) |
| AI chat | Google Gemini (`gemini-2.5-flash` by default) |
| Text-to-speech | pyttsx3 generates WAV for browser playback |
| Voice commands | YouTube, Google, time, date, weather, music |
| UI | Dark theme, glassmorphism, animated mic, typing effect |
| Chat history | localStorage + optional server JSON sync |

## Project Structure

```
voiceassistant/
├── app.py                 # Flask app & REST routes
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
├── README.md
├── static/
│   ├── style.css          # Glassmorphism dark theme
│   └── script.js          # Chat, voice, typing effect
├── templates/
│   └── index.html         # Main UI
├── utils/
│   ├── gemini_ai.py       # Google Gemini integration
│   ├── speech_to_text.py  # SpeechRecognition STT
│   ├── text_to_speech.py  # pyttsx3 TTS
│   └── commands.py        # Voice command handlers
└── data/
    ├── audio/             # Generated TTS files
    └── chat_history.json  # Server-side history (optional)
```

## Quick Start

### 1. Prerequisites

- Python 3.10 or higher
- Microphone (for voice input)
- [Google Gemini API key](https://aistudio.google.com/apikey)
- (Optional) [OpenWeatherMap API key](https://openweathermap.org/api) for weather

### Voice input needs internet

In **Chrome / Edge**, the microphone uses the browser’s **Web Speech API**, which sends audio to **Google’s speech service** in the cloud — it does **not** run fully on your PC, so **Wi‑Fi or Ethernet must be available**.

The **server** STT path (`/api/listen`, `speech_to_text.py`) also uses **Google’s web speech** (or Sphinx as a weak offline fallback), so it also expects network access for good results.

**Offline:** use **typing** in the text box, or integrate a local model later (e.g. Whisper on the server with recorded audio).

### 2. Clone & virtual environment

```powershell
cd c:\aiml\voiceassistant
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

**Windows PyAudio note:** If `PyAudio` fails to install, server-side microphone won't work, but browser voice input still works. Try:

```powershell
pip install pipwin
pipwin install pyaudio
```

### 4. Configure environment

```powershell
copy .env.example .env
```

Edit `.env` and set your keys:

```env
GEMINI_API_KEY=your_actual_key_here
OPENWEATHER_API_KEY=your_key_here
DEFAULT_CITY=London
```

### 5. Run the application

```powershell
python app.py
```

Open **http://127.0.0.1:5000** in Chrome or Edge (best Web Speech API support).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Main web UI |
| `GET` | `/api/health` | Health & config check |
| `POST` | `/api/chat` | Send message → AI or command response |
| `POST` | `/api/listen` | Server microphone STT |
| `POST` | `/api/transcribe` | Upload audio file for STT |
| `POST` | `/api/speak` | Text → TTS audio URL |
| `GET` | `/api/audio/<file>` | Serve TTS WAV file |
| `GET/POST` | `/api/history` | Load/save chat history |

### Example: Chat request

```json
POST /api/chat
{
  "message": "What is machine learning?",
  "history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"}
  ],
  "speak": true
}
```

## Voice Commands

| Say something like… | Action |
|---------------------|--------|
| "Open YouTube" | Opens youtube.com |
| "Open Google" | Opens google.com |
| "What time is it?" | Speaks current time |
| "What's the date?" | Speaks today's date |
| "Weather in Paris" | Fetches weather (needs API key) |
| "Play music" | Opens YouTube relaxing music |
| "Play song Blinding Lights" / "Play Despacito" | YouTube search for that song (pick top result) |

Commands are matched **before** Gemini, so they run instantly without an API call.

## Architecture

```
Browser (mic/text) → Flask REST API → commands.py OR gemini_ai.py
                                    → text_to_speech.py → audio WAV
                                    → JSON response → UI + typing effect
```

- **Modular utils/** — Each concern (STT, TTS, AI, commands) is isolated.
- **Command-first routing** — Fast local actions before cloud AI.
- **Dual STT** — Browser Web Speech for web UX; server mic for desktop use.
- **TTS as files** — pyttsx3 writes WAV; Flask serves them for browser playback.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `GEMINI_API_KEY is not set` | Copy `.env.example` → `.env` and add your key |
| Microphone not working | Use Chrome/Edge; allow mic permission |
| PyAudio install fails | Use browser voice button instead |
| Weather not working | Add `OPENWEATHER_API_KEY` to `.env` |
| TTS silent in browser | Check autoplay policy; interact with page first |

## Production Notes

- Set `FLASK_DEBUG=False` and a strong `SECRET_KEY` in production.
- Use **gunicorn** or **waitress** behind nginx instead of `app.run()`.
- Never commit `.env` — it is in `.gitignore`.
- Rotate API keys and rate-limit `/api/chat` if exposed publicly.

## License

MIT — free for learning, portfolios, and personal projects.
