from __future__ import annotations
import os
from pathlib import Path

APP_NAME = "Second Brain"
BASE_DIR = Path(__file__).resolve().parent
MATERI_DIR = BASE_DIR / "materi_kuliah"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "second_brain.log"

# --- Window ---
WINDOW_WIDTH = 720
WINDOW_HEIGHT = 540
WINDOW_ALPHA = 0.97
WINDOW_TOP_OFFSET_RATIO = 0.18
MAX_PROMPT_CHARS = 4000

# --- Hotkey (pynput syntax; <alt> == Option on macOS) ---
HOTKEY_COMBO = os.environ.get("SECOND_BRAIN_HOTKEY", "<alt>+<space>")
DEFAULT_HOTKEY_COMBO = "<alt>+<space>"
HOTKEY_DEBOUNCE_SECONDS = 0.30

# --- RAG ---
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".json"}
MAX_FILE_SIZE_MB = 25
MAX_PDF_PAGES = 400
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
TOP_K_CHUNKS = 4
MAX_CONTEXT_CHARS = 6000
RESCAN_INTERVAL_SECONDS = 30
SCHEDULE_FILE_PREFIXES = ("jadwal", "schedule", "timetable")
SCHEDULE_MAX_CHARS = 2000
ATTACHMENT_MAX_CHARS = 8000

# --- LLM (Ollama) ---
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
OLLAMA_MODEL = "llama3"
OLLAMA_CONNECT_TIMEOUT = 5
OLLAMA_READ_TIMEOUT = 120
OLLAMA_NUM_CTX = 8192
OLLAMA_KEEP_ALIVE = "30m"
MAX_HISTORY_TURNS = 10

# --- Threading / UI bridge ---
UI_POLL_MS = 30
UI_DRAIN_BATCH = 100
DEBUG_THREAD_ASSERTS = os.environ.get("SECOND_BRAIN_DEBUG") == "1"