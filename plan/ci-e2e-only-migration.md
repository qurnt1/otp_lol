# CI/CD plan for E2E-only testing

## Latest verification update (2026-09-30)

The latest pushed source SHA checked in this update is `7553c697b2e04c37ff6e72037ab977b9e4508e11` on PR #11, compared with `origin/main` at `809d8567ee4755672b812cc63da46488c30a8ce8`. On previous SHA `2143639`, one Windows Playwright run failed a periodic-update boundary at 6,999 ms and two reconnect scenarios remained at “En attente.” The current change adds a realistic timer assertion window and makes the E2E harness acknowledge an LCU event only after a registered handler receives its matching topic and payload. Earlier WebSocket dependency, fake-LCU subscription and narrowly guarded Windows Proactor teardown fixes remain in the branch. The timer and reconnect cases each passed 10/10 locally; full browser 138/138, API 35/35 and full-stack 1/1 passed. See [CPython issue #93821](https://github.com/python/cpython/issues/93821) and [PR #124779](https://github.com/python/cpython/pull/124779) for the prior shutdown workaround context.

Latest local validation: browser **138/138 in 18.3 min**, API **35/35**, full-stack **1/1**, timer repeat **10/10**, reconnect repeats **10/10**, `npm run build`, `npm run api:check`, Python `compileall`, Ruff on `scripts/e2e/app_server.py`, and `node --check scripts/e2e/appServer.mjs` pass. Ruff on `src/desktop/server.py` reports five pre-existing findings; the same five appear on `HEAD`. On GitHub for `7553c69`, the two Windows Playwright jobs were still in progress at the last check; package self-test, frontend build, Python, website/deploy, CodeQL, secret scan and dependency audit succeeded. The Windows package was built and self-tested in CI; interactive WebView2 and a real League client were not validated.

All other reported checks on `7553c69` succeeded, including Windows package self-test, frontend build/typecheck/API type check, Python CI, website CI/deploy, CodeQL, secret scan and dependency audit. The following sections retain evidence from earlier migration snapshots where indicated; they do not supersede this latest check result.

## Scope and repository state

The previous plan snapshot referenced `e5e61c7b39d805656fc56b50391a52c74fa11eae`. The current source is pushed as `7553c697b2e04c37ff6e72037ab977b9e4508e11` on `codex/react-fastapi-webview-migration`, compared with `origin/main` at `809d8567ee4755672b812cc63da46488c30a8ce8`. The E2E changes described above are committed; this documentation update is separate. Python unit, Vitest, website Node tests and unit-only dependencies/scripts/runners have been removed. This does not prove every former assertion has an E2E replacement.

Latest local evidence for this worktree: frontend browser **138/138**, API aggregate **35/35**, full-stack restart/LCU **1/1**, timer and reconnect repeats **10/10 each**. Website **13/13 in an isolated copy** is an earlier result. The native source runner previously reached Settings by mouse, read `presets_enabled=true` and `auto_ban_enabled=false`, then failed because pystray still reported Auto-Ban disabled; cleanup completed, later scenarios did not run. This remains an unconfirmed native UI/tray issue because `GetCursorPos` raised `PermissionError [WinError 5]` under the current desktop. The package self-test passed in CI; its interactive UI was not tested.

## Current GitHub check evidence

The PR #11 check query for `e5e61c7b39d805656fc56b50391a52c74fa11eae` is historical and does not cover the current changes. On `7553c69`, both Windows Playwright jobs were in progress at the last check query; other checks on that SHA (package self-test, static frontend/Python checks, website/deploy, CodeQL, secret and dependency scans) succeeded. The full local Playwright suite and targeted race repeats passed as detailed above.

The historical `e5e61c7` statuses validate only that pushed commit. Local E2E/build results validate this worktree but do not create GitHub checks. The package smoke on `7553c69` used `--self-test --allow-missing-webview2`; it is not proof of interactive WebView2, tray, hotkeys, real League, or installed-EXE UI behavior.

