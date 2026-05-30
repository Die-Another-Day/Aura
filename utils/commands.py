import os
import re
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime
from urllib.parse import quote_plus
# import pyautogui
import requests

# Command patterns: (regex, handler_name)
COMMAND_PATTERNS: list[tuple[str, str]] = [
    (r"\b(open|launch|go to)\s+youtube\b", "open_youtube"),
    (r"\b(open|launch|go to)\s+google\b", "open_google"),
    (r"\b(open|launch|go to)\s+google\b", "open_insta"),
    (r"\b(what('s| is) the )?time\b|\btell me the time\b|\bcurrent time\b", "tell_time"),
    (r"\b(what('s| is) the )?date\b|\btell me the date\b|\btoday('s)? date\b", "tell_date"),
    (r"\bweather\b|\bforecast\b|\btemperature\b", "tell_weather"),
    (r"\b(play|start)\s+(some\s+)?music\b|\bplay music\b", "play_music"),
]

_GENERIC_MUSIC_PHRASES = frozenset({"music", "some music", "a song", "the radio", "something", "anything"})
_BLOCKED_PLAY_TARGETS = frozenset({"youtube", "google", "spotify", "music", "some music", "a song"})

def detect_command(user_text: str) -> str | None:
    text_lower = user_text.lower()
    if re.search(r"\bplay\b", text_lower):
        if _extract_song_name(user_text):
            return "play_song"
        return "play_music"

    for pattern, handler_name in COMMAND_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return handler_name
    return None

def execute_command(handler_name: str, user_text: str) -> dict:
    handlers = {
        "open_youtube": _open_youtube,
        "open_google": _open_google,
        "open_insta": _open_insta_,
        "tell_time": _tell_time,
        "tell_date": _tell_date,
        "tell_weather": _tell_weather,
        "play_music": _play_music,
        "play_song": _play_song,
    }
    handler = handlers.get(handler_name)
    if not handler:
        return {"response": "I don't know how to handle that command.", "action": "error"}
    return handler(user_text)

def _open_youtube(_user_text: str) -> dict:
    return {"response": "Opening YouTube for you.", "action": "open_url", "url": "https://www.youtube.com"}
def _open_insta_(_user_text: str) -> dict:
    return {"response": "Opening YouTube for you.", "action": "open_url", "url": "https://instagram.com"}
def _open_google(_user_text: str) -> dict:
    return {"response": "Opening Google.", "action": "open_url", "url": "https://www.google.com"}

def _tell_time(_user_text: str) -> dict:
    return {"response": f"The current time is {datetime.now().strftime('%I:%M %p')}.", "action": "tell_time"}

