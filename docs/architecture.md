# Architecture

## Runtime boundary

`launcher_web.py` starts the native desktop shell and the local FastAPI application. `pywebview` hosts the compiled `frontend/dist` output in WebView2. The Python runtime owns LCU communication, automation, settings persistence, history, and asset retrieval.

The React application talks to the backend through typed HTTP endpoints and a WebSocket event stream. Runtime status events carry an action key, parameters, and severity; the frontend owns their localized presentation in `fr.ts`. Phase changes update the runtime snapshot and top bar rather than duplicating phase copy in the dashboard activity strip. `useHashRoute` owns the current view, while `runtimeStore` owns the live runtime snapshot and latest activity.

## Main layers

- `src/api/`: HTTP and WebSocket boundary, request validation, and response schemas.
- `src/config/`: paths, constants, first-launch defaults, normalization, import/export, and atomic persistence.
- `src/core/`: champion select, Data Dragon catalog access, and website-region mapping.
- `src/lcu/`: League Client lifecycle, runtime snapshots, and event publication.
- `src/integrations/`: external providers such as CommunityDragon.
- `src/desktop/`: pywebview bridge, native links, self-tests, and window lifecycle.
- `frontend/src/api/`: HTTP client, generated OpenAPI types, and WebSocket event handling.
- `frontend/src/components/`: shared shell and UI primitives.
- `frontend/src/features/`: the four application views and their feature-local components.
- `website/`: separate public Vite site. It is not the desktop frontend.

## Data flow

```text
League Client / LCU
        ↓
LcuRuntime → EventBroker → /api/events → runtimeStore
        ↓                         ↓
automation services          React shell and pages
```

The `/api/bootstrap` response contains cached champion, spell, skin, and ban previews for the first dashboard paint. It does not load remote catalogs or the LCU skin inventory. Full catalogs are fetched only when their editor opens.

Data Dragon provides the champion and skin catalog. CommunityDragon is used only through validated relative asset paths for rune images. Both network paths use timeouts, response checks, bounded payloads, image type validation, logging, and bounded caches.

## Frontend styling

The desktop UI uses the shared stylesheet in `frontend/src/styles/globals.css`. Tailwind is available through the Vite plugin for the few utility-level cases that need it, while the application layout and tokens remain in the inspectable stylesheet.
