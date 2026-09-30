# CI/CD plan for E2E-only testing

## Latest verification update (2026-09-30)

The latest pushed source SHA checked before this update is `23d14d51bc49fc4bc86c8f45ce21244bdc73c61c` on PR #11, compared with `origin/main` at `809d8567ee4755672b812cc63da46488c30a8ce8`. Both Windows Playwright executions failed: 121/138 and 115/138. Logs show Uvicorn 0.41 installed without `websockets` or `wsproto`, causing 404 for `/api/events` despite the FastAPI route; the clean-install manifests now include `websockets~=15.0`, constrained to `15.0.1`. The fake-LCU setup now waits for its initial WebSocket subscription. A third, independent teardown problem was traced to Windows Proactor cleanup after `ConnectionResetError`: CPython skips transport detach after the socket shutdown raises, leaving Uvicorn in `Server.wait_closed()`. A narrowly guarded wakeup is in `src/desktop/server.py`; it requires a closed listener, zero Uvicorn connections/tasks and only already-closing Proactor transports, then rechecks those conditions on the loop. Uvicorn still proceeds through FastAPI lifespan shutdown. See [CPython issue #93821](https://github.com/python/cpython/issues/93821) and [PR #124779](https://github.com/python/cpython/pull/124779); remove the workaround when supported Python releases detach reset clients correctly.

Latest local validation of the worktree: browser **138/138 in 18.3 min**, API **35/35**, full-stack **1/1**, repeated theme teardown **3/3**, repeated onboarding teardown **3/3**, `npm run build`, `npm run api:check`, Python `compileall`, and Ruff on `scripts/e2e/app_server.py` all pass. Ruff on `src/desktop/server.py` reports five pre-existing findings; the same five appear on `HEAD`. GitHub checks for these local changes are pending publication. Package/EXE, interactive WebView2 and real League client were not validated here.

All other reported checks on `23d14d51` succeeded, including the Windows package self-test, frontend build/typecheck/API type check, Python CI, website CI, CodeQL, secret scan and dependency audit. The following sections retain evidence from earlier migration snapshots where indicated; they do not supersede this latest check result.

## Scope and repository state

The previous plan snapshot referenced `e5e61c7b39d805656fc56b50391a52c74fa11eae`. The current working tree is based on pushed `23d14d51bc49fc4bc86c8f45ce21244bdc73c61c` on `codex/react-fastapi-webview-migration`, compared with `origin/main` at `809d8567ee4755672b812cc63da46488c30a8ce8`; the changes above remain uncommitted in this snapshot. Python unit, Vitest, website Node tests and unit-only dependencies/scripts/runners have been removed. This does not prove every former assertion has an E2E replacement.

Latest local evidence for this worktree: frontend browser **138/138**, API aggregate **35/35**, full-stack restart/LCU **1/1**, theme and onboarding teardown repeats **3/3 each**. Website **13/13 in an isolated copy** is an earlier result. The native source runner previously reached Settings by mouse, read `presets_enabled=true` and `auto_ban_enabled=false`, then failed because pystray still reported Auto-Ban disabled; cleanup completed, later scenarios did not run. This remains an unconfirmed native UI/tray issue because `GetCursorPos` raised `PermissionError [WinError 5]` under the current desktop. The packaged EXE UI was not tested.

## Current GitHub check evidence

The PR #11 check query for `e5e61c7b39d805656fc56b50391a52c74fa11eae` is historical and does not cover the current changes. On the latest pushed `23d14d51`, both Windows Playwright checks failed as summarized above; other checks on that SHA (package self-test, static frontend/Python checks, website, CodeQL, secret and dependency scans) succeeded. Checks for the new dependency, LCU barrier and Proactor teardown changes will exist only after they are pushed.

The historical `e5e61c7` statuses validate only that pushed commit. Local E2E/build results validate this worktree but do not create GitHub checks. The last package smoke on `23d14d51` used `--self-test --allow-missing-webview2`; it is not proof of interactive WebView2, tray, hotkeys, real League, or installed-EXE UI behavior.

Sources for the remote evidence: [Frontend CI](https://github.com/qurnt1/otp_lol/actions/runs/36485684899), [Python CI](https://github.com/qurnt1/otp_lol/actions/runs/36485684762), [package smoke](https://github.com/qurnt1/otp_lol/actions/runs/36485684826), [security checks](https://github.com/qurnt1/otp_lol/actions/runs/36485684843), and [Pages](https://github.com/qurnt1/otp_lol/actions/runs/36485675764).

## Current local jobs and commands

| Workflow | Job/check | Commands in the local tree | Assessment |
|---|---|---|---|
| `.github/workflows/python-ci.yml` | `Python 3.13 on Windows` | Install runtime requirements; `compileall` on shipped Python entry/source; Ruff fatal/progressive checks and format check | Static-quality gate only. No pytest/unittest runner or test directory input remains. |
| `.github/workflows/frontend-ci.yml` | `Frontend CI / Unit and build`; `Frontend CI / Playwright Windows` | Linux: `npm ci`, `npm run api:check`, `npm run typecheck`, `npm run build`. Windows: install runtime + E2E Python requirements, build, install Chromium, `npx playwright test --workers=1`, full-stack `playwright.config.mjs --workers=1`, then `npm run test:e2e:api` | Unit/build check name is retained for required-check stability; it no longer runs unit tests. Latest local results: browser 138/138, full-stack 1/1, API 35/35; GitHub checks on these edits are pending publication. |
| `.github/workflows/package-smoke.yml` | `Build and self-test Windows package` | Build frontend; create onedir package; run `OTP LOL.exe --self-test --allow-missing-webview2` | Keep as artifact/resource smoke. It is headless and does not prove interactive native UI. |
| `.github/workflows/release.yml` | `Validate tagged source`; `Package Windows executable` | Source gate: install/build frontend, typecheck, Python compileall, `api:check`, browser E2E `--workers=1`, API E2E script. Package gate: PyInstaller build, signing/verification, packaged self-test, installer/signature/checksum/release artifact | No unit runner. The browser and API gates precede package. Current local release workflow has not run on GitHub. |
| `.github/workflows/deploy-website.yml` | Pages build then deploy | Website `npm ci`, production build, `npx playwright test --workers=1` against preview, upload/deploy | Website build/E2E passed 13/13 in an isolated copy; local workflow changes have no GitHub result. The direct invocation addresses the observed npm worker-flag forwarding issue. |
| `.github/workflows/website-ci.yml` | `Website CI / Build and Playwright` | Website `npm ci`, build, `npx playwright test --workers=1` against preview | New local PR workflow; E2E passed 13/13 in an isolated copy; no GitHub result exists for this workflow. |
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
- GitHub results on `23d14d51` include two failed Windows Playwright jobs and otherwise successful reported checks. The new dependency, LCU barrier and teardown recovery are not yet covered by GitHub.
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

The latest local run passed browser 138/138, API 35/35, full-stack 1/1 and teardown repeats 3/3 for theme and onboarding. The frontend production build, generated API consistency, Python compileall and Ruff on the E2E harness pass. Ruff on `src/desktop/server.py` still reports the same five findings present on base `HEAD`. GitHub checks for the local code changes remain pending publication; EXE, real WebView2, interactive desktop and real League validation remain out of scope for this run.
