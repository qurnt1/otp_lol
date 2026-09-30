# CI/CD plan for E2E-only testing

## Scope and repository state

This plan reflects the shared local tree at `e5e61c7b39d805656fc56b50391a52c74fa11eae` on `codex/react-fastapi-webview-migration`, compared with `origin/main` at `809d8567ee4755672b812cc63da46488c30a8ce8`. The local tree is uncommitted and has not been pushed. The Python unit suite, Vitest suite, website Node test, unit-only dependencies/scripts, and their CI runners have been removed locally. This does not prove that every former assertion has an E2E replacement.

Final local evidence reported by the orchestrator for this working tree: frontend browser **130/130**, API-focused aggregate **23/23**, full-stack restart/LCU **1/1**, and website **13/13 in an isolated copy**. The native source runner now reaches Settings by mouse, verifies Dashboard values `presets_enabled=true` and `auto_ban_enabled=false`, then fails because pystray still reports Auto-Ban disabled. Cleanup completed successfully; scenarios after this assertion do not run. The packaged EXE UI was not tested. This is a confirmed UI-to-tray state mismatch, not the earlier keyboard-selection failure.

## Current GitHub check evidence

The PR #11 check query for `e5e61c7b39d805656fc56b50391a52c74fa11eae` returned completed checks with `success` conclusions, including Python CI, Frontend CI (then named Unit and build), Frontend CI Playwright Windows, package smoke, CodeQL for Python and JavaScript/TypeScript, dependency audit, secret scan, and the Pages jobs. No failed check was present on that SHA, so there is no failing job evidence to explain for the current local migration.

This only validates the pushed commit `e5e61c7`. The local E2E results above validate the current uncommitted test tree, not the workflows remotely, and do not create GitHub checks for workflow/package/documentation/deletion changes. The packaged smoke at that SHA used `--self-test --allow-missing-webview2`; it is not proof of interactive WebView2, tray, hotkeys, real League, or installed-EXE UI behavior.

