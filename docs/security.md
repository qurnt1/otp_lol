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

## Persistence and updates

Settings use atomic writes and recoverable backups when a file is invalid. Release updates require the exact `OTP-LOL-Setup.exe` asset and the matching `OTP-LOL-Setup.exe.sha256` asset. The website displays the release version, date, and checksum when GitHub metadata is available.

The project does not claim Authenticode signing yet. A signed Windows installer is the next integrity improvement for broad public distribution.
