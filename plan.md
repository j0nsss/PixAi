# plan.md: Desktop "Second Brain" AI Assistant

> **Audience:** autonomous AI coding agent (Cursor / Windsurf / Aider).
> **Goal:** build a local, cross-platform (Windows + macOS) floating-overlay AI assistant for student productivity: study-material retrieval (RAG), schedule help, and multi-turn chat. The LLM is local Ollama (`llama3`).

---

## 0. Agent Execution Protocol (read first)

1. Work **phase by phase, task by task, in order**. Do not start a phase until every box in the previous phase is ticked.
2. After each task, run its **Validate** step. If it fails, fix it before moving on. Then tick the box (`- [x]`) and commit with the message `phase-X.Y: <title>`.
3. If a requirement is ambiguous, choose the simplest option stated in this plan. Record the choice in `README.md` under a "Decisions" heading.
4. Do not add dependencies beyond those in Task 1.2. Do not add features beyond this plan.

### Global Engineering Rules (apply to every file)

- **Python 3.10+**. Use `from __future__ import annotations`, full type hints, and a one-line docstring on every public class and function.
- **No magic numbers or strings.** Every tunable lives in `config.py` (Task 1.3).
- **Use `logging`, never `print`.** The only exceptions are the `__main__` smoke-test CLIs.
- **Threading law (critical):**
  - Only the **main thread** may touch Tk or customtkinter objects. This includes `.after()`, `.configure()`, `.insert()`, `.deiconify()` and every other widget call.
  - Worker threads (LLM streaming, file parsing, RAG scanning) and the `pynput` listener thread must never touch widgets. They send work to the main thread only through `UiBridge.post(fn, *args)` (Task 3.1).
  - `UiBridge` is a `queue.Queue` drained by a main-thread `app.after()` polling loop. This is the macOS-safe form of `app.after()`.
- **Never block the main thread** for more than about 50 ms. No network calls, PDF parsing, disk scans or `time.sleep` on the main thread.
- **Dependency direction:**
  - `core/*` and `utils/*` must never import from `ui/*`.
  - `ui/*` may import only `config`, `utils.*` and `core.platform_utils`.
  - `core/controller.py` is the **only** module that imports both `ui` and `core` services.
- **Error contract:**
  - Parsing functions never raise for expected failures. They return a `ParseResult`.
  - LLM functions raise typed exceptions (Task 5.2).
  - All errors reaching the user must be human-readable status or notice text. A raw traceback must never appear in the UI.

---

## 1. Target Directory Structure (final state)

```
second-brain/
├── main.py                      # entry point: logging, arg parsing, wiring, mainloop
├── config.py                    # ALL constants/tunables
├── requirements.txt
├── pytest.ini
├── README.md
├── .gitignore
├── materi_kuliah/               # user's study materials (RAG corpus) + optional jadwal.md
│   └── .gitkeep
├── logs/
│   └── .gitkeep
├── core/
│   ├── __init__.py
│   ├── platform_utils.py        # OS flags, frameless/focus helpers, macOS accessibility check
│   ├── hotkey_manager.py        # pynput GlobalHotKeys wrapper (debounced, thread-safe)
│   ├── file_parser.py           # PDF/TXT/MD/JSON -> text (never raises)
│   ├── rag_engine.py            # background scanner, chunker, BM25 retrieval, context builder
│   ├── chat_memory.py           # multi-turn history + reset
│   ├── prompt_builder.py        # system prompt + per-turn user message assembly
│   ├── llm_client.py            # Ollama streaming client + typed exceptions + health check
│   └── controller.py            # glue: UI <-> RAG <-> LLM <-> hotkey (only module importing both sides)
├── ui/
│   ├── __init__.py
│   ├── theme.py                 # colors, fonts, appearance mode
│   ├── main_window.py           # MainWindow(CTk), UiActions, show/hide/toggle, top bar
│   ├── chat_view.py             # read-only streaming transcript
│   └── input_bar.py             # entry, send/attach buttons, attachment chip
├── utils/
│   ├── __init__.py
│   ├── logger.py                # rotating file + console logging
│   └── threading_utils.py       # UiBridge, assert_main_thread
└── tests/
    ├── __init__.py
    ├── fixtures/
    │   └── .gitkeep
    ├── test_file_parser.py
    ├── test_rag_engine.py
    ├── test_chat_memory.py
    ├── test_prompt_builder.py
    ├── test_llm_client.py
    └── manual_qa_checklist.md
```

---

## Phase 1: Environment Setup & Project Boilerplate

- [ ] **1.1 Create the project skeleton**
  - **Files:** every path in the tree above.
  - **Instructions:**
    - Create all directories and files.
    - `__init__.py` and `.gitkeep` files are empty.
    - Other files may be stubs containing only a module docstring for now.
    - `.gitignore` must contain: `.venv/`, `__pycache__/`, `*.pyc`, `logs/*.log*`, `materi_kuliah/*`, `!materi_kuliah/.gitkeep`, `.pytest_cache/`, `build/`, `dist/`, `*.spec`.
    - `pytest.ini` contains `[pytest]`, `pythonpath = .`, `testpaths = tests`.
  - **Validate:** `find . -not -path "./.venv/*" -type f` (or `tree`) matches the structure in section 1.

- [ ] **1.2 Virtual environment and dependencies**
  - **Files:** `requirements.txt`
  - **Instructions:** write exactly:
```
    customtkinter>=5.2.2
    pynput>=1.7.7
    pypdf>=4.0.0
    requests>=2.31.0
    pytest>=8.0.0
```
    Then run:
```
    python3 -m venv .venv
    # Windows: .venv\Scripts\activate    macOS: source .venv/bin/activate
    pip install -r requirements.txt
```
  - **Validate:**
    - `python -c "import customtkinter, pynput, pypdf, requests; print('ok')"` prints `ok`.
    - `python -c "import tkinter; print(tkinter.TkVersion)"` prints `8.6` or higher.
    - **macOS note:** if the Tk version is 8.5, document in the README that the user must install Python 3.10+ from python.org (or `brew install python-tk`). Apple's system Tk 8.5 breaks customtkinter.

- [ ] **1.3 Central configuration**
  - **Files:** `config.py`
  - **Instructions:** implement this file verbatim. Add constants later only if a task requires them.
```python
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
    WINDOW_TOP_OFFSET_RATIO = 0.18      # window top edge = screen_height * ratio
    MAX_PROMPT_CHARS = 4000

    # --- Hotkey (pynput syntax; <alt> == Option on macOS) ---
    HOTKEY_COMBO = os.environ.get("SECOND_BRAIN_HOTKEY", "<alt>+<space>")
    DEFAULT_HOTKEY_COMBO = "<alt>+<space>"
    HOTKEY_DEBOUNCE_SECONDS = 0.30

    # --- RAG ---
    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".json"}
    MAX_FILE_SIZE_MB = 25
    MAX_PDF_PAGES = 400
    CHUNK_SIZE = 1000                   # characters
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
    OLLAMA_CONNECT_TIMEOUT = 5          # seconds
    OLLAMA_READ_TIMEOUT = 120           # seconds between streamed chunks (cold model load can be slow)
    OLLAMA_NUM_CTX = 8192
    OLLAMA_KEEP_ALIVE = "30m"
    MAX_HISTORY_TURNS = 10              # 1 turn = 1 user + 1 assistant message

    # --- Threading / UI bridge ---
    UI_POLL_MS = 30
    UI_DRAIN_BATCH = 100
    DEBUG_THREAD_ASSERTS = os.environ.get("SECOND_BRAIN_DEBUG") == "1"
```
  - **Validate:** `python -c "import config; print(config.MATERI_DIR)"` prints an absolute path ending in `materi_kuliah`.

- [ ] **1.4 Logging utility**
  - **Files:** `utils/logger.py`
  - **Instructions:**
    - Implement `setup_logging(debug: bool = False) -> None` and `get_logger(name: str) -> logging.Logger`.
    - `setup_logging` creates `LOG_DIR` if missing.
    - It attaches a `RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")` and a console `StreamHandler`.
    - Format: `%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s`. Level is `DEBUG` if `debug`, else `INFO`.
    - It must be idempotent: calling it twice must not duplicate handlers.
  - **Validate:** call `setup_logging(); get_logger("x").info("hi")`. The line appears in the console and in `logs/second_brain.log`, and a second `setup_logging()` call does not double the output.

