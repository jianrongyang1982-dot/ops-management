"""
看板路由
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.config import settings
from app.services.dashboard_service import get_dashboard

router = APIRouter(prefix=f"{settings.API_PREFIX}/dashboard", tags=["看板"])


@router.get("", response_model=Dict[str, Any])
def dashboard(_: dict = Depends(get_current_user)):
    return get_dashboard()
