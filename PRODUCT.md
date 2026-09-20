# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is a League of Legends player on Windows who wants to prepare champion select once and let a local assistant follow the configured sequence while they queue and play.

## Product Purpose

OTP LOL connects locally to the League client, exposes the current client state, and automates configured actions such as ready-check acceptance, priority picks, bans, summoner spells, rune pages, skins, and returning to the lobby. Success means the player can see what is armed, understand the current client state, and adjust the automation quickly.

## Positioning

OTP LOL is a local-first desktop companion: configuration, cached game assets, history, and the LCU boundary stay on the user's machine while the interface makes the automation sequence visible.

## Operating Context

The assistant runs on Windows in a native pywebview window backed by a local FastAPI server. It communicates with the League Client Update API when the client is available, keeps local settings and history, exposes keyboard shortcuts and system-tray behavior, and uses cached Data Dragon or CommunityDragon assets for visual previews.

## Capabilities and Constraints

- The React/Vite interface is separate from the public `website/` project.
- Existing automation behavior and settings contracts are authoritative; the UI must not imply backend capabilities that are not present.
- The interface must support a dark theme and a light theme.
- Preset previews must retain champion, spell, rune, skin, and website imagery when those assets are available.
- When League is unavailable, the interface must remain useful as a configuration surface and state the offline condition clearly.
- The Statistics page displays the external provider selected in Settings. Native `/api/account` statistics remain a separate backend capability and are not presented as the current Statistics UI.

## Brand Commitments

- Keep the OTP LOL name and the existing Garen application icon/asset family recognizable.
- Preserve the visual link to the former desktop application while allowing a more capable web composition.
- Use French product copy in the interface, with concise, operational wording.

## Evidence on Hand

- `README.md` documents the local assistant's real automation features and Windows/WebView2 runtime.
- `config/images/app/` and `frontend/public/assets/app/` contain the application icon, Garen artwork, gear variants, and skin-mode question marks.
- The API exposes runtime state, presets, champion/spell/rune/skin catalogs, history, updates, and stats links.
- The League client and live WebView2 shell are not available as part of ordinary frontend browser validation.

## Product Principles

- Make the next automated action legible before it happens.
- Keep the configuration close to the real champion-select sequence.
- Show real local state and label unavailable live state honestly.
- Keep the player in control through visible settings and reversible toggles.

## Accessibility & Inclusion

The web surface must remain keyboard navigable, preserve visible focus states, keep status changes announced where relevant, maintain readable contrast in both themes, and avoid relying on color or imagery alone to communicate a setting.

## Account identity

The account surface shows the detected Riot ID, provider region, platform ID, regional routing, and source. Automatic detection is enabled by the positive setting **Détection automatique du compte**; when League is closed, a complete locally saved tuple can keep provider profile links usable.