- [ ] **1.5 Platform detection constants**
  - **Files:** `core/platform_utils.py`
  - **Instructions:** define the constants below. Functions are added in Tasks 2.8 and 3.3.
```python
    IS_WINDOWS = sys.platform.startswith("win")
    IS_MACOS = sys.platform == "darwin"
    MOD_KEY = "Command" if IS_MACOS else "Control"      # Tk modifier name for key bindings
    MOD_LABEL = "⌘" if IS_MACOS else "Ctrl"
    HOTKEY_LABEL = "Option+Space" if IS_MACOS else "Alt+Space"
```
  - **Validate:** import it and print the constants on the current OS. Exactly one of `IS_WINDOWS` / `IS_MACOS` is `True` on Windows or macOS.

- [ ] **1.6 `main.py` boot skeleton**
  - **Files:** `main.py`
  - **Instructions:**
    - At the top of `main()`, verify `sys.version_info >= (3, 10)`. Otherwise print a clear message to stderr and `sys.exit(1)`.
    - Parse CLI args with `argparse`: `--show` (show the window on startup) and `--debug`.
    - Call `setup_logging(args.debug)`.
    - Log `"Second Brain starting on <platform>"`.
    - Guard with `if __name__ == "__main__": main()`.
    - Do not build any UI yet.
  - **Validate:** `python main.py --debug` logs the start line and exits cleanly.

- [ ] **1.7 README with prerequisites**
  - **Files:** `README.md`
  - **Instructions:** document these sections:
    - **Install Ollama.** Run `ollama pull llama3`, then confirm with `ollama list`.
    - **Install the project.** Python 3.10+, venv, `pip install -r requirements.txt`.
    - **Run the app.** `python main.py`.
    - **Hotkey.** Alt+Space on Windows, Option+Space on macOS. It can be overridden with the `SECOND_BRAIN_HOTKEY` env var, for example `"<ctrl>+<shift>+<space>"`.
    - **macOS permissions.** Grant Accessibility and Input Monitoring to the terminal or IDE that launches Python.
    - **Materials.** Put files in `./materi_kuliah/`. An optional `jadwal.md` / `schedule.md` / `timetable.*` file is injected into every prompt as the schedule source.
    - **Known conflicts.** PowerToys Run (Alt+Space), Alfred, Raycast, and Windows' native window menu.
    - **Decisions.** An empty section for now.
  - **Validate:** a human can follow the README from a clean machine.

---

## Phase 2: Core UI Components & Window Management

- [ ] **2.1 Theme module**
  - **Files:** `ui/theme.py`
  - **Instructions:**
    - Define the color constants `BG="#1e1e2e"`, `SURFACE="#2a2a3c"`, `SURFACE_ALT="#34344a"`, `ACCENT="#7aa2f7"`, `TEXT="#e6e6f0"`, `MUTED="#8b8ba7"`, `ERROR="#f7768e"`, `WARN="#e0af68"`, `SUCCESS="#9ece6a"`.
    - Define `FONT_FAMILY` as `"Segoe UI"` on Windows, `"Helvetica Neue"` on macOS, and `"Arial"` otherwise.
    - Define `FONT_BODY=(FONT_FAMILY, 13)`, `FONT_SMALL=(FONT_FAMILY, 11)` and `FONT_TITLE=(FONT_FAMILY, 14, "bold")`.
    - Define `STATUS_COLORS = {"info": MUTED, "ok": SUCCESS, "warn": WARN, "error": ERROR, "busy": ACCENT}`.
    - Implement `apply_theme()`, which calls `ctk.set_appearance_mode("dark")` and `ctk.set_default_color_theme("dark-blue")`.
  - **Validate:** importing the module has no side effects, and `apply_theme()` runs without error.

- [ ] **2.2 `MainWindow`: frameless, always-on-top shell**
  - **Files:** `ui/main_window.py`
  - **Instructions:**
    - Implement `class MainWindow(ctk.CTk)`.
    - Define `@dataclass class UiActions` with callable fields, each defaulting to a no-op lambda: `on_submit(text: str)`, `on_attach()`, `on_remove_attachment()`, `on_reset()`, `on_quit()`.
    - `MainWindow.__init__(self, start_hidden: bool = True)`:
      - Call `super().__init__()`, then immediately `self.withdraw()`.
      - Call `apply_theme()` and `self.title(APP_NAME)`.
      - Call `self.configure(fg_color=theme.BG)`.
      - Call `platform_utils.apply_frameless(self)` (Task 2.8).
      - Call `self.attributes("-topmost", True)` and `self.attributes("-alpha", WINDOW_ALPHA)`.
      - Set the geometry to `WINDOW_WIDTH x WINDOW_HEIGHT`.
      - Store `self.actions = UiActions()`, `self._has_been_shown = False` and `self._start_hidden`.
    - **Startup flash guard:** customtkinter's Windows title-bar handling can re-show a withdrawn window shortly after creation. Schedule `self.after(50, self._guard_hidden)` and `self.after(300, self._guard_hidden)`. `_guard_hidden` calls `self.withdraw()` only if `self._start_hidden and not self._has_been_shown`.
    - Methods:
      - `center_on_screen()` places the window at `x = (screen_w - W) // 2` and `y = int(screen_h * WINDOW_TOP_OFFSET_RATIO)`. Use `winfo_screenwidth()` and `winfo_screenheight()` after `update_idletasks()`.
      - `show()` runs, in order: `center_on_screen()`, `deiconify()`, `attributes("-topmost", True)`, `lift()`, `focus_force()`, `platform_utils.activate_app_macos()`, `after(60, self.input_bar.focus_entry)`, then sets `_has_been_shown = True`.
      - `hide()` calls `withdraw()`.
      - `toggle()` calls `hide()` if `bool(self.winfo_viewable())`, else `show()`.
      - `quit_app()` is a stub for now. Task 6.4 fills it in.
  - **Validate:** a throwaway script constructs `MainWindow`, calls `.show()`, and `.after(2000, win.toggle)`. The window appears frameless, centered horizontally and on top, with no taskbar/titlebar. It disappears after 2 s and there is no flash at startup.

- [ ] **2.3 `ChatView`: streaming read-only transcript**
  - **Files:** `ui/chat_view.py`
  - **Instructions:**
    - Implement `class ChatView(ctk.CTkFrame)` containing one `CTkTextbox` with `wrap="word"`, `fg_color=theme.SURFACE`, `font=theme.FONT_BODY`, and `state="disabled"` by default.
    - **Tag rule:** configure tags through `self._tb._textbox.tag_config(name, foreground=..., spacing1=..., spacing3=...)`. Do NOT pass a `font=` option. customtkinter forbids it in `tag_config`.
    - Tags: `user` (ACCENT), `assistant` (TEXT), `notice` (MUTED), `error` (ERROR).
    - Every mutating method must temporarily set `state="normal"`, perform the edit, restore `state="disabled"`, and call `see("end")`.
    - Public API:
      - `append_user(text)` writes `"You: " + text + "\n\n"` with tag `user`.
      - `begin_assistant_message()` writes the prefix `"AI: "` with tag `assistant`.
      - `append_assistant_token(token)` inserts the token with tag `assistant`.
      - `end_assistant_message()` writes `"\n\n"`.
      - `append_notice(text, level="notice")` writes a muted or error line.
      - `clear()` empties the transcript.
    - Call `assert_main_thread()` (from `utils.threading_utils`, Task 6.1) at the top of each mutator once that helper exists. Until then, leave a `# TODO(6.1)` comment.
  - **Validate:** a throwaway script appends a user line, streams 50 tokens through `after()` calls at 20 ms intervals, and appends a notice. Text renders in the correct colors and auto-scrolls. The user cannot type into the box.

