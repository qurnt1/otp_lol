# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

The product surface is a native Windows desktop application built with PySide6. The
platform value follows the design-tool schema; this is not a web interface.

## Users

The primary user is a League of Legends player using OTP LOL during normal desktop
play. They need to know whether League is connected, which preset will run, which
automations are enabled, and whether the last action succeeded.

## Product Purpose

OTP LOL connects to the local League Client Update interface and automates only the
actions the user enables: ready checks, champion select presets, bans, summoner
spells, runes, skins, and optional play-again behavior.

## Positioning

OTP LOL is a local-first League companion. It keeps configuration and action history
on the user's machine and uses the local client interface instead of requiring an
OTP LOL account or hosted profile.

## Operating Context

The user keeps OTP LOL open beside or over League, occasionally checks the Home
dashboard, edits presets between games, and relies on live status during queue and
champion select. Tray controls and global shortcuts remain available when the main
window is hidden.

## Capabilities and Constraints

- Preserve the existing `config`, `core`, and `services` behavior and the persisted
  `pick_1`, `pick_2`, and `pick_3` keys.
- Keep LCU work, network work, and metadata loading outside the Qt GUI thread.
- Use PySide6 for the desktop presentation and maintain Windows/PyInstaller support.
- Treat live League, LCU, tray, hotkey, DPI, and packaged-runtime behavior as manual
  validation boundaries when the real environment is unavailable.
- The current preset model is global; separate role profiles are not invented here.

## Brand Commitments

The product name is OTP LOL. The supplied reference images in
`images version pyside6/` establish a dark midnight-blue companion UI, restrained
gold action color, green connection state, compact system typography, and a quiet
League-inspired visual language without copying the Riot client.

## Evidence on Hand

- Existing runtime source under `src/application`, `src/core`, and `src/services`.
- Existing PyQt6 presentation under `src/desktop`, used as the migration baseline.
- Reference dashboard and screen-family images under `images version pyside6/`.
- Existing config assets under `config/images/` for champions, roles, websites, and
  application branding.
- No fabricated user metrics, testimonials, commercial claims, or cloud features.

## Product Principles

- Show live operational truth before configuration detail.
- Keep configuration discoverable without putting every option on Home.
- Preserve local control, transparent states, and recoverable settings.
- Make the next action obvious during queue and champion select.

## Accessibility & Inclusion

The desktop UI must remain keyboard navigable, expose accessible names for controls,
keep state readable without color alone, preserve visible focus, and avoid motion that
blocks task completion.
