# Provider persistence + Dashboard card polish

## Audit

- [x] Inspect pywebview startup, application paths, main-window geometry, provider lifecycle, card previews, CSS, and tests.
- [x] Confirm pywebview 6.1 defaults to private storage and providers currently use fixed `1100x760` creation bounds.
- [x] Confirm the main `WebViewWindow.geometry()` method is the existing geometry source of truth.

## WebView and providers

- [x] Use one stable OTP LOL WebView profile with private mode disabled.
- [x] Synchronize Stats and Live geometry at user show/open time, including maximized state and monitor-safe coordinates.
- [x] Preserve hidden preload, reuse, focus, and shutdown behavior.
- [x] Add persistent-storage, normal-geometry, maximized-geometry, and preload regression tests.

## Dashboard cards

- [x] Remove the redundant configured-card `Prêt` subtitle.
- [x] Make rune assets borderless and transparent without changing summoner styling.
- [x] Keep the skin splash in the art area and use the champion square icon in the SKIN row.
- [x] Cover fixed, none, fallback, subtitle, and rune styling cases.

## Validation

- [x] Update relevant documentation and tracking.
- [x] Run targeted Python/frontend tests, then the complete suites, build, API check, compileall, Ruff, and `git diff --check`.
- [x] Perform an independent final diff review and document the Windows-only cookie/geometry smoke tests if unavailable.

Detailed plan archived at `docs/archive/2026-09-provider-persistence-geometry-card-plan.md`.
