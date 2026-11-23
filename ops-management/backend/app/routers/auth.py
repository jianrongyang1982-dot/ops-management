"""
认证与主页面路由
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import authenticate_user, create_access_token, get_current_user
from app.schemas import LoginIn, LoginOut, UserOut, ModuleOut
from app.core.config import settings

router = APIRouter(tags=["认证"])


@router.post(f"{settings.API_PREFIX}/auth/login", response_model=LoginOut)
def login(payload: LoginIn):
    user = authenticate_user(payload.usercode, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token({
        "sub": user["usercode"],
        "accountname": user["accountname"],
    })
    return LoginOut(
        access_token=token,
        usercode=user["usercode"],
        accountname=user["accountname"],
        display_name=f"{user['usercode']} {user['accountname']}".strip(),
    )


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
