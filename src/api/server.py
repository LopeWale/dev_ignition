"""FastAPI application wiring for the Ignition control plane."""

from __future__ import annotations

from fastapi import FastAPI

from api.routes import get_environment_router
from services import EnvironmentService


def create_app() -> FastAPI:
    """Instantiate the FastAPI application."""

    app = FastAPI(
        title="Ignition DevOps API",
        version="0.1.0",
        description=(
            "HTTP interface for provisioning and managing Ignition development environments."
        ),
    )

    environment_service = EnvironmentService()
    app.state.environment_service = environment_service
    app.include_router(get_environment_router(environment_service), prefix="/api")

    @app.get("/healthz", tags=["system"], summary="Liveness probe")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
