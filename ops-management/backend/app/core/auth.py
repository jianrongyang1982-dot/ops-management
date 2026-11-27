"""
认证模块：登录校验、JWT 令牌、依赖注入

密码校验采用与 ERP 一致的两层 SHA-256 链路（front-end 计算第一层，服务端计算第二层）：

    第一层（浏览器）:  L1 = sha256(usercode + "_" + 明文密码)
    第二层（服务端）:  L2 = sha256(usercode + "_" + L1 + "_" + salt)

    L2（64 位小写十六进制）与 ucsdb.account.pwd 比对（库内存的是大写，比对时忽略大小写）。
"""
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.database import fetch_all

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login", auto_error=False)

# 账户表统一过滤条件：只认主库拆分（dbsplitcode='1'），status=1 为启用
_ACCOUNT_WHERE = "dbsplitcode='1'"
_STATUS_ENABLED = 1

# 第一层哈希的固定长度（sha256 hex）
_L1_LEN = 64


def stage1_hash(usercode: str, password: str) -> str:
    """第一层：sha256(usercode_password)，前端同样实现。"""
    raw = f"{(usercode or '').strip()}_{password or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stage2_hash(usercode: str, stage1: str, salt: str) -> str:
    """第二层：sha256(usercode_L1_salt)，服务端计算。"""
    raw = f"{(usercode or '').strip()}_{(stage1 or '').strip().lower()}_{(salt or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _looks_like_stage1(value: str) -> bool:
    """判断前端传来的是第一层哈希而非明文（64 位十六进制）。"""
    v = (value or "").strip()
    if len(v) != _L1_LEN:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in v)


def verify_password(stage1: str, stored: str, usercode: str, salt: str) -> bool:
    """
    校验密码：把第一层哈希 + salt 再算一次第二层，与库内 pwd 做常量时间比对。
    - 大小写不敏感（库内存大写十六进制）
    - 使用 hmac.compare_digest 防时序攻击
    """
    if not stored or not salt:
        return False
    expect = (stored or "").strip().lower()
    actual = stage2_hash(usercode, stage1, salt)
    return hmac.compare_digest(actual, expect)


def find_account(usercode: str) -> Optional[Dict[str, Any]]:
    """
    按 usercode 取启用账户。
    存在少量同 usercode 多条记录的情况（如 admin 有 2 条、salt 不同），
    这里全部取出交给调用方逐一验证，避免 fetch_one 随机命中导致的登录不稳定。
    """
    rows = fetch_all(
        f"SELECT id, usercode, accountname, pwd, salt, status "
        f"FROM ucsdb.account WHERE usercode=%s AND {_ACCOUNT_WHERE} ORDER BY id",
        (usercode,),
    )
    return rows or None


def authenticate_user(usercode: str, password: str) -> Optional[Dict[str, Any]]:
    """
    认证入口。
    password 参数可以是：
      1) 前端算好的第一层哈希（64 位 hex）—— 推荐，明文不出浏览器；
      2) 明文密码 —— 兜底兼容（此时服务端自行计算第一层）。
    """
    uc = (usercode or "").strip()
    if not uc or not password:
        return None

    rows = find_account(uc)
    if not rows:
        return None

    stage1 = password.strip().lower() if _looks_like_stage1(password) else stage1_hash(uc, password)

    for row in rows:
        if row.get("status") != _STATUS_ENABLED:
            continue
        if verify_password(stage1, row.get("pwd") or "", uc, row.get("salt") or ""):
            return {
                "usercode": row["usercode"],
                "accountname": row.get("accountname") or "",
                "account_id": row.get("id"),
            }

    logger.info("登录失败: usercode=%s 候选账户=%d", uc, len(rows))
    return None


def hash_password(usercode: str, password: str, salt: str) -> str:
    """按链路生成入库 pwd（供改密/初始化脚本使用）。"""
    return stage2_hash(usercode, stage1_hash(usercode, password), salt)


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
    return {
        "usercode": usercode,
        "accountname": payload.get("accountname", ""),
        "account_id": payload.get("account_id"),
    }
