# OTP LOL — Changelog

## Version 11.0

- feat: enable presets for Clash (700) and Practice Tool via gameMode check
- feat: detect unsupported queue during Lobby/Matchmaking phase via /lol-lobby/v2/lobby
- feat: normalize skin and rune picker UX with shared colors, messages, and fetch buttons
- fix: distinguish LCU-not-detected from skin-not-owned in skin confirmation dialog
- fix: align rune and skin picker layout structure and status-label position
- refactor: extract picker colors and status messages into shared _picker_common module
- refactor: extract skin mode helpers into src/services/skin_modes
- chore: add track_updates.md and CLAUDE.md rules for append-only changelog
- feat: add Fetch skins button to skin picker with concurrent-call guard
- feat: replace hardcoded rune empty message with picker_empty_message
- chore: add debug logging for session gameConfig and lobby queue detection
- fix: add Practice Tool queue IDs (3100 blind, 3110 draft) and fallback to lobby queue in champ select
- feat: fire spells and runes as soon as prepick hover is confirmed, before ban/pick
- feat: scan session actions for prepick detection when myTeam does not yet reflect the hover
- feat: poll lobby during ChampSelect phase so queue ID is available on the first tick
