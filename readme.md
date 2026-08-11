<p align="center">
  <a href="./readme.md"><img src="https://img.shields.io/badge/version-11.0-2f81f7" alt="Version"></a>
  <a href="./requirements.txt"><img src="https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white" alt="Python"></a>
  <a href="https://www.leagueoflegends.com/"><img src="https://img.shields.io/badge/game-League%20of%20Legends-C28F2C" alt="Game"></a>
  <a href="./readme.md"><img src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white" alt="Platform"></a>
</p>

# OTP LOL

OTP LOL is a local Windows assistant for League of Legends. It connects to the local League Client Update interface and automates only the actions enabled in the app.

Current project version: `11.0`.

## Version 11.0 Highlights

- Complete preset rows for champions, summoner spells, rune pages, and skins.
- More reliable owned-skin validation and fixed/random skin selection.
- Rune-page confirmation and retry behavior during champion select.
- Local action history, release checks, and safer runtime shutdown.

## Features

- Automatically accept ready checks.
- Try three ordered champion presets, including pre-pick and lock-in recovery.
- Ban one configured champion.
- Apply two summoner spells, a rune page, and a fixed or random skin for the preset that was actually selected.
- Optionally return to the lobby after a game.
- Detect the current Riot ID and region, or use manual values.
- Open OP.GG, DeepLOL, DPM.LOL, League of Graphs, or Porofessor.
- Keep local action history, configurable global shortcuts, a system tray, and update notifications.
- Preserve settings in a local TOML file with schema migration and atomic writes.

The current preset model is global. The assigned role helps filter and sort champion choices, but the repository does not currently implement separate per-role profiles.

## Desktop interface

The desktop application is implemented with PySide6:

- `QApplication` lifecycle and thread-safe Qt event bridge
- main window and settings tabs
- champion, summoner-spell, rune, and skin dialogs
- Qt system tray and Qt Multimedia ready-check sound
- action-history and update dialogs
- dark and light themes

Global hotkeys still use the `keyboard` package because Qt shortcuts are not system-wide when the app is unfocused. Their callbacks are marshalled back to the Qt GUI thread.

## Website

The React/Vite website lives in [`website`](./website). It has its own visual identity, bilingual content, deterministic GitHub release selection, and responsive layouts.

```bash
cd website
npm install
npm test
npm run build
```

## Requirements

- Windows
- Python 3.13
- League of Legends installed for live LCU features
- Node.js only when developing the website

PySide6 reports `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` in its installed package metadata. This repository currently has no license file. Before distributing the rewritten executable, choose the applicable project license and add the corresponding legal files. This is a release blocker, not a runtime limitation.

## Install and run from source

```bash
git clone https://github.com/qurnt1/otp_lol.git
cd otp_lol
python -m pip install -r requirements.txt
python launcher.py
```

Startup order is intentional:

1. enforce one running process;
2. load and migrate settings;
3. construct the Qt interface and connect event receivers;
4. load Data Dragon metadata in a worker;
5. start the LCU runtime only after metadata is ready;
6. check GitHub release metadata in parallel.

This prevents champion-select automation from racing an empty champion catalog and keeps startup responsive.

## Configuration and local data

- Settings: `%APPDATA%\OTP LOL\parameters.toml`
- Legacy settings backup: `%APPDATA%\OTP LOL\parameters.json.bak`
- Action history: `%APPDATA%\OTP LOL\history.json`
- Logs: `%APPDATA%\OTP LOL\app_debug.log`
- Data Dragon and image caches: `%TEMP%\otp_lol_*`

App-version changes no longer erase readable user preferences. `settings_schema_version` controls migrations independently from `config_version`.

## Default shortcuts

- `Alt + C`: show or hide OTP LOL
- `Alt + P`: open the configured live-game website

Both shortcuts are configurable. They must be different.

## Build the Windows executable

```bash
python -m pip install -r requirements-build.txt
python create_exe.py
```

The PyInstaller script creates `OTP LOL.exe` in the repository root. It includes the `config` assets, PySide6 plugins, Qt Multimedia, LCU dependencies, and optional desktop-shortcut creation.

Do not publish a new binary until the PySide6 license decision above is resolved and the packaged smoke checks pass.

## Architecture

```text
otp_lol/
|-- launcher.py                 # Qt bootstrap and process lifecycle
|-- create_exe.py               # PyInstaller release build
|-- src/
|   |-- application/            # toolkit-neutral controller and settings store
|   |-- config/                 # schema, paths, constants, logging
|   |-- core/                   # Data Dragon, LCU, game state, typed events
|   |-- desktop/                # complete PySide6 presentation and integrations
|   |-- services/               # pure/shared URLs, history, runes, skins, updates
|   `-- atomic_io.py
|-- config/                     # bundled sound, icons, role data
|-- website/                    # React/Vite distribution website
|-- docs/
`-- tests/
```

The core never imports the desktop package. Runtime workers emit immutable event objects through `CoreEventBridge`; widgets are updated only on the Qt GUI thread.

## Tests and verification

Install developer tooling:

```bash
python -m pip install -r requirements-dev.txt
```

Run the validation suite:

```bash
python -m ruff check launcher.py src tests
python -m pytest -q
python -m unittest discover -s tests -v
python -m compileall -q launcher.py create_exe.py src tests
```

The tests cover settings migration and concurrency, typed core events, fake-LCU flows, champion-select behavior, skin/rune helpers, Qt thread delivery, desktop controls, update metadata, history, and release packaging metadata.

## Troubleshooting

### League client not detected

- Confirm that the League client is running on the same Windows session.
- Check `%APPDATA%\OTP LOL\app_debug.log`.
- A transient process scan failure does not trigger the close-on-client-exit timer.

### Tray or hotkeys unavailable

- When no system tray is available, closing the main window exits the app.
- If global hooks cannot be registered, all actions remain available from the window.

### Rune or skin data unavailable

- Rune pages and owned-skin inventory require an active local LCU connection.
- Public champion and skin metadata uses Riot Data Dragon and CommunityDragon network resources.

OTP LOL is not endorsed by Riot Games.
