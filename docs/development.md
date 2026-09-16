# Development

## Local checks

Backend tests:

```powershell
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

The Playwright suite starts Vite on `127.0.0.1:4173` and mocks the local API. It verifies the shared shell, blank first launch, settings dirty-state guard, and history empty state without requiring League to be installed.

Security and quality checks:

```powershell
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-build.txt
cd frontend; npm audit --omit=dev
cd ..; python -m ruff check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py
python -m ruff format --check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py
```

The full local LCU, WebView2, tray, hotkey, and packaged-EXE paths require Windows runtime validation. A real League client is not required for the headless smoke test.
