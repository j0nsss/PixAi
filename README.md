# Second Brain

A local, cross-platform (Windows + macOS) floating-overlay AI assistant for student productivity: study-material retrieval (RAG), schedule help, and multi-turn chat. The LLM is local Ollama (`llama3`).

## Install Ollama

1. Install Ollama from https://ollama.com
2. Pull the model: `ollama pull llama3`
3. Verify: `ollama list` should show `llama3`

## Install the Project

1. Python 3.10+ required
2. Create virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   # Windows: .venv\Scripts\activate
   # macOS: source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Run the App

```bash
python main.py
```

The app starts hidden. Press the hotkey to show the overlay.

## Hotkey

- **Windows**: `Alt+Space`
- **macOS**: `Option+Space`

Override with `SECOND_BRAIN_HOTKEY` environment variable (pynput syntax), e.g.:
```bash
SECOND_BRAIN_HOTKEY="<ctrl>+<shift>+<space>" python main.py
```

## macOS Permissions

Grant **Accessibility** and **Input Monitoring** to the terminal or IDE that launches Python:
- System Settings → Privacy & Security → Accessibility
- System Settings → Privacy & Security → Input Monitoring

Enable the app (Terminal, iTerm, VS Code, Cursor, etc.), then fully quit and relaunch it.

## Materials

Put study files in `./materi_kuliah/`. Supported formats: `.pdf`, `.txt`, `.md`, `.json`.

An optional schedule file named `jadwal.md` / `schedule.md` / `timetable.*` is injected into every prompt as the schedule source.

## Known Conflicts

- PowerToys Run (Alt+Space on Windows)
- Alfred, Raycast (macOS)
- Windows native window menu (Alt+Space)

## Decisions

*None yet.*