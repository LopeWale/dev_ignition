"""API package exposing the FastAPI application factory."""

from .server import app, create_app

__all__ = ["app", "create_app"]