- [ ] **2.4 `InputBar`: entry, buttons, attachment chip**
  - **Files:** `ui/input_bar.py`
  - **Instructions:**
    - Implement `class InputBar(ctk.CTkFrame)`, constructed with `(master, actions: UiActions)`.
    - Layout, bottom to top:
      - **Row 1:** an `Attach` button on the left, a `CTkEntry` that expands (placeholder `"Ask anything…  (Enter to send, Esc to hide)"`), and a `Send` button on the right. Use plain-text button labels, not emoji, to avoid font issues.
      - **Row 2, above row 1:** an attachment chip frame containing a label (`"📄 <filename>"`) and an `✕` button. It is hidden via `grid_remove()` until an attachment exists.
    - Bind `<Return>` on the entry to `_submit()`:
      - Strip the text.
      - Ignore it if empty or if the bar is busy.
      - Truncate to `MAX_PROMPT_CHARS`.
      - Call `actions.on_submit(text)`, then clear the entry.
    - Public methods: `focus_entry()` (calls `entry.focus_set()`), `set_busy(busy: bool)`, `set_attachment(name: str | None)`, and `get_text()`.
    - **Busy behavior:** `set_busy` only disables the Send button and sets an internal flag. It never disables the entry, because the user must be able to type the next question while the model streams.
  - **Validate:** typing text and pressing Enter calls `actions.on_submit` exactly once. Empty or whitespace input does nothing. `set_attachment("a.pdf")` shows the chip and `set_attachment(None)` hides it.

- [ ] **2.5 Top bar, status label, drag-to-move**
  - **Files:** `ui/main_window.py`
  - **Instructions:**
    - Build a top bar frame with:
      - A title label (`APP_NAME`, `FONT_TITLE`) on the left.
      - A status label (`FONT_SMALL`) in the middle that expands.
      - A `Reset` button and a `Quit` button on the right.
    - Assemble the window with a grid: row 0 is the top bar, row 1 is `ChatView` (weight=1), row 2 is `InputBar`.
    - Add `MainWindow.set_status(text: str, level: str = "info")`. It looks up `STATUS_COLORS[level]` and truncates the text to about 80 characters with `…`.
    - Wire the `Reset` button to `actions.on_reset()` and the `Quit` button to `actions.on_quit()`.
    - **Drag:** frameless windows cannot be moved by default. Bind `<ButtonPress-1>` and `<B1-Motion>` on the top bar, the title label and the status label. On press, store `dx = event.x_root - self.winfo_x()` and `dy = event.y_root - self.winfo_y()`. On motion, call `self.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")`.
    - Expose `self.chat_view` and `self.input_bar` as attributes.
  - **Validate:** the window can be dragged by the top bar. `set_status("x", "error")` shows red text.

- [ ] **2.6 Keyboard bindings (keyboard-first)**
  - **Files:** `ui/main_window.py`
  - **Instructions:**
    - `self.bind_all("<Escape>", lambda e: self.hide())`.
    - `self.bind_all(f"<{MOD_KEY}-r>", lambda e: self.actions.on_reset())`. Reset the chat.
    - `self.bind_all(f"<{MOD_KEY}-o>", lambda e: self.actions.on_attach())`. Attach a file.
    - `self.bind_all(f"<{MOD_KEY}-q>", lambda e: self.actions.on_quit())`.
    - Each handler returns `"break"`.
    - Esc only hides the window. It must NOT cancel an in-flight generation. The answer keeps streaming into the hidden window and is visible when reopened.
    - Show the shortcuts as a muted one-line hint in the entry placeholder or a small footer label, using `MOD_LABEL`.
  - **Validate:** with focus in the entry, Esc hides the window, and `Ctrl/Cmd+R` and `Ctrl/Cmd+O` invoke the matching `UiActions` callbacks. Verify by temporarily assigning logging lambdas.

- [ ] **2.7 Temporary UI-only wiring in `main.py`**
  - **Files:** `main.py`
  - **Instructions:**
    - Create `MainWindow(start_hidden=not args.show)`.
    - Set `window.actions.on_submit` to a **temporary placeholder** that appends the user line and streams back `"(echo) " + text` token by token via `window.after`. Mark it with `# TEMP-PHASE2: remove in Task 5.8`.
    - Set `on_quit` to `window.destroy`.
    - Run `window.mainloop()`.
    - Until Phase 3 exists, `--show` is required to see the window.
  - **Validate:** `python main.py --show` opens the overlay. Typing, Enter, streaming echo, Esc hide, drag and Quit all work.

- [ ] **2.8 Frameless and focus handling per OS**
  - **Files:** `core/platform_utils.py`
  - **Instructions:** add two functions.
    - `apply_frameless(window) -> None`:
      - **Windows:** `window.overrideredirect(True)`.
      - **macOS:** try `window.tk.call("::tk::unsupported::MacWindowStyle", "style", window._w, "plain", "none")`. This produces a frameless window that can still take keyboard focus. On `tkinter.TclError`, fall back to `window.overrideredirect(True)` and log a warning.
      - Other OS: `overrideredirect(True)`.
    - `activate_app_macos() -> None`:
      - No-op unless `IS_MACOS`.
      - Run `subprocess.run(["osascript", "-e", f'tell application "System Events" to set frontmost of the first process whose unix id is {os.getpid()} to true'], timeout=2, capture_output=True)`.
      - Wrap it in `try/except Exception` and log at DEBUG.
      - This makes the Python process the active app so the entry receives keystrokes when the window is summoned from another app.
  - **Validate:**
    - On macOS, summon the window while another app is frontmost and type immediately. Characters land in the entry.
    - On Windows, the window is focused and typing works without clicking.
    - If any of this fails, log the exact failure and keep the fallback path.

---

## Phase 3: Global Hotkey Listener Integration

- [ ] **3.1 `UiBridge`: thread-safe main-thread dispatcher**
  - **Files:** `utils/threading_utils.py`
  - **Instructions:**
    - Implement `class UiBridge`, constructed with `(app, poll_ms=UI_POLL_MS, batch=UI_DRAIN_BATCH)`.
    - It holds a `queue.Queue[tuple[Callable, tuple, dict]]`.
    - `post(fn, *args, **kwargs)` is thread-safe and non-blocking (`put_nowait`). It is a no-op after `stop()`.
    - `start()` must be called on the main thread. It schedules `self._drain` with `app.after(poll_ms, ...)`.
    - `_drain()` runs on the main thread:
      - It pops at most `batch` items.
      - It executes each inside `try/except Exception` and logs failures with `logger.exception`, so one bad callback never kills the loop.
      - It reschedules itself with `app.after(poll_ms, self._drain)` unless stopped.
    - `stop()` sets a flag.
    - Also add `assert_main_thread()` now. Raise `RuntimeError` if `threading.current_thread() is not threading.main_thread()`, and only if `config.DEBUG_THREAD_ASSERTS`.
  - **Validate:** a script starts a `MainWindow` and `UiBridge`, spawns 5 threads that each post 100 callbacks appending to a list, and verifies that all 500 run on the main thread (check `threading.current_thread()` inside the callback).

- [ ] **3.2 `HotkeyManager`**
  - **Files:** `core/hotkey_manager.py`
  - **Instructions:**
    - Implement `class HotkeyManager`, constructed with `(combo: str, on_activate: Callable[[], None])`.
    - `on_activate` is called on the pynput thread. The manager never touches Tk. The caller passes `lambda: bridge.post(window.toggle)`.
    - **Combo validation:** in `__init__`, run `pynput.keyboard.HotKey.parse(combo)` inside `try/except (ValueError, KeyError)`. On failure, log an error and fall back to `DEFAULT_HOTKEY_COMBO`.
    - **Debounce:** `_fire()` ignores calls within `HOTKEY_DEBOUNCE_SECONDS` of the previous accepted call, using `time.monotonic()`. This prevents key-repeat double toggles.
    - `start() -> bool`:
      - Create `pynput.keyboard.GlobalHotKeys({combo: self._fire})`.
      - Set `listener.daemon = True` and call `listener.start()`.
      - Wrap everything in `try/except Exception`. On failure, log with `logger.exception` and return `False`. It never raises.
      - After starting, schedule a liveness check via `threading.Timer(0.5, ...)` that logs an ERROR if `not listener.is_alive()`.
    - `stop()` calls `listener.stop()` inside try/except. It is idempotent.
    - `is_running` property.
  - **Validate:** run a script that starts the manager with `on_activate=lambda: print("HOTKEY")`. Pressing the combo prints one `HOTKEY` per press, and 10 rapid presses do not print more than the debounce allows.

