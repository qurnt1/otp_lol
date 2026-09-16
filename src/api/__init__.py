"""FastAPI application boundary for the desktop frontend."""

from .app import ApplicationContext, create_app, create_default_context

__all__ = ["ApplicationContext", "create_app", "create_default_context"]
