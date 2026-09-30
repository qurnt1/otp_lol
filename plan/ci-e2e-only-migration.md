# CI/CD plan for E2E-only testing

## Latest verification update (2026-09-30)

The latest pushed code SHA is `205d05d253bc39dff3aea68fcaea52f72cbbc236` on PR #11, compared with `origin/main` at `809d8567ee4755672b812cc63da46488c30a8ce8`. The `7553c69` changes fixed a Windows timer boundary (6,999 ms) and LCU reconnect-event acknowledgements; both targeted cases passed 10/10 locally. A later GitHub rerun on docs-only SHA `89d8ac4` failed 1/138 at DIAG-01: `clock.pauseAt(new Date())` could target a time already passed in the browser clock. Commit `205d05d` adds a 1 s future margin. DIAG-01 then passed 10/10 and the browser suite passed 138/138 locally in 18.4 min. On GitHub for `205d05d`, one Windows Playwright job passed browser 138/138, full-stack 1/1 and API 35/35; its duplicate passed 137/138 and failed only the update-timer boundary assertion. The current unpushed timer recalibration passes 10/10 targeted and the full browser suite passes 138/138 in 18.2 min. See [CPython issue #93821](https://github.com/python/cpython/issues/93821) and [PR #124779](https://github.com/python/cpython/pull/124779) for prior shutdown-workaround context.

Latest local validation: browser **138/138 in 18.2 min**, DIAG-01 repeat **10/10**, timer repeat **10/10**, API **35/35**, full-stack **1/1**, reconnect repeat **10/10**, build, `api:check`, `compileall`, Ruff on `scripts/e2e/app_server.py`, and `node --check scripts/e2e/appServer.mjs` pass. Ruff on `src/desktop/server.py` reports five pre-existing findings; the same five appear on `HEAD`. On GitHub for `205d05d`, one duplicate Windows Playwright job passed browser, full-stack and API phases; the other failed only the timer boundary assertion. Package self-test, frontend build, Python, website/deploy, CodeQL, secret scan and dependency audit succeeded. Interactive WebView2 and a real League client were not validated.

All non-Playwright checks on `205d05d` succeeded, including Windows package self-test, frontend build/typecheck/API type check, Python CI, website CI/deploy, CodeQL, secret scan and dependency audit. Of the two duplicate Windows Playwright jobs, one passed all phases and one failed only the old timer boundary assertion. The following sections retain evidence from earlier migration snapshots where indicated.

## Scope and repository state

The previous plan snapshot referenced `e5e61c7b39d805656fc56b50391a52c74fa11eae`. The current code is pushed as `205d05d253bc39dff3aea68fcaea52f72cbbc236` on `codex/react-fastapi-webview-migration`, compared with `origin/main` at `809d8567ee4755672b812cc63da46488c30a8ce8`. This documentation update is separate. Python unit, Vitest, website Node tests and unit-only dependencies/scripts/runners have been removed. This does not prove every former assertion has an E2E replacement.

Latest local evidence for this worktree: frontend browser **138/138**, API aggregate **35/35**, full-stack restart/LCU **1/1**, timer and reconnect repeats **10/10 each**. Website **13/13 in an isolated copy** is an earlier result. The native source runner previously reached Settings by mouse, read `presets_enabled=true` and `auto_ban_enabled=false`, then failed because pystray still reported Auto-Ban disabled; cleanup completed, later scenarios did not run. This remains an unconfirmed native UI/tray issue because `GetCursorPos` raised `PermissionError [WinError 5]` under the current desktop. The package self-test passed in CI; its interactive UI was not tested.

## Current GitHub check evidence

The PR #11 check query for `e5e61c7b39d805656fc56b50391a52c74fa11eae` is historical. On `89d8ac4`, Windows Playwright failed 137/138 because DIAG-01 attempted to pause the browser clock at a time already past. The fix is in `205d05d`. Its duplicate Playwright jobs completed: one passed browser 138/138, full-stack 1/1 and API 35/35; the other failed the update-timer assertion after 137/138 browser tests. The current local recalibration passes the timer scenario 10/10 and browser 138/138. Other checks on `205d05d` (package self-test, static frontend/Python checks, website/deploy, CodeQL, secret and dependency scans) succeeded.