- [ ] **3.3 macOS Accessibility and Input Monitoring diagnostics**
  - **Files:** `core/platform_utils.py`
  - **Instructions:**
    - Add `is_accessibility_trusted() -> bool | None`:
      - Return `None` if not macOS.
      - Otherwise load the library and call it:
```python
        import ctypes, ctypes.util
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
```
      - Wrap it in try/except and return `None` if the check itself fails.
    - Add `ACCESSIBILITY_HELP` as a multi-line constant string:
      - `"pynput cannot see global key presses. Open System Settings → Privacy & Security → Accessibility AND Input Monitoring, enable the app that launches Python (Terminal, iTerm, VS Code, Cursor, …), then fully quit and relaunch that app."`
    - In `main.py`, on macOS, call `is_accessibility_trusted()` before starting the hotkey.
      - If it returns `False`, log `ACCESSIBILITY_HELP` at WARNING level and later show a `"warn"` status in the window: `"Hotkey needs macOS Accessibility permission (see log)"`.
      - If it returns `None`, log at INFO that trust could not be determined and continue.
  - **Validate:** on a macOS terminal without permission, the warning is logged with the exact instructions. After granting permission and relaunching, the warning disappears and the hotkey works.

- [ ] **3.4 Wire hotkey, bridge and window in `main.py`**
  - **Files:** `main.py`
  - **Instructions:** startup order:
    1. Create `MainWindow`.
    2. Create and start `UiBridge(window)`.
    3. Run the macOS accessibility check (Task 3.3).
    4. Create `HotkeyManager(HOTKEY_COMBO, lambda: bridge.post(window.toggle))` and call `start()`.
    - **Lock-out protection:** if `start()` returned `False`, or the macOS check returned `False`, call `window.show()` and `window.set_status("Global hotkey unavailable. Use the window controls.", "warn")`. This way the user is never locked out of a hidden, unreachable app.
    - If the hotkey started and `--show` is not set, the window stays hidden.
    - On Quit or window destroy, call `hotkey.stop()`. Task 6.4 hardens this.
  - **Validate:** `python main.py` starts with no visible window. The hotkey shows it focused, and pressing it again hides it. Pressing Esc hides it. Toggling 20 times quickly leaves no crash and no stuck state.

- [ ] **3.5 (Optional, Windows only, best effort) Suppress the Alt+Space system menu**
  - **Files:** `core/hotkey_manager.py`
  - **Instructions:**
    - Only activate when `IS_WINDOWS and combo == DEFAULT_HOTKEY_COMBO`.
    - Pass `win32_event_filter` to the `GlobalHotKeys(...)` constructor.
    - Constants: `WM_SYSKEYDOWN=0x0104`, `WM_SYSKEYUP=0x0105`, `VK_SPACE=0x20`.
    - In the filter: if `msg in (WM_SYSKEYDOWN, WM_SYSKEYUP) and data.vkCode == VK_SPACE`:
      - On `WM_SYSKEYDOWN`, call `self._fire()` directly (the debounce prevents a double toggle if GlobalHotKeys also fires).
      - Then call `self._listener.suppress_event()`. This stops the focused app's system menu from opening.
      - Otherwise `return True`.
    - Wrap the construction in try/except. On any failure, log a warning and fall back to the plain `GlobalHotKeys` without the filter.
  - **Validate:** manually on Windows, pressing Alt+Space shows the overlay and no window system menu flashes in the previous app. If it misbehaves, disable the filter and document the limitation in the README.

---

## Phase 4: Local RAG Engine & File Parsing Logic

- [ ] **4.1 `file_parser.py`: robust text extraction**
  - **Files:** `core/file_parser.py`
  - **Instructions:**
    - Define `@dataclass class ParseResult` with `text: str = ""`, `ok: bool = False`, `warnings: list[str] = field(default_factory=list)` and `source: str = ""`.
    - Implement `parse_file(path: Path) -> ParseResult`. **It never raises.** Wrap the whole body in `try/except Exception`, log with `logger.exception`, and return `ok=False` plus a warning.
    - Pre-checks:
      - Missing file: warning `"file not found"`.
      - Extension not in `SUPPORTED_EXTENSIONS`: warning `"unsupported type"`.
      - Size above `MAX_FILE_SIZE_MB`: warning `"file too large (>N MB)"`.
      - A zero-byte file returns `ok=False` with `"file is empty"`.
    - **TXT/MD** (`_parse_text`): read bytes, then decode by trying `utf-8`, `utf-8-sig`, `cp1252`, then `latin-1`. The last always succeeds, so decoding never fails. Normalize `\r\n` to `\n`.
    - **JSON** (`_parse_json`): decode as above, then `json.loads`. On success, return `json.dumps(obj, indent=2, ensure_ascii=False)`. On `json.JSONDecodeError`, fall back to the raw decoded text and add the warning `"invalid JSON, used raw text"`.
    - **PDF** (`_parse_pdf`), using `pypdf.PdfReader` with this fallback chain:
      1. Open with `PdfReader(str(path))`. On `pypdf.errors.PdfReadError` or any exception, return `ok=False` with `"corrupted or unreadable PDF"`.
      2. If `reader.is_encrypted`, try `reader.decrypt("")`. If that returns 0 or raises, return `ok=False` with `"PDF is password-protected"`.
      3. Iterate over `reader.pages[:MAX_PDF_PAGES]`. If there are more pages, add the warning `"only first N pages read"`.
      4. For each page, first try `page.extract_text()`. If it raises or returns only whitespace, retry with `page.extract_text(extraction_mode="layout")`. If that also fails, skip the page, log at DEBUG, and increment a `skipped_pages` counter.
      5. After the loop, if the joined text is whitespace-only, return `ok=False` with the warning `"no extractable text (probably a scanned/image-only PDF; OCR is not supported)"`.
      6. If `skipped_pages > 0` and the text is non-empty, return `ok=True` with the warning `"N pages had no extractable text"`.
      - Join pages with `"\n\n"`. Collapse runs of 3+ newlines to 2.
    - Add `parse_attachment(path: Path, max_chars: int = ATTACHMENT_MAX_CHARS) -> ParseResult`. It calls `parse_file`, and if the text is longer than `max_chars` it truncates it and appends `"\n[…truncated]"` plus the warning `"attachment truncated to N characters"`.
  - **Validate:** see Task 4.7 for the test suite. Quick check: parsing a `.txt` and a `.json` file returns `ok=True`, and a random-bytes file renamed to `.pdf` returns `ok=False` without raising.

- [ ] **4.2 Chunker**
  - **Files:** `core/rag_engine.py`
  - **Instructions:**
    - Implement `chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]`.
    - Algorithm:
      1. Strip the text. Return `[]` if it is empty.
      2. Return `[text]` if `len(text) <= size`.
      3. Use a sliding window with `step = size - overlap`.
      4. For each window `[start, start+size)`, if it is not the last window, snap `end` back to the last whitespace within the final 100 characters of the window. If none, keep the hard cut.
      5. The next `start` is `end - overlap`. Guarantee progress: `start` must strictly increase every iteration.
      6. Strip each chunk and drop empty chunks.
    - Raise `ValueError` if `overlap >= size`.
  - **Validate:** the unit tests in Task 4.7 pass. A 5000-character input gives overlapping chunks, each at most `size` long, and the concatenation covers the entire text.