Sources for the remote evidence: [Frontend CI](https://github.com/qurnt1/otp_lol/actions/runs/36485684899), [Python CI](https://github.com/qurnt1/otp_lol/actions/runs/36485684762), [package smoke](https://github.com/qurnt1/otp_lol/actions/runs/36485684826), [security checks](https://github.com/qurnt1/otp_lol/actions/runs/36485684843), and [Pages](https://github.com/qurnt1/otp_lol/actions/runs/36485675764).

## Current local jobs and commands

| Workflow | Job/check | Commands in the local tree | Assessment |
|---|---|---|---|
| `.github/workflows/python-ci.yml` | `Python 3.13 on Windows` | Install runtime requirements; `compileall` on shipped Python entry/source; Ruff fatal/progressive checks and format check | Static-quality gate only. No pytest/unittest runner or test directory input remains. |
| `.github/workflows/frontend-ci.yml` | `Frontend CI / Unit and build`; `Frontend CI / Playwright Windows` | Linux: `npm ci`, `npm run api:check`, `npm run typecheck`, `npm run build`. Windows: install runtime + E2E Python requirements, build, install Chromium, `npx playwright test --workers=1`, full-stack `playwright.config.mjs --workers=1`, then `npm run test:e2e:api` | Unit/build check name is intentionally retained for required-check stability; it no longer runs unit tests. Latest local results are browser 130/130, full-stack 1/1, API aggregate 23/23; these are not GitHub checks on local edits. |
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

The matching specs live under `scripts/e2e/`. The API configurations start the actual FastAPI application and use controlled fake LCU/Data Dragon fixtures at external integration boundaries. The API contract scenarios include invalid request handling, origins/CORS and WebSocket Origin behavior. The aggregate passed **23/23** on the current local tree.

## Removed unit-only paths

- Python `tests/test_*.py`, `tests/fake_lcu_server.py`, `tests/__init__.py`, and `requirements-test.txt` are absent in the shared local tree. Python CI/release no longer install pytest or run pytest/unittest discovery. Runtime `unittest.mock` use in `src/desktop/self_test.py` remains part of the packaged self-test, not a suite runner.
- Frontend `*.test.ts(x)` files and the Vitest setup were deleted. `frontend/package.json`/lockfile no longer depend on Vitest, jsdom or Testing Library; Vite build config remains. Frontend CI/release do not invoke a unit script.
- `website/test/content.test.mjs` and the `npm test` script were removed after their release-link, screenshot metadata and rendered-asset assertions were moved into `website/e2e/site.spec.ts`.
- `requirements-constraints.txt` no longer pins pytest or the httpx version used only by the removed metadata test. E2E Python requirements are installed explicitly from `scripts/e2e/requirements.txt`.

Historical archives and migration inventories may mention these previous runners while describing the baseline. They must not document them as active local commands. No command using `pytest`, `unittest discover`, Vitest or `node --test` should be active in a manifest/workflow. Keep OpenAPI generation, typecheck, Ruff, compileall, builds, audits, package self-test and Playwright.

## Workflow coverage and residual blind spots

The browser specs use the production frontend build and real FastAPI for ordinary requests. Targeted UI recovery scenarios deliberately install `page.route` handlers for `/api/network/status`, `/api/history`, `/api/champions`, `/api/presets/pick_1`, `/api/assets/skins/86/86013/splash*`, and `/api/settings`. These handlers inject transport/API failures to test the browser response; they are not evidence that FastAPI produces those failures. The six API E2E configs complement those UI simulations using the real server.

Potential green-CI gaps that remain material:

- Current local browser, full-stack, API and website results are 130/130, 1/1, 23/23 and 13/13 respectively. The source native runner fails on the confirmed disabled Auto-Ban tray entry after reading the Dashboard values; cleanup completes, but assertions after the failure do not execute.
- Existing GitHub successes belong to `e5e61c7`, whose frontend workflow still contained the old unit check. No uncommitted workflow or spec change has a GitHub check attached.
- `Frontend CI / Unit and build` is a legacy required-check label with no unit runner now. Renaming it can disrupt branch protection; leave the check name unchanged unless repository rules are intentionally updated.
- Chromium, fake LCU and HTTP fixtures do not exercise an installed League Client, real WebView2, interactive Windows desktop, DPI/multi-monitor behavior, global hotkeys, tray, native dialogs or providers. The native runner is not a validated CI gate.
- Package `--self-test --allow-missing-webview2` does not launch the actual interactive UI. A successful PyInstaller build and self-test can coexist with an EXE-only WebView/resource/permission failure.
- The website workflows use direct `npx playwright test --workers=1` because the npm invocation used during verification ran two workers. The 13/13 isolated-copy result does not validate either workflow on GitHub.
- A green `api:check`/typecheck/build proves generated types and compilability, not that every frontend error path matches backend behavior.

## E2E-only acceptance gates

1. Preserve the current 130/130 browser, 23/23 API and 1/1 full-stack results as local evidence; obtain a second consecutive browser pass if the release gate continues to require two clean runs.
2. Keep all six API configs in the serial `npm run test:e2e:api` command and workflow. The current aggregate is 23/23; repeat only if later changes affect these specs, harness or workflow.
3. Preserve the 1/1 full-stack result; repeat if later changes affect restart, reconnect, persistence, egress or cleanup.
4. Execute static gates on the final tree: API generation, TypeScript, Vite builds, Python compileall/Ruff, dependency audits and package self-test. These do not replace E2E results.
5. Website build/E2E passed 13/13 in an isolated copy. Run both workflows on an intended remote SHA before treating GitHub checks as green.
6. Resolve the confirmed tray mismatch: with `presets_enabled=true` and `auto_ban_enabled=false` from the Dashboard, the native menu exposes Auto-Ban as disabled. Rerun the full native source scenario; its current failure prevents later assertions from executing. Keep packaged-EXE UI coverage separate until the interactive runner exercises the package itself.
7. Check GitHub Actions at the new pushed SHA only after publication is separately authorized. A passing old SHA is never substituted for current checks.

## Validation state and next actions

The E2E results above were produced by the coordinated parent run, not by this agent. Static checks confirmed the six configs/specs exist in declared order, each uses one worker, and frontend CI/release/docs call the aggregate script. The latest native run passes the Settings click but fails the Auto-Ban menu assertion; cleanup is complete and subsequent scenarios are not run. GitHub checks remain those attached to `e5e61c7`; uncommitted workflow edits need a remote run on a later SHA.
