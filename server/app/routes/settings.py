from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import SettingUpdate
from app.state import library_service


router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings() -> dict[str, str]:
    return library_service.get_settings()


@router.post("/settings")
def set_setting(payload: SettingUpdate) -> dict[str, str]:
    return library_service.set_setting(payload.key, payload.value)

