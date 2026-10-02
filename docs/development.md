# Development

## Local checks

```powershell
python -m compileall -q launcher_web.py src create_exe.py
python -m ruff check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py
python -m ruff format --check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py
```

Frontend checks:

```powershell
python -m pip install -c requirements-constraints.txt -r requirements.txt -r scripts/e2e/requirements.txt
cd frontend
npm ci
npm run api:check
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e -- --workers=1
npx playwright test --config ../scripts/e2e/playwright.config.mjs --workers=1
npm run test:e2e:api
```

The frontend expects Node.js `22` and Python `3.13` for the E2E harness. Build `frontend/dist` before running Playwright: each browser test starts a fresh real FastAPI subprocess that serves this bundle and uses the real API/WebSocket with an isolated temporary profile and controllable fake League client. The full-stack restart/LCU smoke and API-focused scenarios use separate Playwright configs; `test:e2e:api` runs the account, asset, diagnostics, LCU automation, Data Dragon cache, and API contract configs sequentially with one worker each. The contract checks cover real API validation/CORS and WebSocket origin behavior. External HTTP dependencies are answered at the Python client boundary, and the browser runner blocks non-app origins. Neither Playwright E2E path connects to an installed League client. A real packaged smoke test still requires Windows and WebView2.

The README images in [`docs/images/`](./images/) are current Playwright captures of the mocked desktop shell. Update them only from a validated current UI state, and keep real account data out of committed screenshots.

Security and quality checks:

```powershell
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-build.txt
python -m pip_audit -r scripts/e2e/requirements.txt
cd frontend; npm audit --omit=dev
cd ..; python -m ruff check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py
python -m ruff format --check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py
```

The full local LCU, WebView2, tray, hotkey, and packaged-EXE paths require Windows runtime validation. A real League client is not required for the headless smoke test. The strict local packaged self-test requires WebView2; CI uses `--allow-missing-webview2` because the installer and the real smoke test validate that machine prerequisite separately.

## Windows package smoke

The release source checks do not prove that PyInstaller can freeze the current frontend and desktop runtime. Run the same package smoke locally from a Windows checkout after building the frontend:

```powershell
cd frontend
npm ci
npm run build
cd ..
python -m pip install -c requirements-constraints.txt -r requirements-build.txt
python create_exe.py --mode onedir --no-shortcut
& ".\OTP LOL\OTP LOL.exe" --self-test
```

The `Package Windows smoke` GitHub Actions workflow runs these package checks on pull requests and important branch pushes. It does not create an installer or publish a release.
