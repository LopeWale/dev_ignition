"""Automation Gateway specific API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import (
    AutomationGatewayTemplate,
    AutomationGatewayTemplateDetail,
    AutomationGatewayTemplateList,
    ErrorMessage,
)
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

    @router.get(
        "/templates/{template_name}",
        response_model=AutomationGatewayTemplateDetail,
        responses={
            400: {"model": ErrorMessage},
            404: {"model": ErrorMessage},
        },
        summary="Fetch detailed metadata and contents for a template",
    )
    def get_template(template_name: str) -> AutomationGatewayTemplateDetail:
        try:
            detail = service.get_template_detail(template_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return AutomationGatewayTemplateDetail(
            name=detail.name,
            filename=detail.filename,
            exists=detail.exists,
            relative_path=detail.relative_path,
            description=detail.description,
            is_default=detail.is_default,
            content=detail.content,
        )

    return router