- [ ] **4.3 `RagEngine`: index, incremental background scanner**
  - **Files:** `core/rag_engine.py`
  - **Instructions:**
    - Define `@dataclass class ScanReport` with `files_total`, `files_indexed`, `files_skipped`, `chunks`, `warnings: list[str]`, `folder_created: bool`, plus `status_text() -> str` returning one of:
      - Folder created: `"Created ./materi_kuliah. Add your notes and PDFs."`
      - `files_total == 0`: `"materi_kuliah is empty. Answering from general knowledge."`
      - `files_indexed == 0`: `f"Found {files_total} files but none had readable text (see log)."`
      - Otherwise: `f"Indexed {files_indexed} files · {chunks} chunks"`.
    - Define `@dataclass class IndexedFile` with `rel_path: str`, `mtime_ns: int`, `size: int`, `chunks: list[str]`, and per-chunk `tokens: list[Counter]` and `lengths: list[int]`.
    - Implement `class RagEngine`, constructed with `(root: Path = MATERI_DIR)`. It owns `self._lock = threading.Lock()`, `self._files: dict[str, IndexedFile]`, `self._df: Counter`, `self._avgdl: float`, `self._n_chunks: int`, `self._stop = threading.Event()`, `self.enabled = True`.
    - `scan() -> ScanReport`:
      - If the folder does not exist, run `root.mkdir(parents=True, exist_ok=True)` and set `folder_created=True`. If `mkdir` raises `OSError`, log an ERROR, set `self.enabled=False` and return a report whose warnings contain the error.
      - Walk with `os.walk(root, followlinks=False)`. Skip dot-files, `~$*` Office temp files, and `__pycache__` directories.
      - Keep only `SUPPORTED_EXTENSIONS`, matched case-insensitively. Count them in `files_total`.
      - Incremental update: if a file's `(mtime_ns, size)` matches the existing `IndexedFile`, reuse it. Otherwise call `parse_file` and `chunk_text` and build a new `IndexedFile`. A file whose `ParseResult.ok` is `False` is counted in `files_skipped` and its warnings are collected. It is not indexed.
      - Files no longer on disk are removed from the index.
      - Build the new `files` dict outside the lock. Swap it in under the lock together with the recomputed `_df`, `_avgdl` and `_n_chunks`.
    - `start_background_scan(on_update: Callable[[ScanReport], None]) -> None`:
      - Start a `daemon=True` thread named `rag-scanner`.
      - It runs `scan()` immediately and calls `on_update(report)`.
      - Then loop: `while not self._stop.wait(RESCAN_INTERVAL_SECONDS)`, run `scan()` again.
      - Call `on_update` only when something changed since the last report (a different `files_indexed`, `chunks` or `files_total`).
      - Wrap each iteration in try/except so the thread never dies.
      - `on_update` runs on this thread. The caller must wrap it with `bridge.post`.
    - `stop()` sets `_stop`.
  - **Validate:** with `--debug`, a smoke run (Task 4.6) prints a `ScanReport` for an empty folder, for a missing folder (which gets created), and for a folder with 2 files. Touching a file triggers a re-index on the next cycle and deleting it removes it.

- [ ] **4.4 BM25 retrieval (pure Python, no embeddings)**
  - **Files:** `core/rag_engine.py`
  - **Instructions:**
    - Add module-level `STOPWORDS`, a frozenset of common English and Indonesian words. It must include at least: `the a an and or of to in on for with is are was be this that it as by at from yang dan di ke dari untuk pada adalah itu ini dengan atau apa bagaimana siapa kapan dimana saya aku tolong jelaskan`.
    - Add `tokenize(text: str) -> list[str]`: lowercase, `re.findall(r"\w+", text)`, drop tokens shorter than 2 characters and stopwords.
    - **At index time**, build each chunk's token `Counter` from `tokenize(Path(rel_path).stem + " " + chunk)`. The file name is included so queries such as "jadwal" match `jadwal.md`.
    - Define `@dataclass class RetrievedChunk` with `source: str`, `chunk_index: int`, `text: str`, `score: float`.
    - Implement `retrieve(query: str, top_k: int = TOP_K_CHUNKS) -> list[RetrievedChunk]` under the lock:
      - Return `[]` if the engine is disabled, the index is empty, or the query has no tokens.
      - BM25 with `k1=1.5`, `b=0.75`, and `idf = log(1 + (N - df + 0.5) / (df + 0.5))`.
      - Score = sum over query terms present in the chunk of `idf * tf * (k1+1) / (tf + k1 * (1 - b + b * dl / avgdl))`.
      - Keep only `score > 0`. Sort descending and return the top `top_k`.
  - **Validate:** the unit tests in Task 4.7 pass. A query matching a keyword unique to one file returns a chunk from that file first.

- [ ] **4.5 Context builder and schedule injection**
  - **Files:** `core/rag_engine.py`
  - **Instructions:**
    - `build_context(query: str, max_chars: int = MAX_CONTEXT_CHARS) -> tuple[str, list[str]]`:
      - Call `retrieve`.
      - Format each chunk as `f"[Source: {source} · part {chunk_index + 1}]\n{text}"`, separated by `"\n\n---\n\n"`.
      - Append whole chunks until adding the next one would exceed `max_chars`. If the first chunk alone exceeds the limit, hard-truncate it.
      - Return the context string and a de-duplicated, order-preserving list of source file names. Both are empty when nothing matches.
    - `get_schedule_context(max_chars: int = SCHEDULE_MAX_CHARS) -> str`:
      - Collect indexed files whose stem lowercased starts with any of `SCHEDULE_FILE_PREFIXES`.
      - Concatenate their full chunks in file and chunk order, with a header line `f"[{source}]"` per file.
      - Truncate to `max_chars`. Return `""` if there are none.
    - `stats() -> dict` returns `{"files": ..., "chunks": ...}`.
  - **Validate:** with `jadwal.md` and `notes.md` indexed, `get_schedule_context()` returns only the jadwal text, and `build_context("neural network")` returns only matching material.

- [ ] **4.6 RAG smoke-test CLI**
  - **Files:** `core/rag_engine.py`
  - **Instructions:** add an `if __name__ == "__main__":` block using `argparse` with `--query TEXT`. It sets up logging, runs a single `scan()`, prints `report.status_text()` and any warnings, then prints the sources and the first 300 characters of the context for the query.
  - **Validate:** `python -m core.rag_engine --query "kalkulus"` works against a folder you populate manually. Cover the cases: no folder, empty folder, folder with only `.docx`, folder with a corrupted PDF.

- [ ] **4.7 Tests for parser, chunker, retrieval**
  - **Files:** `tests/test_file_parser.py`, `tests/test_rag_engine.py`
  - **Instructions:** use `tmp_path` fixtures and write files at test time. Required cases:
    - **Parser:**
      - UTF-8 text and a cp1252 text file.
      - Valid JSON and invalid JSON (fallback plus warning).
      - A zero-byte file.
      - An unsupported extension.
      - Random bytes saved as `.pdf` (`ok=False`, no exception).
      - A blank-page PDF created with `pypdf.PdfWriter().add_blank_page(...)`, which must give `ok=False` with a "scanned" warning.
      - A positive text PDF: use `tests/fixtures/sample.pdf` if present, otherwise mark the test with `pytest.mark.skipif(not path.exists(), reason=...)`.
      - Oversize-file rejection, monkeypatching `config.MAX_FILE_SIZE_MB` to a tiny value.
    - **Chunker:** short text gives one chunk. Long text has the right overlap, never exceeds `size`, and covers the whole text. `overlap >= size` raises `ValueError`. Empty text gives `[]`.
    - **Engine:**
      - Missing folder is created and reported via `folder_created`.
      - An empty folder gives `status_text()` containing "empty".
      - Incremental re-scan reuses unchanged files, picks up modified ones and drops deleted ones.
      - `retrieve` returns the correct file first, and returns `[]` for gibberish.
      - Schedule context picks up `jadwal.md`.
      - Dot-files and unsupported types are ignored.
  - **Validate:** `python -m pytest -q` is green.

---

## Phase 5: Ollama API Integration & Context Memory

- [ ] **5.1 `ChatMemory`**
  - **Files:** `core/chat_memory.py`
  - **Instructions:**
    - Implement `class ChatMemory`, constructed with `(max_turns: int = MAX_HISTORY_TURNS)`. It holds a list of `{"role": "user"|"assistant", "content": str}` dicts.
    - Methods:
      - `commit_turn(user_text: str, assistant_text: str)` appends both messages **together**. This guarantees history always alternates user/assistant. Messages are only ever committed after a successful generation.
      - `get_history() -> list[dict]` returns a **copy** of the last `max_turns * 2` messages.
      - `reset()` clears the history.
      - `__len__` returns the number of turns.
    - **Important:** store the user's **raw question only**. Retrieved context and attachment text must never be saved in memory. Otherwise history bloats and the context window overflows.
  - **Validate:** tests in Task 5.9.