Current remote evidence for `7553c69`: [Windows Playwright job, run 36689129426](https://github.com/qurnt1/otp_lol/actions/runs/36689129426/job/109801891129) and [duplicate PR-triggered job, run 36689122906](https://github.com/qurnt1/otp_lol/actions/runs/36689122906/job/109801869893) were in progress at the last status query. [Package self-test](https://github.com/qurnt1/otp_lol/actions/runs/36689129510/job/109801891345), [Website CI](https://github.com/qurnt1/otp_lol/actions/runs/36689129593/job/109801891628) and [deploy](https://github.com/qurnt1/otp_lol/actions/runs/36689122440/job/109802005744) succeeded. Earlier migration snapshots retain their own run links where indicated.

## Current local jobs and commands

| Workflow | Job/check | Commands in the local tree | Assessment |
|---|---|---|---|
| `.github/workflows/python-ci.yml` | `Python 3.13 on Windows` | Install runtime requirements; `compileall` on shipped Python entry/source; Ruff fatal/progressive checks and format check | Static-quality gate only. No pytest/unittest runner or test directory input remains. |
| `.github/workflows/frontend-ci.yml` | `Frontend CI / Unit and build`; `Frontend CI / Playwright Windows` | Linux: `npm ci`, `npm run api:check`, `npm run typecheck`, `npm run build`. Windows: install runtime + E2E Python requirements, build, install Chromium, `npx playwright test --workers=1`, full-stack `playwright.config.mjs --workers=1`, then `npm run test:e2e:api` | Unit/build check name is retained for required-check stability; it no longer runs unit tests. Local: browser 138/138, full-stack 1/1, API 35/35; timer and reconnect targeted repeats 10/10. On `7553c69`, static/build passed; both Windows Playwright jobs were still in progress at the last query. |
| `.github/workflows/package-smoke.yml` | `Build and self-test Windows package` | Build frontend; create onedir package; run `OTP LOL.exe --self-test --allow-missing-webview2` | Keep as artifact/resource smoke. It is headless and does not prove interactive native UI. |
| `.github/workflows/release.yml` | `Validate tagged source`; `Package Windows executable` | Source gate: install/build frontend, typecheck, Python compileall, `api:check`, browser E2E `--workers=1`, API E2E script. Package gate: PyInstaller build, signing/verification, packaged self-test, installer/signature/checksum/release artifact | No unit runner. The browser and API gates precede package. Current local release workflow has not run on GitHub. |
| `.github/workflows/deploy-website.yml` | Pages build then deploy | Website `npm ci`, production build, `npx playwright test --workers=1` against preview, upload/deploy | `deploy` succeeded on `7553c69`; the isolated local E2E run had passed 13/13 earlier. |
| `.github/workflows/website-ci.yml` | `Website CI / Build and Playwright` | Website `npm ci`, build, `npx playwright test --workers=1` against preview | `Website CI / Build and Playwright` succeeded on `7553c69`; the isolated local E2E run had passed 13/13 earlier. |
| `.github/workflows/security.yml` | dependency audit, CodeQL, secret scan | `pip-audit`, `npm audit --omit=dev`, CodeQL, Gitleaks | Keep. These scans are independent of behavior tests and should use current manifests/lockfiles. |

`frontend/package.json` defines `test:e2e:api` as six sequential Playwright commands, each with `--workers=1`, chained with `&&` for Windows npm shell compatibility:

1. `../scripts/e2e/account-api.config.mjs`
2. `../scripts/e2e/asset-api.config.mjs`
3. `../scripts/e2e/diagnostics-api.config.mjs`
4. `../scripts/e2e/lcu-automation-api.config.mjs`
5. `../scripts/e2e/datadragon-cache-api.config.mjs`
6. `../scripts/e2e/api-contract.config.mjs`

The matching specs live under `scripts/e2e/`. The API configurations start the actual FastAPI application and use controlled fake LCU/Data Dragon fixtures at external integration boundaries. The API contract scenarios include invalid request handling, origins/CORS and WebSocket Origin behavior. The aggregate passed **35/35** on the current local tree.

## Removed unit-only paths

- Python `tests/test_*.py`, `tests/fake_lcu_server.py`, `tests/__init__.py`, and `requirements-test.txt` are absent in the shared local tree. Python CI/release no longer install pytest or run pytest/unittest discovery. Runtime `unittest.mock` use in `src/desktop/self_test.py` remains part of the packaged self-test, not a suite runner.
- Frontend `*.test.ts(x)` files and the Vitest setup were deleted. `frontend/package.json`/lockfile no longer depend on Vitest, jsdom or Testing Library; Vite build config remains. Frontend CI/release do not invoke a unit script.
- `website/test/content.test.mjs` and the `npm test` script were removed after their release-link, screenshot metadata and rendered-asset assertions were moved into `website/e2e/site.spec.ts`.
- `requirements-constraints.txt` no longer pins pytest or the httpx version used only by the removed metadata test. E2E Python requirements are installed explicitly from `scripts/e2e/requirements.txt`.

Historical archives and migration inventories may mention these previous runners while describing the baseline. They must not document them as active local commands. No command using `pytest`, `unittest discover`, Vitest or `node --test` should be active in a manifest/workflow. Keep OpenAPI generation, typecheck, Ruff, compileall, builds, audits, package self-test and Playwright.

## Workflow coverage and residual blind spots

The browser specs use the production frontend build and real FastAPI for ordinary requests. Targeted UI recovery scenarios deliberately install `page.route` handlers for `/api/network/status`, `/api/history`, `/api/champions`, `/api/presets/pick_1`, `/api/assets/skins/86/86013/splash*`, and `/api/settings`. These handlers inject transport/API failures to test the browser response; they are not evidence that FastAPI produces those failures. The six API E2E configs complement those UI simulations using the real server.

Potential green-CI gaps that remain material:

- Current local browser, full-stack and API results are 138/138, 1/1 and 35/35 respectively. Website 13/13 is a separate earlier run. The native source runner remains inconclusive after a WinError 5 under the current desktop and does not validate the tray state.
- GitHub results on `7553c69` show the package, static frontend/Python, website/deploy, CodeQL, secret and dependency checks successful. Both Windows Playwright jobs were still in progress at the last query; do not claim those jobs passed until their conclusions arrive.
- `Frontend CI / Unit and build` is a legacy required-check label with no unit runner now. Renaming it can disrupt branch protection; leave the check name unchanged unless repository rules are intentionally updated.
- Chromium, fake LCU and HTTP fixtures do not exercise an installed League Client, real WebView2, interactive Windows desktop, DPI/multi-monitor behavior, global hotkeys, tray, native dialogs or providers. The native runner is not a validated CI gate.
- Package `--self-test --allow-missing-webview2` does not launch the actual interactive UI. A successful PyInstaller build and self-test can coexist with an EXE-only WebView/resource/permission failure.
- The website workflows use direct `npx playwright test --workers=1` because the npm invocation used during verification ran two workers. The 13/13 isolated-copy result does not validate either workflow on GitHub.
- A green `api:check`/typecheck/build proves generated types and compilability, not that every frontend error path matches backend behavior.

## E2E-only acceptance gates

1. Preserve the current 138/138 browser, 35/35 API and 1/1 full-stack results as local evidence. The latest browser result is after the teardown/dependency changes.
2. Keep all six API configs in the serial `npm run test:e2e:api` command and workflow. The current aggregate is 35/35; repeat only if later changes affect these specs, harness or workflow.
3. Preserve the 1/1 full-stack result; repeat if later changes affect restart, reconnect, persistence, egress or cleanup.
4. Execute static gates on the final tree: API generation, TypeScript, Vite builds, Python compileall/Ruff, dependency audits and package self-test. These do not replace E2E results.
5. Website build/E2E passed 13/13 in an isolated copy. Run both workflows on an intended remote SHA before treating GitHub checks as green.
6. Resolve the confirmed tray mismatch: with `presets_enabled=true` and `auto_ban_enabled=false` from the Dashboard, the native menu exposes Auto-Ban as disabled. Rerun the full native source scenario; its current failure prevents later assertions from executing. Keep packaged-EXE UI coverage separate until the interactive runner exercises the package itself.
7. Check GitHub Actions at the new pushed SHA only after publication is separately authorized. A passing old SHA is never substituted for current checks.

## Validation state and next actions

The latest local run passed browser 138/138, API 35/35, full-stack 1/1, and timer/reconnect repeats 10/10. The frontend production build, generated API consistency, Python compileall, Node syntax check and Ruff on the E2E harness pass. Ruff on `src/desktop/server.py` still reports the same five findings present on base `HEAD`. On `7553c69`, all reported GitHub checks except the two Windows Playwright jobs had passed at the last query; package self-test is not interactive EXE validation. Real WebView2, desktop tray interactions and a real League client remain untested.
