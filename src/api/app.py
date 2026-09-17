"""FastAPI application factory used by the desktop shell and tests."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import CURRENT_VERSION
from ..services.urls import LIVE_FRAME_ORIGINS, STATS_FRAME_ORIGINS
from .context import ApplicationContext
from .routes import catalog, history, runtime, settings


def create_default_context() -> ApplicationContext:
    return ApplicationContext.from_system()


def create_app(
    context: ApplicationContext | None = None,
    *,
    frontend_dir: str | Path | None = None,
) -> FastAPI:
    app_context = context or create_default_context()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await app_context.start()
        try:
            yield
        finally:
            await app_context.stop()

    app = FastAPI(title="OTP LOL", version=CURRENT_VERSION, lifespan=lifespan)
    app.state.context = app_context
    allow_dev_origins = frontend_dir is None or os.environ.get("OTP_LOL_ALLOW_DEV_ORIGINS") == "1"
    dev_origins = ["http://127.0.0.1:5173", "http://localhost:5173"] if allow_dev_origins else []

    @app.middleware("http")
    async def validate_mutation_origin(request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            local_origin = f"{request.url.scheme}://{request.url.netloc}"
            if not origin or origin not in {local_origin, *dev_origins}:
                return JSONResponse(status_code=403, content={"detail": "Untrusted request origin"})
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=dev_origins,
        allow_credentials=False,
        allow_methods=["GET", "PATCH", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        frame_sources = " ".join(sorted(set(STATS_FRAME_ORIGINS.values()) | set(LIVE_FRAME_ORIGINS.values())))
        response.headers.setdefault(
            "Content-Security-Policy",
            f"default-src 'self'; connect-src 'self' http://127.0.0.1:5173 http://localhost:5173 ws://127.0.0.1:5173 ws://localhost:5173; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; base-uri 'self'; frame-src 'self' {frame_sources}; frame-ancestors 'none'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response
    app.include_router(runtime.router)
    app.include_router(settings.router)
    app.include_router(catalog.router)
    app.include_router(history.router)

    if frontend_dir:
        static_dir = Path(frontend_dir)
        if static_dir.is_dir():
            app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return app


app = create_app()

__all__ = ["ApplicationContext", "app", "create_app", "create_default_context"]