- [ ] **5.2 `OllamaClient`: streaming chat, health check, typed errors**
  - **Files:** `core/llm_client.py`
  - **Instructions:**
    - Exceptions, all subclasses of `class LLMError(Exception)`:
      - `OllamaConnectionError`.
      - `OllamaTimeoutError`, with attribute `kind: Literal["connect", "read"]`.
      - `OllamaModelNotFoundError`.
      - `OllamaResponseError`, with attribute `detail: str`.
      - `OllamaCancelled`, which is not an error and is used for user-initiated cancel.
    - `class OllamaClient`, constructed with `(chat_url=OLLAMA_CHAT_URL, tags_url=OLLAMA_TAGS_URL, model=OLLAMA_MODEL)`.
    - `stream_chat(messages: list[dict], cancel_event: threading.Event | None = None) -> Iterator[str]`:
      - Build the payload: `{"model": model, "messages": messages, "stream": True, "keep_alive": OLLAMA_KEEP_ALIVE, "options": {"num_ctx": OLLAMA_NUM_CTX}}`.
      - Call `requests.post(chat_url, json=payload, stream=True, timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_READ_TIMEOUT))`.
      - **Exception order matters.** `ConnectTimeout` is a subclass of both `ConnectionError` and `Timeout`. Catch in this order:
        1. `requests.exceptions.ConnectTimeout` → `OllamaTimeoutError("connect")`.
        2. `requests.exceptions.ReadTimeout` → `OllamaTimeoutError("read")`.
        3. `requests.exceptions.ConnectionError` → `OllamaConnectionError`.
      - **Mid-stream timeouts:** `requests` raises `ConnectionError` for read timeouts that happen inside `iter_lines()`. Inside the stream loop, if `"timed out"` appears in `str(exc).lower()`, raise `OllamaTimeoutError("read")`. Otherwise raise `OllamaResponseError("stream interrupted")`.
      - **HTTP errors:** if `status_code == 404`, raise `OllamaModelNotFoundError`. For any other non-200, raise `OllamaResponseError` with the first 200 characters of the body.
      - **Parsing:** iterate `resp.iter_lines(decode_unicode=True)`.
        - Skip empty lines.
        - On `json.JSONDecodeError`, log and skip the line.
        - If the object has an `"error"` key, raise `OllamaResponseError(detail=...)`.
        - Yield `obj["message"]["content"]` when non-empty.
        - Stop when `obj.get("done")` is true.
      - Check `cancel_event.is_set()` between lines. If set, raise `OllamaCancelled`.
      - Always close the response in a `finally` block with `resp.close()`.
    - `check_health() -> tuple[bool, str]`:
      - GET `tags_url` with `timeout=(OLLAMA_CONNECT_TIMEOUT, 5)`.
      - Failure to connect gives `(False, "Ollama is not running at localhost:11434.")`.
      - If a model's `name == self.model` or `name.startswith(self.model + ":")` exists, return `(True, "Ollama ready · llama3")`. Otherwise `(False, "Model 'llama3' not installed. Run: ollama pull llama3")`.
      - It must never raise.
  - **Validate:** tests in Task 5.9. Manual check with Ollama running: `list(client.stream_chat([{"role":"user","content":"Say hi"}]))` returns tokens.

- [ ] **5.3 `prompt_builder.py`**
  - **Files:** `core/prompt_builder.py`
  - **Instructions:**
    - Define `SYSTEM_PROMPT_TEMPLATE` exactly as follows:
```
      You are Second Brain, a private study assistant for a university student.
      Current local date and time: {now}.
      Rules:
      - Reply in the same language the student uses (Indonesian or English).
      - When a "COURSE MATERIAL" block is provided, base your answer on it and mention the source file names you used.
      - When a "SCHEDULE" block is provided, use it for questions about classes, deadlines or plans; resolve relative dates ("tomorrow", "besok") using the current date above.
      - When an "ATTACHED DOCUMENT" block is provided, treat it as the primary source for this question.
      - If the provided material does not contain the answer, say so clearly, then answer from general knowledge and label it as such.
      - Be concise; use short lists or steps for study explanations.
```
    - `build_system_prompt(now: datetime | None = None) -> str`: format `{now}` as `"%A, %d %B %Y, %H:%M"`.
    - `build_user_message(question: str, rag_context: str = "", schedule_context: str = "", attachment: tuple[str, str] | None = None) -> str`:
      - Assemble the blocks in this order, omitting any that are empty: `### SCHEDULE`, `### COURSE MATERIAL`, `### ATTACHED DOCUMENT (<filename>)`, then always `### QUESTION` followed by the raw question.
      - Separate blocks with a blank line.
    - `assemble_messages(system: str, history: list[dict], user_message: str) -> list[dict]` returns `[{"role": "system", ...}, *history, {"role": "user", ...}]`.
  - **Validate:** tests in Task 5.9.

- [ ] **5.4 `AppController`: orchestration**
  - **Files:** `core/controller.py`
  - **Instructions:**
    - Implement `class AppController`, constructed with `(window: MainWindow, bridge: UiBridge, rag: RagEngine, client: OllamaClient, memory: ChatMemory)`.
    - State: `self._busy: bool`, `self._gen_id: int = 0`, `self._cancel: threading.Event | None`, and `self._attachment: tuple[str, str] | None` holding `(filename, text)`.
    - `bind()` assigns the `window.actions` callbacks to the controller methods below.
    - **`on_submit(text)`** runs on the main thread:
      1. Ignore it if `self._busy`.
      2. Set `_busy=True`, increment `_gen_id` and store `gen_id`.
      3. Create a new `_cancel = threading.Event()`.
      4. Call `chat_view.append_user(text)` and `input_bar.set_busy(True)`.
      5. Set the status `("Searching materials…", "busy")`.
      6. Snapshot the attachment.
      7. Start `threading.Thread(target=self._generate, args=(gen_id, text, snapshot, self._cancel), daemon=True, name="llm-worker")`.
    - **`_generate(gen_id, question, attachment, cancel)`** runs on the worker thread and **must never touch widgets**. Use `bridge.post` for every UI effect, and have each posted callback ignore itself if `gen_id != self._gen_id`:
      1. Call `rag.build_context(question)` and `rag.get_schedule_context()`.
      2. If the context is empty and there is no attachment, post status `("No local match · asking llama3…", "busy")`. Otherwise post `("Thinking…", "busy")`.
      3. Build the system prompt, user message and messages (Task 5.3) using `memory.get_history()`.
      4. Post `chat_view.begin_assistant_message`.
      5. Iterate `client.stream_chat(messages, cancel)`. For each token, append it to a local list and post `chat_view.append_assistant_token(token)`.
      6. On success, post `_on_done(gen_id, question, "".join(tokens), sources)`.
      7. On `OllamaCancelled`, post nothing (the reset flow already cleaned up the UI).
      8. On `LLMError`, post `_on_error(gen_id, _format_error(exc), partial_text)`.
      9. On any other `Exception`, log with `logger.exception` and post `_on_error(gen_id, "Unexpected error. See logs/second_brain.log", partial_text)`.
    - **`_on_done`** runs on the main thread, only if `gen_id == self._gen_id`:
      - Call `chat_view.end_assistant_message()`.
      - If `sources` is non-empty, call `chat_view.append_notice("Sources: " + ", ".join(sources))`.
      - Call `memory.commit_turn(question, answer)`.
      - Clear the attachment (the attachment is one-shot: it is temporary for that specific prompt) and call `input_bar.set_attachment(None)`.
      - Set `_busy=False`, call `input_bar.set_busy(False)`, set the status `("Ready", "ok")`, and call `input_bar.focus_entry()`.
    - **`_on_error`** runs on the main thread, only if `gen_id == self._gen_id`:
      - If a partial answer was streamed, call `end_assistant_message()` and append the notice `"[response interrupted]"`.
      - Call `append_notice(message, "error")`.
      - Do **not** commit anything to memory.
      - **Keep** the attachment so the user can retry.
      - Reset `_busy` and the input state. Set the status `(message, "error")`.
    - **`_format_error(exc) -> str`** mapping:
      - `OllamaConnectionError` → `"Can't reach Ollama at localhost:11434. Start the Ollama app (or run 'ollama serve') and try again."`
      - `OllamaModelNotFoundError` → `"Model 'llama3' isn't installed. Run: ollama pull llama3"`
      - `OllamaTimeoutError` with kind `connect` → `"Ollama didn't answer within 5 s. Is it running?"`
      - `OllamaTimeoutError` with kind `read` → `"The model stopped responding for 120 s. It may still be loading. Try again."`
      - `OllamaResponseError` → `f"Ollama returned an error: {exc.detail}"`
    - **Rule of thumb:** use the config constants in these messages through f-strings rather than hard-coded numbers.
  - **Validate:** unit-style check with a fake `OllamaClient` whose `stream_chat` yields tokens. After one exchange, `memory` has exactly 1 turn, the attachment is cleared, and `_busy` is `False`. With a fake client that raises `OllamaConnectionError`, `memory` stays empty and the attachment is kept.

