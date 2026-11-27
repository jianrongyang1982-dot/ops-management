"""
认证与主页面路由
"""
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import authenticate_user, create_access_token, get_current_user
from app.schemas import LoginIn, LoginOut, UserOut, ModuleOut
from app.core.config import settings
from app.services import system_service as system_svc

router = APIRouter(tags=["认证"])


@router.post(f"{settings.API_PREFIX}/auth/login", response_model=LoginOut)
def login(payload: LoginIn, request: Request):
    started = time.time()
    usercode = (payload.usercode or "").strip()
    if not usercode or not payload.password:
        raise HTTPException(status_code=400, detail="请输入用户名和密码")

    user = authenticate_user(usercode, payload.password)
    if not user:
        # 记录失败日志（含 IP、耗时、备注）
        system_svc.write_login_log(
            usercode=usercode,
            username="",
            success=False,
            client_ip=_client_ip(request),
            cost_ms=int((time.time() - started) * 1000),
            remark="用户名或密码错误",
        )
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token({
        "sub": user["usercode"],
        "accountname": user["accountname"],
        "account_id": user.get("account_id"),
    })
    # 记录成功日志
    system_svc.write_login_log(
        usercode=usercode,
        username=user["accountname"] or "",
        success=True,
        client_ip=_client_ip(request),
        cost_ms=int((time.time() - started) * 1000),
    )
    return LoginOut(
        access_token=token,
        usercode=user["usercode"],
        accountname=user["accountname"],
        display_name=f"{user['usercode']} {user['accountname']}".strip(),
    )


def _client_ip(request: Request) -> str:
    """取真实客户端 IP：优先 X-Forwarded-For（Nginx 反代场景）。"""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real = request.headers.get("x-real-ip", "")
    if real:
        return real.strip()
    return request.client.host if request.client else ""


@router.get(f"{settings.API_PREFIX}/auth/me", response_model=UserOut)
def me(current_user: dict = Depends(get_current_user)):
    return UserOut(
        usercode=current_user["usercode"],
        accountname=current_user.get("accountname", ""),
        display_name=f"{current_user['usercode']} {current_user.get('accountname', '')}".strip(),
    )


@router.get(f"{settings.API_PREFIX}/modules", response_model=list[ModuleOut])
def list_modules(current_user: dict = Depends(get_current_user)):
    """主页面模块按钮，模块化扩展：后续新增模块在此注册即可"""
    return [
        ModuleOut(key="container", name="集装箱跟踪", icon="box", path="/container"),
        # 后续扩展示例：ModuleOut(key="xxx", name="XXX", icon="xxx", path="/xxx"),
    ]