def _tell_date(_user_text: str) -> dict:
    return {"response": f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.", "action": "tell_date"}

def _tell_weather(user_text: str) -> dict:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return {"response": "Weather is not configured.", "action": "weather_error"}
    city = _extract_city(user_text) or os.getenv("DEFAULT_CITY", "London")
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        resp = requests.get(url, params={"q": city, "appid": api_key, "units": "metric"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "response": f"Weather in {city}: {data['weather'][0]['description'].capitalize()}, {round(data['main']['temp'])}°C.",
            "action": "tell_weather",
            "city": city,
        }
    except requests.RequestException as exc:
        return {"response": f"Sorry, I couldn't fetch weather for {city}. {exc}", "action": "weather_error"}

def _play_music(_user_text: str) -> dict:
    url = "https://www.youtube.com/results?search_query=relaxing+music"
    return {"response": "Playing music on YouTube.", "action": "play_music", "url": url}

def _extract_song_name(text: str) -> str | None:
    cleaned = text.strip()
    if not cleaned: return None
    patterns = [
        r"(?:can you|could you|please)\s+play(?:\s+the)?\s+song\s+(.+)$",
        r"play(?:\s+the)?\s+song\s+(.+)$",
        r"start(?:\s+the)?\s+song\s+(.+)$",
        r"listen\s+to\s+(.+)$",
        r"play\s+music\s+(.+)$",
        r"(?:can you|could you|please)\s+play\s+(.+)$",
        r"^play\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            song = _clean_song_title(match.group(1))
            if song.lower() not in _GENERIC_MUSIC_PHRASES and song.lower() not in _BLOCKED_PLAY_TARGETS:
                return song
    return None

def _clean_song_title(raw: str) -> str:
    song = raw.strip().strip(".,!?")
    song = re.sub(r"\s+(on youtube|in youtube|on spotify|in spotify|for me|please|now)\s*$", "", song, flags=re.IGNORECASE).strip()
    song = re.sub(r"^(the|a|an)\s+", "", song, flags=re.IGNORECASE).strip()
    return song if len(song) >= 2 else ""

def _detect_platform(text: str):
    text = text.lower()
    if re.search(r"\bon spotify\b|\bspotify\b", text): return "spotify"
    if re.search(r"\bon youtube\b|\byoutube\b", text): return "youtube"
    return "spotify" # Defaults to Spotify

def _is_spotify_installed() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "spotify"):
                return True
        except FileNotFoundError:
            return False
    elif sys.platform == "darwin":
        return os.path.exists("/Applications/Spotify.app")
    return False

def _open_spotify_smart(song: str):
    query = quote_plus(song)
    url = f"https://open.spotify.com/search/{query}"
    
    if _is_spotify_installed():
        spotify_uri = f"spotify:search:{query}"
        
        # 1. Open the Spotify app
        if sys.platform == "win32":
            os.startfile(spotify_uri)
        else:
            webbrowser.open(spotify_uri)
            
        # 2. WAIT 5 SECONDS
        time.sleep(15) 

      
        song = "Blinding Lights"

        query = quote_plus(song)
        spotify_url = f"https://open.spotify.com/search/{query}"

        return {
            "mode": "web",
            "url": spotify_url
        }

        # 3. Simulate pressing Tab and Enter
      #  pyautogui.press('tab')
        # time.sleep(0.5)
        #pyautogui.press('enter')
        
       # return {"mode": "app", "url": spotify_uri}
    
    webbrowser.open(url)
    return {"mode": "web", "url": url}

def _play_youtube_smart(song: str):
    try:
        query = quote_plus(song)
        # Fetch the search page in the background
        html = urllib.request.urlopen(f"https://www.youtube.com/results?search_query={query}")
        video_ids = re.findall(r"watch\?v=(\S{11})", html.read().decode())
        
        if video_ids:
            # Force browser to open the exact first video URL
            video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            webbrowser.open(video_url)
            return {"mode": "direct", "url": video_url}
    except Exception as e:
        print(f"YouTube Error: {e}")

    # Fallback to search if the scrape fails
    fallback_url = f"https://www.youtube.com/results?search_query={quote_plus(song)}"
    webbrowser.open(fallback_url)
    return {"mode": "search", "url": fallback_url}

def _play_song(user_text: str) -> dict:
    song = _extract_song_name(user_text)
    if not song: 
        return _play_music(user_text)

    platform = _detect_platform(user_text)

    # -------- SPOTIFY --------
    if platform == "spotify":
        result = _open_spotify_smart(song)
        return {
            "response": f"Playing {song} on Spotify.",
            "action": "play_spotify",
            "mode": result["mode"],
            "url": result.get("url"),
            "song": song,
        }

    # -------- YOUTUBE --------
    result = _play_youtube_smart(song)
    return {
        "response": f"Playing {song} on YouTube.",
        "action": "play_song",
        "mode": result["mode"],
        "url": result.get("url"),
        "song": song,
    }

def _extract_city(text: str) -> str | None:
    patterns = [r"weather in ([a-zA-Z\s]+)", r"forecast for ([a-zA-Z\s]+)", r"temperature in ([a-zA-Z\s]+)"]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match: return match.group(1).strip().title()
    return None

# """
# Voice command handlers.

# Detects intent from user text and runs local actions (open URLs, time, weather, etc.)
# before falling back to Gemini AI for general conversation.
# """

# import os
# import re
# from datetime import datetime
# from urllib.parse import quote_plus
# import webbrowser
# import requests

# # Command patterns: (regex, handler_name)
# COMMAND_PATTERNS: list[tuple[str, str]] = [
#     (r"\b(open|launch|go to)\s+youtube\b", "open_youtube"),
#     (r"\b(open|launch|go to)\s+google\b", "open_google"),
#     (r"\b(what('s| is) the )?time\b|\btell me the time\b|\bcurrent time\b", "tell_time"),
#     (r"\b(what('s| is) the )?date\b|\btell me the date\b|\btoday('s)? date\b", "tell_date"),
#     (r"\bweather\b|\bforecast\b|\btemperature\b", "tell_weather"),
#     (r"\b(play|start)\s+(some\s+)?music\b|\bplay music\b", "play_music"),
# ]

# # Phrases that mean "generic music", not a specific song title
# _GENERIC_MUSIC_PHRASES = frozenset(
#     {
#         "music",
#         "some music",
#         "a song",
#         "the radio",
#         "something",
#         "anything",
#     }
# )

# # Not song titles — sites or generic commands
# _BLOCKED_PLAY_TARGETS = frozenset(
#     {"youtube", "google", "spotify", "music", "some music", "a song"}
# )


# # def detect_command(user_text: str) -> str | None:
# #     """
# #     Check if user text matches a built-in command.

# #     Returns:
# #         Handler name string, or None if no command matched.
# #     """
# #     text = user_text.strip()
# #     # Named song (e.g. "play Blinding Lights") — checked before generic play music
# #     if _extract_song_name(text):
# #         return "play_song"

# #     text_lower = text.lower()
# #     for pattern, handler_name in COMMAND_PATTERNS:
# #         if re.search(pattern, text_lower, re.IGNORECASE):
# #             return handler_name
# #     return None

# def detect_command(user_text: str) -> str | None:
#     text_lower = user_text.lower()

#     # 1. music command detection FIRST (but safer)
#     if re.search(r"\bplay\b", text_lower):
#         if _extract_song_name(user_text):
#             return "play_song"
#         return "play_music"

#     # 2. other commands
#     for pattern, handler_name in COMMAND_PATTERNS:
#         if re.search(pattern, text_lower, re.IGNORECASE):
#             return handler_name

#     return None
# def execute_command(handler_name: str, user_text: str) -> dict:
#     """
#     Run the matched command handler.

#     Returns:
#         JSON-serializable dict with keys: response, action, url (optional).
#     """
#     handlers = {
#         "open_youtube": _open_youtube,
#         "open_google": _open_google,
#         "tell_time": _tell_time,
#         "tell_date": _tell_date,
#         "tell_weather": _tell_weather,
#         "play_music": _play_music,
#         "play_song": _play_song,
#     }
#     handler = handlers.get(handler_name)
#     if not handler:
#         return {
#             "response": "I don't know how to handle that command.",
#             "action": "error",
#         }
#     return handler(user_text)


# def _open_youtube(_user_text: str) -> dict:
#     """Return YouTube URL for the client to open (no server-side browser)."""
#     url = "https://www.youtube.com"
#     return {
#         "response": "Opening YouTube for you.",
#         "action": "open_url",
#         "url": url,
#     }


# def _open_google(_user_text: str) -> dict:
#     """Return Google URL for the client to open."""
#     url = "https://www.google.com"
#     return {
#         "response": "Opening Google.",
#         "action": "open_url",
#         "url": url,
#     }


# def _tell_time(_user_text: str) -> dict:
#     """Return the current local time."""
#     now = datetime.now()
#     time_str = now.strftime("%I:%M %p")
#     return {
#         "response": f"The current time is {time_str}.",
#         "action": "tell_time",
#     }


# def _tell_date(_user_text: str) -> dict:
#     """Return today's date."""
#     now = datetime.now()
#     date_str = now.strftime("%A, %B %d, %Y")
#     return {
#         "response": f"Today is {date_str}.",
#         "action": "tell_date",
#     }


# def _tell_weather(user_text: str) -> dict:
#     """
#     Fetch weather from OpenWeatherMap API.

#     Requires OPENWEATHER_API_KEY and optionally DEFAULT_CITY in .env.
#     City can be extracted from phrases like "weather in Paris".
#     """
#     api_key = os.getenv("OPENWEATHER_API_KEY")
#     if not api_key:
#         return {
#             "response": (
#                 "Weather is not configured. Add OPENWEATHER_API_KEY to your .env file. "
#                 "Get a free key at https://openweathermap.org/api"
#             ),
#             "action": "weather_error",
#         }

#     city = _extract_city(user_text) or os.getenv("DEFAULT_CITY", "London")
#     try:
#         url = "https://api.openweathermap.org/data/2.5/weather"
#         params = {"q": city, "appid": api_key, "units": "metric"}
#         resp = requests.get(url, params=params, timeout=10)
#         resp.raise_for_status()
#         data = resp.json()
#         temp = round(data["main"]["temp"])
#         desc = data["weather"][0]["description"].capitalize()
#         humidity = data["main"]["humidity"]
#         return {
#             "response": (
#                 f"Weather in {city}: {desc}, {temp}°C, humidity {humidity}%."
#             ),
#             "action": "tell_weather",
#             "city": city,
#         }
#     except requests.RequestException as exc:
#         return {
#             "response": f"Sorry, I couldn't fetch weather for {city}. {exc}",
#             "action": "weather_error",
#         }

# def _play_music(_user_text: str) -> dict:

#     """Return YouTube search URL for generic music (client opens tab)."""
#     url = "https://www.youtube.com/results?search_query=relaxing+music"
#     return {
#         "response": "Playing music on YouTube.",
#         "action": "play_music",
#         "url": url,
#     }


# def _extract_song_name(text: str) -> str | None:
#     """
#     Parse a song title from phrases like:
#       - play song Blinding Lights
#       - can you play Despacito
#       - play Shape of You on YouTube
#     """
#     cleaned = text.strip()
#     if not cleaned:
#         return None

#     patterns = [
#         r"(?:can you|could you|please)\s+play(?:\s+the)?\s+song\s+(.+)$",
#         r"play(?:\s+the)?\s+song\s+(.+)$",
#         r"start(?:\s+the)?\s+song\s+(.+)$",
#         r"listen\s+to\s+(.+)$",
#         r"play\s+music\s+(.+)$",
#         r"(?:can you|could you|please)\s+play\s+(.+)$",
#         r"^play\s+(.+)$",
#     ]

#     for pattern in patterns:
#         match = re.search(pattern, cleaned, re.IGNORECASE)
#         if not match:
#             continue
#         song = _clean_song_title(match.group(1))
#         low = song.lower()
#         if low not in _GENERIC_MUSIC_PHRASES and low not in _BLOCKED_PLAY_TARGETS:
#             return song
#     return None


# def _clean_song_title(raw: str) -> str:
#     """Remove trailing filler words from extracted song text."""
#     song = raw.strip().strip(".,!?")
#     song = re.sub(
#         r"\s+(on youtube|in youtube|for me|please|now)\s*$",
#         "",
#         song,
#         flags=re.IGNORECASE,
#     ).strip()
#     # Drop leading articles only when the rest is long enough
#     song = re.sub(r"^(the|a|an)\s+", "", song, flags=re.IGNORECASE).strip()
#     return song if len(song) >= 2 else ""


# def _youtube_search_url(song: str) -> str:
#     """Build YouTube search URL (top result is usually the official track)."""
#     query = quote_plus(f"{song} official song")
#     return f"https://www.youtube.com/results?search_query={query}"


# # def _play_song(user_text: str) -> dict:
# #     """Search YouTube for the requested song and open results in the browser."""
# #     song = _extract_song_name(user_text)
# #     if not song:
# #         return _play_music(user_text)

# #     url = _youtube_search_url(song)
# #     return {
# #         "response": f"Playing {song} on YouTube. Pick the top result in the new tab.",
# #         "action": "play_song",
# #         "url": url,
# #         "song": song,
# #     }

# def _detect_platform(text: str):
#     text = text.lower()

#     if re.search(r"\bon spotify\b|\bspotify\b", text):
#         return "spotify"
#     if re.search(r"\bon youtube\b|\byoutube\b", text):
#         return "youtube"

#     return "spotify"   # default platform (you can change to spotify if you want)

# def _open_spotify_smart(song: str):
#     """
#     Try opening Spotify desktop app first.
#     If it fails → fallback to web browser.
#     """

#     query = quote_plus(song)

#     # 1. Try Spotify desktop app (Windows only)
   

#  # 2. Fallback → Web version
#     url = f"https://open.spotify.com/search/{query}"
#     webbrowser.open(url)

#     return {
#         "mode": "web",
#         "url": url
#     }
# def _play_song(user_text: str) -> dict:
#     song = _extract_song_name(user_text)

#     if not song:
#         return _play_music(user_text)

#     platform = _detect_platform(user_text)

#     # -------- SPOTIFY --------
#     if platform == "spotify":
#         result = _open_spotify_smart(song)
#         return {
#             "response": f"Playing {song} on Spotify.",
#             "action": "play_spotify",
#             "mode": result["mode"],
#             "url": result.get("url"),
#             "song": song,
#         }

#     # -------- YOUTUBE (default) --------
#     url = _youtube_search_url(song)

#     return {
#         "response": f"Playing {song} on YouTube.",
#         "action": "play_song",
#         "url": url,
#         "song": song,
#     }

# def _extract_city(text: str) -> str | None:
#     """Parse city from phrases like 'weather in Mumbai' or 'forecast for Tokyo'."""
#     patterns = [
#         r"weather in ([a-zA-Z\s]+)",
#         r"forecast for ([a-zA-Z\s]+)",
#         r"temperature in ([a-zA-Z\s]+)",
#     ]
#     for pattern in patterns:
#         match = re.search(pattern, text, re.IGNORECASE)
#         if match:
#             return match.group(1).strip().title()
#     return None
