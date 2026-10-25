# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

OTP LOL v11.1 — a Windows desktop assistant for League of Legends champion select automation. Connects to the LCU API via `lcu-driver`, auto-accepts queues, pre-picks/locks champions, bans, sets summoner spells, applies rune pages, and selects skins. Built with Python 3.13, FastAPI, React, and pywebview, then shipped as a PyInstaller executable.

## Commands

```bash
# Install runtime deps
pip install -r requirements.txt

# Install build deps (includes runtime)
pip install -r requirements-build.txt

# Run the app (dev)
cd frontend
npm ci
npm run build
cd ..
python launcher_web.py

# Build the executable
python create_exe.py

# Run browser E2E checks (after installing Python runtime and E2E dependencies)
python -m pip install -c requirements-constraints.txt -r requirements.txt -r scripts/e2e/requirements.txt
cd frontend
npm ci
npm run api:check
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e -- --workers=1
npx playwright test --config ../scripts/e2e/playwright.config.mjs --workers=1
npm run test:e2e:api
```

## Architecture

The codebase is layered: **config → core → services → api/domain/lcu → desktop**, with `launcher_web.py` as the orchestrator.

### Core flow

1. `launcher_web.py` creates the local FastAPI app, `DataDragon` (shared registry), and the pywebview desktop shell.
2. `WebSocketManager` runs `lcu_driver.Connector` on a background `asyncio` thread, dispatches typed events (`EVENT_CONNECTED`, `EVENT_PHASE_CHANGE`, `EVENT_CHAMPION_PICKED`, etc.) to the event broker.
3. When champ select starts, `ChampSelectMixin._champ_select_tick()` is called repeatedly — it reads the LCU session, resolves the effective profile config, then callthroughs `_logic_do_pick()`, `_logic_do_ban()`, `_resolve_spell_selection()`, `_resolve_skin_selection()`, `_set_rune_page()`, etc.
4. FastAPI exposes runtime state and events to the React frontend through HTTP and WebSocket routes.

### Mixin-based composition (critical pattern)

Large classes are split via multiple inheritance. Each mixin uses `self: "ConcreteClass"` type annotations to declare its target class:

| Concrete class | Mixins |
|---|---|
| `WebSocketManager` | `ChampSelectMixin` |

When modifying champ select logic, work in `ChampSelectMixin` — the mixin methods are called by `WebSocketManager` event handlers.

### Configuration module (`src/config/`)

- `constants.py` — immutable: version, URLs, LCU endpoints, spell maps, themes
- `paths.py` — runtime paths: AppData for user files, TEMP for caches, `resource_path()` for PyInstaller `sys._MEIPASS`
- `settings.py` — `DEFAULT_PARAMS`, `FIRST_LAUNCH_PARAMS`, `load_parameters()` with automatic reset for missing, invalid, or unsupported files, `_normalize_parameters()` for the current schema only
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

`resource_path()` resolves bundled vs dev paths via `sys._MEIPASS`. The build script (`create_exe.py`) configures `--add-data` and `--hidden-import` directives.

## Commit style

Conventional commits in English: `refactor:`, `fix:`, `feat:`, `chore:`. Messages describe the "why", not the "what".
