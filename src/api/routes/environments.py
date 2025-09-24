"""Environment management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from api.schemas import (
    EnvironmentCreate,
    EnvironmentDetail,
    EnvironmentList,
    ErrorMessage,
)
from services import EnvironmentNotFoundError, EnvironmentService


def get_router(service: EnvironmentService) -> APIRouter:
    """Create a router bound to the provided environment service."""

    router = APIRouter(prefix="/environments", tags=["environments"])

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        response_model=EnvironmentDetail,
        responses={
            status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorMessage},
        },
    )
    def create_environment(payload: EnvironmentCreate) -> EnvironmentDetail:
        record = service.create_environment(payload)
        return EnvironmentDetail(**service.to_detail_payload(record))

    @router.get(
        "",
        response_model=EnvironmentList,
        responses={status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorMessage}},
    )
    def list_environments() -> EnvironmentList:
        records = service.list_environments()
        items = [service.to_summary_payload(record) for record in records]
        return EnvironmentList(items=items)

    @router.get(
        "/{env_id}",
        response_model=EnvironmentDetail,
        responses={status.HTTP_404_NOT_FOUND: {"model": ErrorMessage}},
    )
    def get_environment(env_id: str) -> EnvironmentDetail:
        try:
            record = service.get_environment(env_id)
        except EnvironmentNotFoundError as exc:  # pragma: no cover - straightforward branch
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found") from exc
        return EnvironmentDetail(**service.to_detail_payload(record))

    @router.delete(
        "/{env_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={status.HTTP_404_NOT_FOUND: {"model": ErrorMessage}},
    )
    def delete_environment(env_id: str) -> Response:
        try:
            service.delete_environment(env_id)
        except EnvironmentNotFoundError as exc:  # pragma: no cover - straightforward branch
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found") from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