- [ ] **5.5 Manual file upload (temporary attachment)**
  - **Files:** `core/controller.py`, `ui/input_bar.py`
  - **Instructions:**
    - `on_attach()` runs on the main thread:
      - Ignore it while busy.
      - Temporarily call `window.attributes("-topmost", False)` before opening the dialog and restore it afterwards in a `finally`, so the native dialog is not hidden behind the always-on-top window (notably on macOS).
      - Open `tkinter.filedialog.askopenfilename(parent=window, title="Attach a document", filetypes=[("Documents", "*.pdf *.txt *.md *.json")])`.
      - Return silently if the user cancels (the dialog returns `""`).
    - Parse in a worker thread named `attach-parser` that calls `file_parser.parse_attachment(path)`, then posts the result to the main thread:
      - Set the status `("Reading <filename>…", "busy")` before starting the thread.
      - If `result.ok`, store `(path.name, result.text)`, call `input_bar.set_attachment(path.name)` and set the status `(f"Attached {path.name}", "ok")`. Show any warnings as a `"warn"` status (the first warning is enough).
      - If not `ok`, call `append_notice(f"Couldn't read {path.name}: {result.warnings[0]}", "error")` and attach nothing.
    - `on_remove_attachment()` clears `_attachment` and calls `input_bar.set_attachment(None)`.
  - **Validate:**
    - Attach a small PDF, ask "summarize the attachment", and receive an answer based on it. The chip disappears after the answer.
    - Attach a corrupted PDF and get a readable notice with no chip.
    - Attach a scanned PDF and get the "no extractable text" notice.

- [ ] **5.6 Conversation reset with in-flight cancellation**
  - **Files:** `core/controller.py`
  - **Instructions:**
    - `on_reset()` runs on the main thread:
      - If `_cancel` exists, call `.set()`.
      - Increment `_gen_id`. This invalidates any late callbacks from the old worker.
      - Call `memory.reset()`, `chat_view.clear()`, clear the attachment, call `input_bar.set_attachment(None)` and `input_bar.set_busy(False)`.
      - Set `_busy=False`.
      - Set the status `("Conversation reset", "ok")`.
      - Call `input_bar.focus_entry()`.
  - **Validate:** start a long answer and press `Ctrl/Cmd+R` mid-stream. The transcript clears, no stray tokens appear afterwards, and a new question works immediately.

- [ ] **5.7 Startup wiring: RAG scanner and Ollama health check**
  - **Files:** `core/controller.py`, `main.py`
  - **Instructions:**
    - `controller.start_background_services()`:
      - Call `rag.start_background_scan(lambda report: bridge.post(self._on_scan_update, report))`.
      - Start a one-shot daemon thread named `health-check` that calls `client.check_health()` and posts the `(ok, message)` result to `_on_health(ok, message)`.
    - `_on_scan_update(report)` is main-thread only. If not busy, set the status `(report.status_text(), "warn" if report.files_indexed == 0 else "info")`. If busy, skip, so it does not overwrite "Thinking…". Log the first 5 report warnings at WARNING level.
    - `_on_health(ok, message)` is main-thread only. If not ok, call `append_notice(message, "error")` and set the status `(message, "error")`. Do not block usage, because Ollama may be started later.
  - **Validate:** with Ollama stopped, the window shows the "not running" message at startup, and after starting Ollama a question works with no restart. With the `llama3` model missing, the pull instruction appears.

- [ ] **5.8 Final `main.py` wiring and removal of placeholder**
  - **Files:** `main.py`
  - **Instructions:**
    - Remove the `# TEMP-PHASE2` echo handler.
    - Construct `RagEngine`, `OllamaClient`, `ChatMemory` and `AppController(...)`.
    - Call `controller.bind()` and `controller.start_background_services()`.
    - Keep the hotkey wiring from Task 3.4.
    - `window.actions.on_quit` must call `controller.shutdown()` (Task 6.4).
  - **Validate:** end to end. Press the hotkey, ask "What is in my notes about X?" with a matching file in `materi_kuliah/`, and get a streamed answer with a `Sources:` line. A follow-up question shows memory in effect (for example "explain that more simply").

- [ ] **5.9 Tests for memory, prompts and LLM client**
  - **Files:** `tests/test_chat_memory.py`, `tests/test_prompt_builder.py`, `tests/test_llm_client.py`
  - **Instructions:**
    - **Memory:**
      - `commit_turn` keeps alternating roles.
      - `get_history` trims to `max_turns * 2`.
      - `get_history` returns a copy.
      - `reset` empties the history.
    - **Prompts:**
      - Empty blocks are omitted.
      - Block order is schedule, material, attachment, question.
      - The system prompt contains the formatted date.
      - `assemble_messages` places the system message first and the user message last.
    - **LLM client:** monkeypatch `requests.post` with a fake response exposing `status_code`, `iter_lines()` and `close()`. Cover:
      - Normal NDJSON stream with a final `{"done": true}` line.
      - A malformed JSON line is skipped.
      - An `{"error": "..."}` line raises `OllamaResponseError`.
      - HTTP 404 raises `OllamaModelNotFoundError`.
      - `ConnectTimeout` raises `OllamaTimeoutError` with `kind="connect"`.
      - `ReadTimeout` raises `OllamaTimeoutError` with `kind="read"`.
      - `ConnectionError` raises `OllamaConnectionError`.
      - A `ConnectionError("Read timed out")` raised from inside `iter_lines` becomes `OllamaTimeoutError("read")`.
      - A set `cancel_event` raises `OllamaCancelled`.
      - `close()` is always called.
      - `check_health` for a tag list with `llama3:latest` returns ok, an empty list returns the pull instruction, and a connection error returns not-running.
  - **Validate:** `python -m pytest -q` is green.

---

## Phase 6: Multithreading, Error Handling & Cross-Platform Polish

- [ ] **6.1 Thread-safety audit and runtime assertions**
  - **Files:** `ui/chat_view.py`, `ui/input_bar.py`, `ui/main_window.py`, `utils/threading_utils.py`
  - **Instructions:**
    - Call `assert_main_thread()` (Task 3.1) at the top of every public mutating method of `ChatView`, `InputBar` and `MainWindow` (`show`, `hide`, `toggle`, `set_status`, `set_attachment` and so on).
    - Remove the `TODO(6.1)` comments left in Phase 2.
    - Audit `core/` and `utils/` with `grep -rn "after(\|\.configure(\|\.insert(\|deiconify\|withdraw" core utils`. Only `UiBridge._drain` may reference `.after`. Any other hit in a thread-run function is a bug.
    - Verify every callback passed to `bridge.post` runs main-thread-only code.
  - **Validate:** run `SECOND_BRAIN_DEBUG=1 python main.py --debug` and exercise all features (hotkey, ask, attach, reset, rescan). No `RuntimeError` appears from the assertions.

- [ ] **6.2 Global exception hooks**
  - **Files:** `main.py`
  - **Instructions:**
    - Set `sys.excepthook` and `threading.excepthook` to log the traceback with `logger.critical` or `logger.error`.
    - Override `window.report_callback_exception = lambda exc, val, tb: logger.error("Tk callback error", exc_info=(exc, val, tb))` and also show a `"error"` status: `"Internal error. See logs/second_brain.log"`.
    - Ensure the hotkey, RAG and LLM threads each have an outermost try/except. A background thread must never die silently.
  - **Validate:** temporarily raise an exception inside a Tk callback and inside a worker thread. Both are logged, the UI keeps running, and the temporary raise is removed afterwards.

