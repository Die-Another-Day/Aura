/**
 * AURA AI Voice Assistant — Frontend logic
 *
 * Features:
 *  - Chat UI with typing effect
 *  - Browser Web Speech API + server STT fallback
 *  - Chat history (localStorage + optional server sync)
 *  - TTS playback from server-generated audio
 *  - Error handling & loading states
 */

const API = {
  health: "/api/health",
  chat: "/api/chat",
  listen: "/api/listen",
  transcribe: "/api/transcribe",
  speak: "/api/speak",
  history: "/api/history",
};

const STORAGE_KEY = "aura_chat_history";

// DOM elements
const chatContainer = document.getElementById("chatContainer");
const welcomeMessage = document.getElementById("welcomeMessage");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");
const stopSpeechBtn = document.getElementById("stopSpeechBtn");
const clearChatBtn = document.getElementById("clearChatBtn");
const loader = document.getElementById("loader");
const statusBadge = document.getElementById("statusBadge");
const statusText = document.getElementById("statusText");
const toastContainer = document.getElementById("toastContainer");

// State
let chatHistory = [];
let isProcessing = false;
/** @type {SpeechRecognition | null} One-shot instance per mic press (Chrome breaks reuse). */
let activeRecognition = null;
/** @type {MediaStream | null} Released after each voice session. */
let activeMicStream = null;
let isListening = false;
/** Blocks double-tap while a voice session is starting or active. */
let voiceBusy = false;
/** Cancels an in-flight getUserMedia if the user taps mic again. */
let micRequestAbort = null;
/** @type {HTMLAudioElement | null} Current assistant voice playback. */
let currentTtsAudio = null;
let isSpeaking = false;
/** Set true to skip remaining typing animation chars. */
let skipTyping = false;

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  loadHistory();
  checkHealth();
  bindEvents();
  hintVoiceSupport();
});

function bindEvents() {
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (text) sendMessage(text);
  });

  micBtn.addEventListener("click", toggleVoiceInput);
  if (stopSpeechBtn) {
    stopSpeechBtn.addEventListener("click", () => {
      stopSpeaking();
      showToast("Speech stopped.", "info");
    });
  }
  clearChatBtn.addEventListener("click", clearChat);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (isSpeaking) stopSpeaking();
      else if (isListening || voiceBusy) stopBrowserVoice();
      else if (isProcessing) skipTyping = true;
    }
  });
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.success === false) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}

async function checkHealth() {
  try {
    const data = await apiRequest(API.health);
    statusBadge.classList.add("status-badge--online");
    statusText.textContent = data.gemini_configured ? "Online" : "Fix API key";
    if (!data.gemini_configured) {
      const hint =
        data.gemini_setup_hint ||
        "Add a real GEMINI_API_KEY to .env from https://aistudio.google.com/apikey";
      showToast(hint, "error");
    }
  } catch {
    statusBadge.classList.add("status-badge--offline");
    statusText.textContent = "Offline";
    showToast("Cannot reach server. Is Flask running?", "error");
  }
}

// ---------------------------------------------------------------------------
// Chat flow
// ---------------------------------------------------------------------------

async function sendMessage(text, options = {}) {
  if (isProcessing || !text.trim()) return;

  stopSpeaking();
  isProcessing = true;
  setLoading(true);
  setInputsDisabled(true);
  hideWelcome();

  appendMessage("user", text);
  messageInput.value = "";

  // Prior turns only — the current message is sent as `message` (avoids duplicate with Gemini)
  const priorHistory = chatHistory.filter(
    (m) => m.role === "user" || m.role === "assistant"
  );

  chatHistory.push({ role: "user", content: text, timestamp: Date.now() });
  saveHistory();

  try {
    const data = await apiRequest(API.chat, {
      method: "POST",
      body: JSON.stringify({
        message: text,
        history: priorHistory,
        speak: options.speak !== false,
      }),
    });

    const responseText = data.response || "No response.";
    const meta =
      data.source === "command"
        ? `Command · ${data.action || ""}`
        : "Gemini AI";

    skipTyping = false;
    await appendMessageWithTyping("assistant", responseText, meta);

    chatHistory.push({
      role: "assistant",
      content: responseText,
      timestamp: Date.now(),
      source: data.source,
    });
    saveHistory();

    if (data.audio_url) {
      playAudio(data.audio_url);
    }

    if (
      data.url &&
      (data.action === "open_url" ||
        data.action === "play_music" ||
        data.action === "play_song")
    ) {
      window.open(data.url, "_blank");
    }
  } catch (err) {
    showToast(err.message, "error");
    appendMessage("assistant", `Sorry, something went wrong: ${err.message}`);
  } finally {
    isProcessing = false;
    setLoading(false);
    setInputsDisabled(false);
  }
}

// ---------------------------------------------------------------------------
// UI: Messages
// ---------------------------------------------------------------------------

function hideWelcome() {
  if (welcomeMessage) welcomeMessage.classList.add("hidden");
}

function appendMessage(role, content, meta = "") {
  const el = createMessageElement(role, content, meta);
  chatContainer.appendChild(el);
  scrollToBottom();
  return el;
}

