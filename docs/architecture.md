# Architecture

## Runtime boundary

`launcher_web.py` starts the native desktop shell and the local FastAPI application. `pywebview` hosts the compiled `frontend/dist` output in WebView2. The Python runtime owns LCU communication, automation, settings persistence, history, and asset retrieval.

The React application talks to the backend through typed HTTP endpoints and a WebSocket event stream. Runtime status events carry an action key, parameters, and severity; the frontend owns their localized presentation in `fr.ts`. The sidebar shows League connection, account, and version; the Dashboard shows the current phase and the latest automation status. `useHashRoute` owns page and settings-section routes (including browser history), while `runtimeStore` owns the live runtime snapshot and latest status. `#statistics` displays the external provider selected in Settings through `/api/links/stats`; it does not render the native `/api/account` statistics endpoints. `#live` and `/api/links/live` use `preferred_hotkey_site` for in-game links. Account and live iframe origins have separate allowlists.

## Main layers

- `src/api/`: HTTP and WebSocket boundary, request validation, and response schemas.
- `src/config/`: paths, constants, first-launch defaults, normalization, import/export, and atomic persistence.
- `src/core/`: champion select, Data Dragon catalog access, and website-region mapping.
- `src/lcu/`: bounded local `LcuClient`, versioned static-data snapshots, normalized account statistics, diagnostics buffers, runtime snapshots, and event publication.
- `src/integrations/`: external providers such as CommunityDragon.
- `src/desktop/`: pywebview bridge, native links, self-tests, and window lifecycle.
- `frontend/src/api/`: HTTP client, generated OpenAPI types, and WebSocket event handling.
- `frontend/src/components/`: shared shell and UI primitives.
- `frontend/src/features/`: the dashboard, presets, statistics, history, and settings views with feature-local components.
- `website/`: separate public Vite site. It is not the desktop frontend.

## Data flow

```text
League Client / LCU
        ↓
LcuClient
  ├── static data and local asset lookup
  ├── normalized account statistics
  ├── diagnostics (requests + existing events)
  └── existing automation runtime
        ↓
typed FastAPI endpoints + /api/events
        ↓
React shell and pages
```

The `/api/bootstrap` response contains cached champion, spell, skin, and ban previews for the first dashboard paint. It does not load remote catalogs or the LCU skin inventory. Full catalogs are fetched only when their editor opens.

Dashboard skin-mode controls update the matching `pick_slots[pick_N].skin_mode` preset value directly. There is no separate dashboard-only override. Settings require the exact current schema; there is no schema migration. A missing, invalid, or unsupported settings file is backed up when present and replaced by first-launch defaults and editable starter presets. Factory reset restores those defaults and starter presets, with automation switches off.

Detected account links share one resolver across the Stats API, live-provider API, and native provider window. Auto mode uses a complete connected identity first and falls back to the last validated Riot ID/region/platform tuple only when the LCU is disconnected. Manual mode remains separate. The detected identity is installation-local, excluded from settings export/import, cleared by factory reset, and retained when presets alone are reset or cleared.

`src/domain/providers.py` is the canonical provider registry for identifiers, labels, logos, homepages, supported profile/live pages, URL builders, embed eligibility, host allowlists, and ordering. Settings validation, API catalog options, account/live URL generation, and the native desktop allowlist derive from it.

Provider pages that cannot be embedded naturally can open in a second top-level pywebview window. Python builds the URL from the selected provider and account, validates HTTPS and the provider host, and creates the window without the `DesktopBridge` JavaScript API. This reuses the existing WebView2 runtime and installer, with less host work than replacing pywebview with a native WinForms/WPF/WinUI WebView2 shell. It is also more integrated than opening only the system browser. It does not put provider content in a separate process or security sandbox, and pywebview's documented high-level events do not provide a reliable pre-navigation hook to block every top-level redirect. Popup links are sent to the system browser; top-level provider navigation remains subject to that limitation.

The League Client is the normal source for champion, spell, perk, item, map, and queue static data. Validated snapshots are persisted under `%APPDATA%\\OTP LOL\\cache\\lcu` and kept across disconnects; catalogues are loaded on demand, while refresh follows LCU connection in the background. Data Dragon and CommunityDragon remain recovery fallbacks for unavailable static data, individual assets, skins, and rune artwork. Static refreshes, external responses, image reads, and account snapshots are bounded and validated. `GET /api/game-data/status` reports source and availability.

Typed native account-statistics endpoints exist under `/api/account`; they are not currently the Statistics page UI. That page uses the external provider links from `/api/links/stats`, while `/api/links/live` targets the configured live-provider page. The `/api/account` endpoints separately cache sanitized DTO snapshots under `%APPDATA%\\OTP LOL\\cache\\account`; an offline pointer stores only a SHA-256 identity hash, not a raw PUUID or LCU credential, and cached results are marked stale.

The diagnostics page is reachable from Settings > Advanced, not the main sidebar. It reads bounded request/event/error buffers from the existing runtime connection, and its test action can issue only predefined LCU GET requests. The latest normalized endpoint results remain available after frontend navigation and are included in the report export. Event payload JSON is shown only in its **Voir JSON** drawer. It does not expose an arbitrary LCU proxy or create a second event connection.

## Frontend styling

The desktop UI uses the shared stylesheet in `frontend/src/styles/globals.css`. Tailwind is available through the Vite plugin for the few utility-level cases that need it, while the application layout and tokens remain in the inspectable stylesheet.

## Account identity and regional routing

`src/config/regions.py` is the shared normalization boundary for platform IDs, provider regions, and Riot regional routing. `detect_account_routing` checks platform configuration, RSO authorization, region-locale endpoints, then command-line arguments. It does not infer a platform from locale or `webRegion`. The runtime stores the complete tuple with its source and exposes it through `/api/account/identity`; provider links and account statistics consume the same resolver.

The tuple is persisted only when Riot ID, provider region, and platform ID are consistent. Repeating the same tuple does not publish a duplicate `account_identity_updated` event.
The identity response keeps the account source (`connected`, `saved`, `manual`, `unavailable`) separate from `routing_source`, which records the LCU source that supplied the platform (`platform_config`, `rso_auth`, `region_locale`, or `command_line_args`).
