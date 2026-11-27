"""
系统管理路由：登录日志、在线人员、个人密码修改
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user, stage1_hash
from app.core.config import settings
from app.schemas import MessageOut
from app.services import system_service as svc
from pydantic import BaseModel, Field

router = APIRouter(prefix=f"{settings.API_PREFIX}/system", tags=["系统管理"])


class KickIn(BaseModel):
    usercode: str = Field(..., min_length=1, description="要退出的账号")
    remark: str = ""


class ChangePasswordIn(BaseModel):
    old_password: str = Field(..., description="原密码明文（前端计算第一层 SHA-256 后传入）")
    new_password: str = Field(..., description="新密码明文（前端计算第一层 SHA-256 后传入）")
    confirm_password: str = Field(..., description="确认新密码（前端计算第一层 SHA-256 后传入）")


@router.get("/login-logs")
def api_login_logs(
    usercode: str = "",
    username: str = "",
    date_from: str = "",
    date_to: str = "",
    success: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    """登录日志（ERP 原生 logdb.loginlog）"""
    return svc.login_logs(usercode, username, date_from, date_to, success, page, page_size)


@router.get("/online-users")
def api_online_users(
    usercode: str = "",
    username: str = "",
    minutes: int = svc.ONLINE_WINDOW_MINUTES,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    """在线人员：最近 N 分钟登录成功且未后台退出的用户"""
    return svc.online_users(usercode, username, minutes, page, page_size)


@router.post("/online-users/kick", response_model=MessageOut)
def api_kick_out(payload: KickIn, current_user: dict = Depends(get_current_user)):
    """后台退出：将指定账号标记为下线"""
    try:
        svc.kick_out(payload.usercode, current_user.get("usercode", ""), payload.remark)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MessageOut(message=f"已将 {payload.usercode} 退出")


@router.post("/change-password", response_model=MessageOut)
def api_change_password(payload: ChangePasswordIn, current_user: dict = Depends(get_current_user)):
    """
    修改个人密码：usercode 与 account_id 均取自 JWT，不接受前端指定，无法修改他人密码。
    前端传入的密码为第一层 SHA-256 哈希（64 位），后端按登录链路校验。
    """
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致")

    usercode = current_user.get("usercode", "")
    account_id = current_user.get("account_id")

    # 兼容前端传明文（非 64 位 hex）的情况，统一转成第一层哈希
    def to_l1(v: str) -> str:
        v = (v or "").strip()
        if len(v) == 64 and all(c in "0123456789abcdefABCDEF" for c in v):
            return v.lower()
        return stage1_hash(usercode, v)

    try:
        svc.change_password(
            usercode=usercode,
            old_password_l1=to_l1(payload.old_password),
            new_password_l1=to_l1(payload.new_password),
            account_id=account_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return MessageOut(message="密码已修改，请使用新密码重新登录")
