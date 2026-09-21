# Development

## Local checks

Backend tests:

```powershell
python -m pip install -c requirements-constraints.txt -r requirements-test.txt
python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q launcher_web.py src tests
```

Frontend checks:

```powershell
cd frontend
npm ci
npm run api:check
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

The frontend expects Node.js `22`. The Playwright suite starts Vite on `127.0.0.1:4173` and mocks the local API. It verifies the shared shell, blank first launch, settings dirty-state guard, and history empty state without requiring League to be installed. The release and E2E Windows jobs install Chromium on Windows; a real packaged smoke test still requires WebView2.

The README images in [`docs/images/`](./images/) are current Playwright captures of the mocked desktop shell. Update them only from a validated current UI state, and keep real account data out of committed screenshots.

Security and quality checks:

```powershell
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-test.txt
python -m pip_audit -r requirements-build.txt
cd frontend; npm audit --omit=dev
cd ..; python -m ruff check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py
python -m ruff format --check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py
```

The full local LCU, WebView2, tray, hotkey, and packaged-EXE paths require Windows runtime validation. A real League client is not required for the headless smoke test.
