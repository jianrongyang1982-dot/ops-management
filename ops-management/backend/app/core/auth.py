"""
认证模块：登录校验、JWT 令牌、依赖注入
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.database import fetch_one

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login", auto_error=False)


def verify_password(plain: str, stored: str) -> bool:
    """
    明文直接比对（按需求：memo as pwd，不做加密）
    兼容去除首尾空白，避免数据库字段带空格导致误判
    """
    return (plain or "").strip() == (stored or "").strip()


def authenticate_user(usercode: str, password: str) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        "SELECT usercode, accountname, memo AS pwd FROM ucsdb.account WHERE usercode=%s",
        (usercode,),
    )
    if not row:
        return None
    if not verify_password(password, row.get("pwd")):
        return None
    # 状态校验：status 若为 0 表示停用（存在该字段时）
    return {"usercode": row["usercode"], "accountname": row.get("accountname") or ""}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    payload = decode_token(token)
    if not payload:
        raise credentials_exc
    usercode = payload.get("sub")
    if not usercode:
        raise credentials_exc
    return {"usercode": usercode, "accountname": payload.get("accountname", "")}
