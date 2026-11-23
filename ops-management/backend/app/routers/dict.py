"""
字典路由
"""
from fastapi import APIRouter, Depends, Header
from app.core.auth import get_current_user
from app.core.config import settings
from app.schemas import DictItem
from app.services import dict_service

router = APIRouter(prefix=f"{settings.API_PREFIX}/dict", tags=["字典"])


def _lang(accept_language: str | None) -> str:
    return accept_language or "zh-CN"


@router.get("/brands", response_model=list[DictItem])
def brands(_: dict = Depends(get_current_user), accept_language: str | None = Header(None)):
    return dict_service.get_brands(_lang(accept_language))


@router.get("/forwarders", response_model=list[DictItem])
def forwarders(_: dict = Depends(get_current_user), accept_language: str | None = Header(None)):
    return dict_service.get_forwarders(_lang(accept_language))


@router.get("/ship-companies", response_model=list[DictItem])
def ship_companies(_: dict = Depends(get_current_user), accept_language: str | None = Header(None)):
    return dict_service.get_ship_companies(_lang(accept_language))


@router.get("/warehouses", response_model=list[DictItem])
def warehouses(_: dict = Depends(get_current_user), accept_language: str | None = Header(None)):
    return dict_service.get_warehouses(_lang(accept_language))


@router.get("/ports/{kind}", response_model=list[DictItem])
def ports(kind: str, _: dict = Depends(get_current_user), accept_language: str | None = Header(None)):
    if kind not in ("pol", "pod"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="kind must be pol or pod")
    return dict_service.get_ports(kind, _lang(accept_language))


@router.get("/cargotypes", response_model=list[DictItem])
def cargotypes(_: dict = Depends(get_current_user), accept_language: str | None = Header(None)):
    return dict_service.get_cargotypes(_lang(accept_language))
