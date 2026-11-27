"""
菜单 / 角色 / 权限 / 个人收藏 路由
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import settings
from app.services import menu_service as svc

router = APIRouter(prefix=f"{settings.API_PREFIX}/menu", tags=["菜单权限"])


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------

class FavoritesIn(BaseModel):
    menu_codes: List[str] = Field(default_factory=list)


class RoleIn(BaseModel):
    role_code: str = Field("", description="新增时必填")
    role_name: str = Field("", description="角色名称")
    role_name_en: str = ""
    remark: str = ""
    is_admin: bool = False
    status: int = 1


class RoleMenusIn(BaseModel):
    role_code: str
    menu_codes: List[str] = Field(default_factory=list)


class UserRolesIn(BaseModel):
    usercode: str
    role_codes: List[str] = Field(default_factory=list)


def _handle_error(exc: Exception):
    msg = str(exc)
    if "数据表尚未创建" in msg:
        raise HTTPException(status_code=503, detail=msg)
    if any(k in msg for k in ("不存在", "不能为空", "已存在", "无权", "无需配置")):
        raise HTTPException(status_code=400, detail=msg)
    raise HTTPException(status_code=500, detail=msg)


def _uc(current_user: dict) -> str:
    return (current_user.get("usercode") or "").strip()


# ---------------------------------------------------------------------------
# 我的菜单 / 收藏（所有登录用户）
# ---------------------------------------------------------------------------

@router.get("/my-menus")
def api_my_menus(current_user: dict = Depends(get_current_user)):
    try:
        return svc.my_menus(_uc(current_user))
    except Exception as exc:
        _handle_error(exc)


@router.get("/my-favorites")
def api_my_favorites(current_user: dict = Depends(get_current_user)):
    try:
        return {"items": svc.my_favorites(_uc(current_user))}
    except Exception as exc:
        _handle_error(exc)


@router.post("/my-favorites")
def api_save_favorites(payload: FavoritesIn, current_user: dict = Depends(get_current_user)):
    try:
        return {"items": svc.save_favorites(_uc(current_user), payload.menu_codes)}
    except Exception as exc:
        _handle_error(exc)


# ---------------------------------------------------------------------------
# 角色管理（仅管理员，由前端按角色可见性控制；后端再做一次角色校验）
# ---------------------------------------------------------------------------

def _require_admin(current_user: dict) -> None:
    roles = svc.user_role_codes(_uc(current_user))
    if not roles:
        # 未分配角色=全量权限，视为管理员
        return
    admins = [r["role_code"] for r in svc.roles() if r["is_admin"]]
    if not any(r in admins for r in roles):
        raise HTTPException(status_code=403, detail="只有管理员可以配置菜单权限")


@router.get("/roles")
def api_roles(current_user: dict = Depends(get_current_user)):
    try:
        return {"items": svc.roles()}
    except Exception as exc:
        _handle_error(exc)


@router.post("/roles")
def api_add_role(payload: RoleIn, current_user: dict = Depends(get_current_user)):
    try:
        _require_admin(current_user)
        return svc.add_role(payload.role_code, payload.role_name, payload.role_name_en,
                            payload.remark, payload.is_admin)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_error(exc)


@router.put("/roles/{role_id}")
def api_update_role(role_id: int, payload: RoleIn, current_user: dict = Depends(get_current_user)):
    try:
        _require_admin(current_user)
        return svc.update_role(role_id, payload.role_name, payload.role_name_en,
                               payload.remark, payload.status, payload.is_admin)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_error(exc)


@router.delete("/roles/{role_id}")
def api_delete_role(role_id: int, current_user: dict = Depends(get_current_user)):
    try:
        _require_admin(current_user)
        return svc.delete_role(role_id)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_error(exc)


@router.get("/role-menus")
def api_role_menus(role_code: str, current_user: dict = Depends(get_current_user)):
    try:
        return {"items": svc.role_menus(role_code)}
    except Exception as exc:
        _handle_error(exc)


@router.post("/role-menus")
def api_save_role_menus(payload: RoleMenusIn, current_user: dict = Depends(get_current_user)):
    try:
        _require_admin(current_user)
        return svc.save_role_menus(payload.role_code, payload.menu_codes)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_error(exc)


@router.get("/user-roles")
def api_user_roles(usercode: str, current_user: dict = Depends(get_current_user)):
    try:
        return {"items": svc.user_roles(usercode)}
    except Exception as exc:
        _handle_error(exc)


@router.post("/user-roles")
def api_assign_user_roles(payload: UserRolesIn, current_user: dict = Depends(get_current_user)):
    try:
        _require_admin(current_user)
        return svc.assign_user_roles(payload.usercode, payload.role_codes)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_error(exc)


@router.get("/users")
def api_users(keyword: str = "", page: int = Query(1, ge=1),
              page_size: int = Query(20, ge=1, le=200),
              current_user: dict = Depends(get_current_user)):
    try:
        _require_admin(current_user)
        return svc.search_users(keyword, page, page_size)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_error(exc)