The historical `e5e61c7` statuses validate only that pushed commit. Local E2E/build results validate this worktree but do not create GitHub checks. The package smoke on `205d05d` used `--self-test --allow-missing-webview2`; it is not proof of interactive WebView2, tray, hotkeys, real League, or installed-EXE UI behavior.

Current remote evidence for `205d05d`: [Windows Playwright job, run 36695679852](https://github.com/qurnt1/otp_lol/actions/runs/36695679852/job/109822957204) failed only the timer assertion after 137/138 browser tests; [duplicate PR-triggered job, run 36695669611](https://github.com/qurnt1/otp_lol/actions/runs/36695669611/job/109822925776) passed browser 138/138, full-stack 1/1 and API 35/35. The local timer recalibration is not on GitHub yet. Package self-test, [Website CI](https://github.com/qurnt1/otp_lol/actions/runs/36695679920/job/109822956987), Python and security checks succeeded. The previous [DIAG-01 failure log](https://github.com/qurnt1/otp_lol/actions/runs/36690732429/job/109807068531) is on `89d8ac4`. Earlier migration snapshots retain their own run links where indicated.

## Current local jobs and commands

| Workflow | Job/check | Commands in the local tree | Assessment |
|---|---|---|---|
| `.github/workflows/python-ci.yml` | `Python 3.13 on Windows` | Install runtime requirements; `compileall` on shipped Python entry/source; Ruff fatal/progressive checks and format check | Static-quality gate only. No pytest/unittest runner or test directory input remains. |
| `.github/workflows/frontend-ci.yml` | `Frontend CI / Unit and build`; `Frontend CI / Playwright Windows` | Linux: `npm ci`, `npm run api:check`, `npm run typecheck`, `npm run build`. Windows: install runtime + E2E Python requirements, build, install Chromium, `npx playwright test --workers=1`, full-stack `playwright.config.mjs --workers=1`, then `npm run test:e2e:api` | Unit/build check name is retained for required-check stability; it no longer runs unit tests. Local: browser 138/138, full-stack 1/1, API 35/35; timer, reconnect and DIAG-01 targeted repeats 10/10. On `205d05d`, static/build passed; one Windows Playwright job passed all phases and the duplicate failed only the timer boundary assertion. The local timer fix now passes the full browser suite. |
| `.github/workflows/package-smoke.yml` | `Build and self-test Windows package` | Build frontend; create onedir package; run `OTP LOL.exe --self-test --allow-missing-webview2` | Keep as artifact/resource smoke. It is headless and does not prove interactive native UI. |
| `.github/workflows/release.yml` | `Validate tagged source`; `Package Windows executable` | Source gate: install/build frontend, typecheck, Python compileall, `api:check`, browser E2E `--workers=1`, API E2E script. Package gate: PyInstaller build, signing/verification, packaged self-test, installer/signature/checksum/release artifact | No unit runner. The browser and API gates precede package. Current local release workflow has not run on GitHub. |
| `.github/workflows/deploy-website.yml` | Pages build then deploy | Website `npm ci`, production build, `npx playwright test --workers=1` against preview, upload/deploy | `deploy` succeeded on `205d05d`; the isolated local E2E run had passed 13/13 earlier. |
| `.github/workflows/website-ci.yml` | `Website CI / Build and Playwright` | Website `npm ci`, build, `npx playwright test --workers=1` against preview | `Website CI / Build and Playwright` succeeded on `205d05d`; the isolated local E2E run had passed 13/13 earlier. |
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
- GitHub results on `89d8ac4` show one browser test failure: DIAG-01 used `pauseAt(new Date())` and raced past its target. The 1 s future margin fix is on `205d05d`; one CI duplicate passed every phase and the other failed only the old update-timer boundary assertion. The local timer recalibration passes 10/10 and the current browser suite passes 138/138. Other current checks passed.
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

The latest local run passed browser 138/138 in 18.2 min, DIAG-01 and timer 10/10, API 35/35, full-stack 1/1 and reconnect repeats 10/10. The frontend build, generated API consistency, Python compileall, Node syntax check and Ruff on the E2E harness pass. Ruff on `src/desktop/server.py` still reports the same five findings present on base `HEAD`. On `205d05d`, all non-Playwright checks passed; one Windows Playwright job passed every phase and its duplicate failed only the old timer assertion. The local correction has not yet been pushed; package self-test is not interactive EXE validation. Real WebView2, desktop tray interactions and a real League client remain untested.