async function appendMessageWithTyping(role, fullText, meta = "") {
  const el = createMessageElement(role, "", meta);
  const bubble = el.querySelector(".bubble");
  bubble.classList.add("typing-cursor");
  chatContainer.appendChild(el);
  scrollToBottom();

  // Long replies: show text at once so you can read while optionally hearing shorter TTS
  if (fullText.length > 400) {
    bubble.textContent = fullText;
    scrollToBottom();
  } else {
    const delay = Math.max(12, Math.min(30, 2000 / Math.max(fullText.length, 1)));
    for (let i = 0; i < fullText.length; i++) {
      if (skipTyping) {
        bubble.textContent = fullText;
        break;
      }
      bubble.textContent = fullText.slice(0, i + 1);
      if (i % 3 === 0) scrollToBottom();
      await sleep(delay);
    }
  }
  skipTyping = false;

  bubble.classList.remove("typing-cursor");

  if (meta) {
    const metaEl = document.createElement("div");
    metaEl.className =
      "bubble__meta" +
      (meta.startsWith("Command") ? " bubble__meta--command" : "");
    metaEl.textContent = meta;
    bubble.appendChild(metaEl);
  }
}

function createMessageElement(role, content, meta = "") {
  const wrapper = document.createElement("div");
  wrapper.className = `message message--${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;

  if (meta && content) {
    const metaEl = document.createElement("div");
    metaEl.className = "bubble__meta";
    metaEl.textContent = meta;
    bubble.appendChild(document.createElement("br"));
    bubble.appendChild(metaEl);
  }

  wrapper.appendChild(bubble);
  return wrapper;
}

function renderHistory() {
  chatContainer.querySelectorAll(".message").forEach((el) => el.remove());
  if (chatHistory.length === 0) {
    if (welcomeMessage) welcomeMessage.classList.remove("hidden");
    return;
  }
  hideWelcome();
  chatHistory.forEach((msg) => {
    const meta =
      msg.source === "command" ? "Command" : msg.source === "gemini" ? "Gemini AI" : "";
    appendMessage(msg.role, msg.content, meta);
  });
}

function clearChat() {
  stopSpeaking();
  chatHistory = [];
  localStorage.removeItem(STORAGE_KEY);
  chatContainer.querySelectorAll(".message").forEach((el) => el.remove());
  if (welcomeMessage) welcomeMessage.classList.remove("hidden");
  apiRequest(API.history, {
    method: "POST",
    body: JSON.stringify({ history: [] }),
  }).catch(() => {});
  showToast("Chat cleared.", "info");
}

// ---------------------------------------------------------------------------
// History persistence
// ---------------------------------------------------------------------------

function loadHistory() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      chatHistory = JSON.parse(stored);
      renderHistory();
    }
  } catch {
    chatHistory = [];
  }

  // Optional server sync
  apiRequest(API.history)
    .then((data) => {
      if (data.history?.length && chatHistory.length === 0) {
        chatHistory = data.history;
        renderHistory();
        localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
      }
    })
    .catch(() => {});
}

function saveHistory() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
  apiRequest(API.history, {
    method: "POST",
    body: JSON.stringify({ history: chatHistory }),
  }).catch(() => {});
}

// ---------------------------------------------------------------------------
// Voice input (Web Speech API)
// ---------------------------------------------------------------------------

function hintVoiceSupport() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR && micBtn) {
    micBtn.title =
      "Voice recognition needs Chrome or Edge. Or use text input.";
  }
}

function releaseMicStream() {
  if (activeMicStream) {
    activeMicStream.getTracks().forEach((t) => t.stop());
    activeMicStream = null;
  }
}

function stopBrowserVoice() {
  if (micRequestAbort) {
    try {
      micRequestAbort.abort();
    } catch {
      /* ignore */
    }
    micRequestAbort = null;
  }
  if (activeRecognition) {
    try {
      activeRecognition.abort();
    } catch {
      try {
        activeRecognition.stop();
      } catch {
        /* ignore */
      }
    }
    activeRecognition = null;
  }
  releaseMicStream();
  isListening = false;
  voiceBusy = false;
  micBtn.classList.remove("mic-btn--active");
  micBtn.setAttribute("aria-pressed", "false");
}

/**
 * Start browser speech recognition (Chrome / Edge / Safari where supported).
 * Uses a fresh SpeechRecognition each time — reusing one instance often breaks on Chrome.
 */
async function startBrowserVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    showToast(
      "This browser has no voice recognition. Use Chrome or Edge, or type your message.",
      "error"
    );
    await serverListen();
    return;
  }

  if (!window.isSecureContext) {
    showToast(
      "Voice needs a secure page. Open http://127.0.0.1:5000 (not an IP URL unless HTTPS).",
      "error"
    );
    return;
  }

  if (voiceBusy || isListening) return;
  voiceBusy = true;

  micRequestAbort = new AbortController();
  try {
    activeMicStream = await navigator.mediaDevices.getUserMedia({
      audio: true,
      signal: micRequestAbort.signal,
    });
  } catch (err) {
    micRequestAbort = null;
    voiceBusy = false;
    if (err.name === "AbortError") {
      return;
    }
    showToast(
      "Microphone permission denied or unavailable. Allow mic in the address bar.",
      "error"
    );
    return;
  }
  micRequestAbort = null;

  let committed = false;
  let lastTranscript = "";

  const rec = new SR();
  rec.continuous = false;
  rec.interimResults = true;
  rec.lang = (navigator.language || "en-US").replace("_", "-");

  rec.onstart = () => {
    isListening = true;
    micBtn.classList.add("mic-btn--active");
    micBtn.setAttribute("aria-pressed", "true");
    showToast("Listening… (voice recognition uses the internet)", "info");
  };

  rec.onresult = (event) => {
    lastTranscript = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      lastTranscript += event.results[i][0].transcript;
    }
    messageInput.value = lastTranscript;

    const last = event.results[event.results.length - 1];
    if (last.isFinal && !committed) {
      committed = true;
      const text = lastTranscript.trim();
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
      if (text) sendMessage(text);
    }
  };

  rec.onerror = (event) => {
    const err = event.error;
    if (err === "aborted") {
      activeRecognition = null;
      releaseMicStream();
      isListening = false;
      voiceBusy = false;
      micBtn.classList.remove("mic-btn--active");
      micBtn.setAttribute("aria-pressed", "false");
      return;
    }
    const hints = {
      "not-allowed":
        "Microphone blocked. Click the lock icon in the address bar and allow the mic.",
      "no-speech": "No speech heard. Try again and speak a bit louder.",
      "network":
        "Browser speech could not reach Google (try another Wi‑Fi, disable VPN, or allow Chrome past firewall). You can still type messages.",
      "audio-capture": "No microphone found. Plug in a mic and try again.",
    };
    showToast(hints[err] || `Voice error: ${err}`, "error");
    stopBrowserVoice();
  };

  rec.onend = () => {
    activeRecognition = null;
    isListening = false;
    micBtn.classList.remove("mic-btn--active");
    micBtn.setAttribute("aria-pressed", "false");
    releaseMicStream();
    voiceBusy = false;

    // Chrome often ends without isFinal; still send the last interim text.
    if (!committed) {
      const text = (lastTranscript || messageInput.value || "").trim();
      if (text) {
        committed = true;
        sendMessage(text);
      }
    }
  };

  activeRecognition = rec;
  try {
    rec.start();
  } catch (err) {
    voiceBusy = false;
    showToast(`Could not start voice: ${err.message || err}`, "error");
    stopBrowserVoice();
  }
}

function toggleVoiceInput() {
  // Stop assistant voice first so the mic is not fighting speaker output
  if (isSpeaking) {
    stopSpeaking();
  }

  if (isProcessing) {
    showToast("Wait for the reply to finish generating, or press Esc.", "info");
    return;
  }

  // Cancel listening or an in-flight mic permission request
  if (isListening || voiceBusy || activeRecognition) {
    stopBrowserVoice();
    return;
  }

  startBrowserVoice();
}

async function serverListen() {
  setLoading(true);
  micBtn.classList.add("mic-btn--active");
  showToast("Listening on server microphone...", "info");

  try {
    const data = await apiRequest(API.listen, {
      method: "POST",
      body: JSON.stringify({ timeout: 8, phrase_limit: 12 }),
    });
    if (data.text) {
      messageInput.value = data.text;
      await sendMessage(data.text);
    }
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    setLoading(false);
    micBtn.classList.remove("mic-btn--active");
  }
}

// ---------------------------------------------------------------------------
// Audio playback (TTS) — stoppable so you can use the mic again
// ---------------------------------------------------------------------------

function updateSpeechUi() {
  if (!stopSpeechBtn) return;
  stopSpeechBtn.classList.toggle("hidden", !isSpeaking);
  if (micBtn) {
    micBtn.title = isSpeaking
      ? "Stop speech & listen (tap)"
      : "Voice input";
  }
}

function stopSpeaking() {
  skipTyping = true;
  if (currentTtsAudio) {
    currentTtsAudio.pause();
    currentTtsAudio.currentTime = 0;
    currentTtsAudio.src = "";
    currentTtsAudio = null;
  }
  isSpeaking = false;
  updateSpeechUi();
}

function playAudio(url) {
  stopSpeaking();
  const audio = new Audio(url);
  currentTtsAudio = audio;
  isSpeaking = true;
  updateSpeechUi();

  audio.onended = () => {
    if (currentTtsAudio === audio) {
      currentTtsAudio = null;
      isSpeaking = false;
      updateSpeechUi();
    }
  };
  audio.onerror = () => {
    isSpeaking = false;
    updateSpeechUi();
  };

  audio.play().catch(() => {
    isSpeaking = false;
    updateSpeechUi();
    showToast("Could not play audio. Click to allow sound.", "info");
  });
}

// ---------------------------------------------------------------------------
// UI utilities
// ---------------------------------------------------------------------------

function setLoading(show) {
  loader.classList.toggle("hidden", !show);
}

function setInputsDisabled(disabled) {
  messageInput.disabled = disabled;
  sendBtn.disabled = disabled;
  micBtn.disabled = disabled;
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
