"""API route registration helpers."""

from .automation_gateway import get_router as get_automation_gateway_router
from .environments import get_router as get_environment_router

__all__ = ["get_environment_router", "get_automation_gateway_router"]
