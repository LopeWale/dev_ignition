"""API route registration helpers."""

from .environments import get_router as get_environment_router

__all__ = ["get_environment_router"]