- [ ] **6.3 Input and resource hardening**
  - **Files:** `core/controller.py`, `ui/input_bar.py`, `core/rag_engine.py`
  - **Instructions:**
    - Reject prompts longer than `MAX_PROMPT_CHARS` by truncating them and showing a one-line notice.
    - Confirm the combined prompt (system + schedule + context + attachment + history) stays within `OLLAMA_NUM_CTX` tokens, approximating 1 token ≈ 4 characters. If the estimate exceeds about 90% of `OLLAMA_NUM_CTX * 4` characters, drop the oldest history turns until it fits and log the trim at INFO.
    - Make `RagEngine.scan()` tolerate files that vanish or are locked mid-scan (`OSError`, `PermissionError`). Skip the file and add a warning.
  - **Validate:** paste 10,000 characters and confirm truncation plus notice. Attach a maximum-size text file, ask a question, and confirm no error and a coherent answer.

- [ ] **6.4 Graceful shutdown**
  - **Files:** `core/controller.py`, `ui/main_window.py`, `main.py`
  - **Instructions:**
    - `AppController.shutdown()`:
      - Set `_cancel` if present.
      - Call `rag.stop()` and `hotkey.stop()` (pass a reference to the hotkey manager into the controller).
      - Call `bridge.stop()`.
      - Log "shutdown".
    - `MainWindow.quit_app()` calls `actions.on_quit()` and, afterwards, `self.destroy()` inside try/except.
    - Register `atexit.register(controller.shutdown)`.
    - Install `signal.signal(signal.SIGINT, lambda *_: bridge.post(window.quit_app))` so Ctrl+C in the launching terminal quits cleanly. The `UiBridge` poll keeps the interpreter responsive to signals.
    - Handle the window-manager close event with `window.protocol("WM_DELETE_WINDOW", window.quit_app)`.
  - **Validate:** quit via the Quit button, `Ctrl/Cmd+Q`, and Ctrl+C in the terminal. In all cases, the process exits within about 2 s and no `python` process lingers in Task Manager or Activity Monitor.

- [ ] **6.5 Cross-platform visual and focus polish**
  - **Files:** `ui/theme.py`, `ui/main_window.py`, `core/platform_utils.py`
  - **Instructions:**
    - Reassert `-topmost` and `-alpha` on every `show()`.
    - Confirm `-alpha` works with the frameless window on both OSes. If it errors on macOS, catch `tkinter.TclError` and continue.
    - Confirm the window is centered on the **primary** screen. Per-monitor placement is out of scope. Document it in the README Decisions section.
    - Verify fonts render on both OSes, with the fallback families from Task 2.1.
    - macOS Dock: the Python process shows a Dock icon. Document this as a known limitation. Do not add PyObjC.
  - **Validate:** run the full manual QA checklist (Task 6.7) on both Windows and macOS.

- [ ] **6.6 (Optional) Packaging notes**
  - **Files:** `README.md`
  - **Instructions:** document, without automating:
    - Windows: `pyinstaller --noconsole --onefile --collect-all customtkinter main.py`.
    - macOS: `pyinstaller --windowed --collect-all customtkinter main.py`. Note that the Accessibility and Input Monitoring grant must then be given to the built app instead of the terminal.
    - `config.BASE_DIR` assumes running from source. Under PyInstaller, `materi_kuliah/` and `logs/` should resolve next to the executable. Add this as a TODO in the README.
  - **Validate:** the README section exists. No packaging code is required.

- [ ] **6.7 Manual QA checklist and final README pass**
  - **Files:** `tests/manual_qa_checklist.md`, `README.md`
  - **Instructions:** write the checklist below as markdown checkboxes in `tests/manual_qa_checklist.md`. Run every item on both Windows and macOS, and record the OS and result for each.
    - Hotkey toggles show and hide 20 times quickly, with no crash and no double toggle.
    - After showing, typing works immediately with no click. Esc hides the window.
    - Window can be dragged. Reset, Attach and Quit shortcuts work.
    - Missing `materi_kuliah/`: the folder is created and the status says so.
    - Empty `materi_kuliah/`: the status says it is empty and the chat still answers from general knowledge.
    - Folder with only `.docx`: it reports files found but none readable.
    - Corrupted PDF, password-protected PDF and scanned PDF in `materi_kuliah/`: the app does not crash and the log shows clear warnings.
    - A question that matches a file returns an answer with a `Sources:` line.
    - A `jadwal.md` file: "jadwal besok apa?" and "what do I have on Friday?" produce answers using the current date.
    - Adding a file while the app runs: it is indexed within `RESCAN_INTERVAL_SECONDS`. Deleting it removes it from the index.
    - Multi-turn memory: a follow-up without context works. Reset clears memory and the transcript.
    - Reset during streaming: the old stream stops and nothing leaks into the new conversation.
    - Attachment: it is used for one prompt, then cleared. A failed prompt keeps the attachment.
    - Ollama stopped: a clear message appears, and the app recovers after Ollama starts.
    - Model missing: the pull instruction appears.
    - Timeout: set `OLLAMA_READ_TIMEOUT = 1`, ask a question against a cold model, and confirm the timeout message appears. Restore the value afterwards.
    - macOS without Accessibility permission: the warning is logged and the window is shown at startup with the status notice.
    - Invalid `SECOND_BRAIN_HOTKEY` value: it falls back to the default and logs an error.
    - Quit via button, `Ctrl/Cmd+Q` and Ctrl+C: all exit cleanly.
  - Update the README "Decisions" section with every choice made during implementation.
  - **Validate:** the checklist is complete with no unchecked failures, and `python -m pytest -q` is green.

---

## Edge-Case Coverage Matrix

| Edge case | Where handled | How |
|---|---|---|
| macOS Tkinter thread safety | 3.1, 5.4, 6.1 | Only the main thread touches Tk. Other threads call `UiBridge.post`, drained by a main-thread `app.after()` loop. Debug-mode `assert_main_thread()` enforces it. |
| macOS Accessibility / Input Monitoring for `pynput` | 3.3, 3.4 | `AXIsProcessTrusted` check, a logged warning with exact System Settings steps, and the window is shown at startup so the user is never locked out. |
| macOS focus on a frameless window | 2.8 | `MacWindowStyle plain none` with fallback to `overrideredirect`, plus `activate_app_macos()`. |
| Empty / missing / unreadable `materi_kuliah` | 4.3, 4.6, 4.7 | Auto-create the folder, distinct `status_text()` messages, no context block, and the model answers from general knowledge. |
| PDF extraction failures | 4.1, 4.7 | `extract_text()`, then `layout` mode, then page skip, then whole-document "scanned PDF" result. Handles corrupt and encrypted files and page limits. Never raises. |
| LLM connection errors and timeouts | 5.2, 5.4, 5.9 | Typed exceptions with correct `requests` exception ordering, mid-stream timeout detection, and friendly messages. Memory is untouched on failure. |
| Hotkey double firing and conflicts | 3.2, 3.5, README | Debounce, optional Windows system-menu suppression, and a configurable combo with fallback. |
| Stale async results after reset | 5.6 | `_gen_id` guard plus a cancel event. |
| Context window overflow | 5.1, 6.3 | Memory stores raw questions only, context and attachment are size-capped, and old history is trimmed. |

---

## Definition of Done

- [ ] All boxes in Phases 1 to 6 are ticked.
- [ ] `python -m pytest -q` is green on Windows and macOS.
- [ ] The manual QA checklist (Task 6.7) is fully complete on both OSes.
- [ ] `python main.py` starts hidden, the global hotkey summons a focused frameless dark overlay, Esc hides it, and the whole flow (RAG answer with sources, schedule question, attachment, multi-turn memory, reset) works against a local `llama3` via Ollama.
- [ ] No Tk call occurs off the main thread (verified with `SECOND_BRAIN_DEBUG=1`).
- [ ] The README contains setup steps, OS permissions, hotkey configuration, known limitations and the Decisions log.