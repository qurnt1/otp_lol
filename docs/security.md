# Security model

OTP LOL is a local desktop application. The security boundary is designed around localhost traffic, untrusted external responses, and user-controlled settings.

## Local API

- CORS is limited to the development frontend origins.
- WebSocket connections validate `Origin` before accepting external browser origins.
- Responses include CSP, `X-Content-Type-Options`, and `Referrer-Policy` headers.
- Request schemas reject unknown fields and validate providers, regions, Riot IDs, hotkeys, spells, and preset conflicts.

## External requests

- `/api/assets` accepts only known Data Dragon or CommunityDragon relative asset paths.
- Absolute URLs, protocol-relative URLs, query strings, fragments, traversal, and unknown path prefixes are rejected.
- Image downloads have timeouts, size limits, content-type checks, format checks, and decode validation.
- Native external links are restricted to the configured HTTPS provider allowlist.

## Statistics embeds and WebView bridge

`/api/links/stats` and `/api/links/live` build URLs from a provider selected for that page, a validated Riot ID, and a valid region. Automatic account detection uses only the currently connected League snapshot; manual values are used only when manual mode is enabled. The frontend never accepts an arbitrary profile URL. Account frames use the `STATS_FRAME_ORIGINS` allowlist, which currently contains only `https://www.deeplol.gg`; `LIVE_FRAME_ORIGINS` is intentionally empty until a provider is validated for live embedding. Other sites use the explicit external-browser fallback. The account allowlist reflects observed probes, not a claim about every profile or future response: DeepLOL returned 200 without displayed XFO/CSP headers; the local DPM GET returned a Cloudflare 403 with SAMEORIGIN while another 16/09/2026 sample returned 308 then 200; OP.GG returned 404 with SAMEORIGIN; LeagueOfGraphs returned a 403 challenge with SAMEORIGIN/CSP. No response is bypassed or rewritten.

The DeepLOL frame uses `sandbox="allow-scripts allow-same-origin allow-forms"` so its own origin-based requests/storage are not forced into an opaque origin. It does not receive popup or top-navigation permissions, and `referrerPolicy` is `no-referrer`. The external action stays visible. A timeout or frame error shows an explicit fallback; a browser `load` event is not treated as proof that the provider rendered successfully.

An isolated WebView2 153.0.4234.32 / pywebview 6.1 check on 2026-09-17 confirmed that a cross-origin provider iframe can see `chrome.webview.postMessage`. Sending an unknown, side-effect-free bridge method did not produce a pywebview host-dispatch log entry. This matches WebView2's documented split between top-level `CoreWebView2.WebMessageReceived` and frame-level `CoreWebView2Frame.WebMessageReceived`; pywebview subscribes only to the top-level event ([WebView2 frame messaging](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/frames)). This is evidence for the tested runtime and harness, not every provider/runtime combination. Repeat the source/bridge check after WebView2 or pywebview upgrades. Do not expand the provider allowlist based on the bridge test.

The 2026-09-17 live-page probe used a deliberately nonexistent Riot ID, so it did not verify a real in-game page: DeepLOL returned HTTP 200 without displayed XFO/CSP headers but ultimately showed an unregistered-summoner page; the app's 12-second unconfirmed-render fallback appeared as designed. Porofessor and DPM returned HTTP 403 with `SAMEORIGIN`, while OP.GG returned HTTP 404 with `SAMEORIGIN` for that same fake ID. `LIVE_FRAME_ORIGINS` therefore remains empty; do not bypass frame restrictions or claim live embedding works until a real in-game account and the final app flow have been checked.

## Persistence and updates

Settings use schema version 6, atomic writes, and recoverable backups when a file is invalid or uses another schema. Missing settings are created with defaults on first launch. Older settings are not migrated; imports require the current schema version. Release updates require the exact `OTP-LOL-Setup.exe` asset and the matching `OTP-LOL-Setup.exe.sha256` asset. The website displays the release version, date, and checksum when GitHub metadata is available.

The project does not claim Authenticode signing yet. A signed Windows installer is the next integrity improvement for broad public distribution.
