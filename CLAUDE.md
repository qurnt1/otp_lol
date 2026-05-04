# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

OTP LOL v11.0 — a Windows desktop assistant for League of Legends champion select automation. Connects to the LCU API via `lcu-driver`, auto-accepts queues, pre-picks/locks champions, bans, sets summoner spells, applies rune pages, and selects skins. Built with Python 3.13, Tkinter/ttkbootstrap, and shipped as a PyInstaller executable.

## Commands

```bash
# Install runtime deps
pip install -r requirements.txt

# Install build deps (includes runtime)
pip install -r requirements-build.txt

# Run the app (dev)
python launcher.py

# Build the executable
python create_exe.py

# Run all tests
python -m unittest discover -s tests -v

# Run a single test file
python -m unittest tests.test_config -v
```

## Architecture

The codebase is layered: **config → core → services → ui**, with `launcher.py` as the orchestrator.

### Core flow

1. `launcher.py` creates `LoLAssistantUI` (main window), `DataDragon` (shared registry), and `WebSocketManager` (LCU connector).
2. `WebSocketManager` runs `lcu_driver.Connector` on a background `asyncio` thread, dispatches typed events (`EVENT_CONNECTED`, `EVENT_PHASE_CHANGE`, `EVENT_CHAMPION_PICKED`, etc.) to the UI callback.
3. When champ select starts, `ChampSelectMixin._champ_select_tick()` is called repeatedly — it reads the LCU session, resolves the effective profile config, then callthroughs `_logic_do_pick()`, `_logic_do_ban()`, `_resolve_spell_selection()`, `_resolve_skin_selection()`, `_set_rune_page()`, etc.
4. The UI schedules Tkinter updates via `root.after()` from the callback.

### Mixin-based composition (critical pattern)

Large classes are split via multiple inheritance. Each mixin uses `self: "ConcreteClass"` type annotations to declare its target class:

| Concrete class | Mixins |
|---|---|
| `WebSocketManager` | `ChampSelectMixin` |
| `LoLAssistantUI` | `MainPreviewMixin`, `MainSkinOverridesMixin` |
| `SettingsWindow` | `SettingsSkinMixin`, `SettingsRunesMixin`, `SettingsHotkeysMixin` |

When modifying champ select logic, work in `ChampSelectMixin` — the mixin methods are called by `WebSocketManager` event handlers.

### Configuration module (`src/config/`)

- `constants.py` — immutable: version, URLs, LCU endpoints, spell maps, themes
- `paths.py` — runtime paths: AppData for user files, TEMP for caches, `resource_path()` for PyInstaller `sys._MEIPASS`
- `settings.py` — `DEFAULT_PARAMS`, `FIRST_LAUNCH_PARAMS`, `load_parameters()` with automatic reset on version mismatch, `_normalize_parameters()` for schema migration
- `logging_config.py` — root logger setup (file + console)

### GameState (`src/core/game_state.py`)

`@dataclass` with persistent fields (survive between games) and transient fields (reset via `reset_between_games()`). Fields marked `metadata={'transient': True}` are cleared between matches. Shared across the app by reference.

### DataDragon (`src/core/datadragon.py`)

Central registry shared by reference everywhere — champion metadata, image cache (`OrderedDict`-based LRU, max 200), skin catalog lookups, rune perk icon paths. Fetches from Riot's Data Dragon API, caches to `%TEMP%`.

### Key LCU endpoints

- `EP_SESSION = "/lol-champ-select/v1/session"` — current champ select state
- `EP_ACTION = "/lol-champ-select/v1/session/actions/{id}"` — perform pick/ban
- `EP_CURRENT_SUMMONER = "/lol-summoner/v1/current-summoner"` — account info
- `EP_GAMEFLOW = "/lol-gameflow/v1/gameflow-phase"` — phase tracking

### PyInstaller compatibility

`resource_path()` resolves bundled vs dev paths via `sys._MEIPASS`. The build script (`create_exe.py`) configures `--add-data`, `--hidden-import`, and `--collect-all` directives.

## Tests

Framework: `unittest` (stdlib). Tests live in `tests/`. There's a `fake_lcu_server.py` that provides an `aiohttp`-based mock LCU for integration tests. The `tests/test_champ_select.py` tests are async and exercise the pick/ban/spell/skin resolution logic against a fake LCU session.

## Commit style

Conventional commits in English: `refactor:`, `fix:`, `feat:`, `chore:`. Messages describe the "why", not the "what".

## Release changelog

An up-to-date changelog grouped by version lives in `track_updates.md` at the repo root. After every meaningful change (feature, fix, refactor, significant cleanup) append a one-line summary to the **current version** bullet list in that file.

**Rules for writing to track_updates.md:**
- Only ever **append** new entries. Never edit, reword, reorder, or delete existing lines.
- Group entries under `## Version X.Y` headings. When a new version is released, create a new heading at the top.
- Each entry is a single-line bullet: `- <verb>: <description>`.
- Keep descriptions short — one line, no more than ~100 characters.
- Use the same conventional-commit verbs as git messages: `feat`, `fix`, `refactor`, `chore`.
- If you are unsure whether a change is "meaningful", include it anyway — it is easier to skim past a minor entry than to notice a missing one.
- When in doubt, ask before writing to the file.
