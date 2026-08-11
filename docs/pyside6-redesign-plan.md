# PySide6 desktop redesign plan

## Objective

Move the desktop presentation to PySide6 and make OTP LOL read as a small League
Companion: one operational Home dashboard, dedicated Presets and Automation pages,
an event-focused History view, and focused Settings/edit dialogs.

## Verified starting point

- The repository already has a toolkit-neutral controller, typed runtime events,
  settings storage, LCU services, tray integration, hotkeys, and Qt dialogs on the
  `codex/future-version` baseline.
- The reference images are stored in `images version pyside6/` and are the visual
  authority for the shell, density, palette, and page family.
- The existing persisted keys `pick_1`, `pick_2`, and `pick_3` remain the contract.

## Implementation phases

1. Convert the desktop imports, signals, decorators, image helpers, and packaging
   metadata from PyQt6 to PySide6. Verify imports and offscreen widget construction.
2. Replace the compact main window with a reusable shell: sidebar, live header, page
   stack, panel primitives, preset cards, toggle rows, activity rows, and feedback.
3. Connect Home, Presets, Automation, History, and Settings to existing controller
   callbacks. Keep runtime work outside the GUI thread and preserve tray/hotkeys.
4. Add focused Qt tests for navigation, signal forwarding, settings refresh, active
   states, and the PySide6 import contract.
5. Render the window offscreen at reference sizes, inspect screenshots, run the full
   Python suite, compileall, Ruff, and the packaged-build metadata checks.

## Acceptance criteria

- No `PyQt6` imports or packaging references remain in the new desktop path.
- Home answers connection, active preset, automation, and health at a glance.
- Preset editing remains discoverable without moving business logic into widgets.
- Connected/offline, empty, disabled, loading, error, and selected states are legible.
- Keyboard focus and accessible names exist for navigation and primary controls.
- Existing backend tests remain green and live-runtime limits are documented.

## Boundaries and rollback

The redesign does not change LCU endpoints, settings keys, automation semantics, or
external website behavior. If a UI migration breaks a runtime contract, revert the
desktop/bootstrap slice while keeping the toolkit-neutral controller and services.
No commit or push is part of this implementation pass.
