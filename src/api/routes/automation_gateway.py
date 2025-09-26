"""Automation Gateway specific API routes."""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas import AutomationGatewayTemplate, AutomationGatewayTemplateList
from services import AutomationGatewayService


def get_router(service: AutomationGatewayService) -> APIRouter:
    """Bind Automation Gateway related endpoints to the provided service."""

    router = APIRouter(prefix="/automation-gateway", tags=["automation-gateway"])

    @router.get(
        "/templates",
        response_model=AutomationGatewayTemplateList,
        summary="List available Automation Gateway configuration templates",
    )
    def list_templates() -> AutomationGatewayTemplateList:
        templates = [
            AutomationGatewayTemplate(
                name=metadata.name,
                filename=metadata.filename,
                exists=metadata.exists,
                relative_path=metadata.relative_path,
                description=metadata.description,
                is_default=metadata.is_default,
            )
            for metadata in service.list_templates()
        ]
        return AutomationGatewayTemplateList(items=templates)

    return router
