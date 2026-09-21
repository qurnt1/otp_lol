# Dashboard UI polish

## Scope

- [x] Audit the Dashboard, sidebar, preset cards, responsive CSS, and frontend tests.
- [x] Keep the change frontend-only. Preserve routes, interactions, API behavior, and automation logic.

## Implementation

- [x] Give the sidebar more breathing room while keeping navigation and footer placement intact.
- [x] Stretch the Dashboard columns so Priority, Ban, and Quick Actions read as one balanced block.
- [x] Add clear separation before Automations.
- [x] Split preset card metadata into spell, rune, and skin rows with equal-height, overflow-safe cards.
- [x] Preserve keyboard focus, accessible names, and existing links.

## Validation

- [x] Add or update focused card layout coverage.
- [x] Manually review Dashboard screenshots at desktop and compact sizes before updating snapshots.
- [x] Run frontend tests, typecheck, build, API contract check, E2E tests, and `git diff --check`.
- [x] Perform an independent diff review for scope, dead code, and behavior changes.

Detailed plan archived at `docs/archive/2026-09-dashboard-ui-refresh-plan.md`.
