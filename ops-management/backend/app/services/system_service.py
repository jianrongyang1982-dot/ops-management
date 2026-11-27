"""
系统管理服务：登录日志、在线人员、个人密码修改

登录日志与在线人员使用本系统自建表（bidb），不沿用 ERP 的 logdb.loginlog：
- bidb.ops_login_log    登录日志（成功 / 失败都记录）
- bidb.ops_online_user  在线人员（每账号一条，登录 upsert，退出置 status=0）

岗位名称 / 部门名称在登录时从 ucsdb 字典表取快照写入在线表，查询时只读本表：
- ucsdb.ent_account_dept_post / ent_post / ent_dept

账户密码仍使用 ERP 原生表：
- ucsdb.account（pwd / salt）

在线人员的判定：ops_online_user.status=1，并可按最近 N 分钟过滤。
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import execute, fetch_all, fetch_one
from app.core.auth import stage2_hash, verify_password

logger = logging.getLogger(__name__)

T_LOGIN_LOG = "bidb.ops_login_log"
T_ONLINE = "bidb.ops_online_user"
T_ACCOUNT = "ucsdb.account"
T_ADP = "ucsdb.ent_account_dept_post"
T_POST = "ucsdb.ent_post"
T_DEPT = "ucsdb.ent_dept"

# 在线判定窗口（分钟）
ONLINE_WINDOW_MINUTES = 120

# 终端平台 / 产品默认值
DEFAULT_TERMINAL = "PC-WEB"
DEFAULT_PRODUCT = "web"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _dt(v: Any) -> str:
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return str(v) if v is not None else ""


def _post_dept_snapshot(usercode: str) -> Dict[str, str]:
    """登录时取岗位/部门快照，写入在线人员表；取不到则为空串。"""
    try:
        row = fetch_one(
            f"""
            SELECT
              (SELECT p.postname FROM {T_ADP} e
                 LEFT JOIN {T_POST} p ON e.postcode = p.postcode AND p.dbsplitcode = '1'
                WHERE e.usercode = %s AND e.dbsplitcode = '1'
                ORDER BY e.ismain DESC, e.id LIMIT 1) AS postname,
              (SELECT d.deptname FROM {T_ADP} e
                 LEFT JOIN {T_DEPT} d ON e.deptcode = d.deptcode AND d.dbsplitcode = '1'
                WHERE e.usercode = %s AND e.dbsplitcode = '1'
                ORDER BY e.ismain DESC, e.id LIMIT 1) AS deptname
            """,
            (usercode, usercode),
        )
        return {
            "postname": (row or {}).get("postname") or "",
            "deptname": (row or {}).get("deptname") or "",
        }
    except Exception as exc:
        logger.warning("取岗位部门快照失败: usercode=%s err=%s", usercode, exc)
        return {"postname": "", "deptname": ""}


def _upsert_online(
    usercode: str,
    username: str,
    client_ip: str,
    terminal: str,
    device: str,
) -> None:
    """登录成功后 upsert 在线人员表；同一账号只保留一条在线记录。"""
    snap = _post_dept_snapshot(usercode)
    execute(
        f"""
        INSERT INTO {T_ONLINE}
          (usercode, username, terminal, product, postname, deptname,
           client_ip, device, login_time, last_active_time, status, logout_time, logout_reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), 1, NULL, '')
        ON DUPLICATE KEY UPDATE
          username         = VALUES(username),
          terminal         = VALUES(terminal),
          product          = VALUES(product),
          postname         = VALUES(postname),
          deptname         = VALUES(deptname),
          client_ip        = VALUES(client_ip),
          device           = VALUES(device),
          login_time       = NOW(),
          last_active_time = NOW(),
          status           = 1,
          logout_time      = NULL,
          logout_reason    = ''
        """,
        (
            usercode, username or "", terminal or DEFAULT_TERMINAL, DEFAULT_PRODUCT,
            snap["postname"], snap["deptname"], client_ip or "", device or "",
        ),
    )


# ---------------------------------------------------------------------------
# 登录日志写入（由认证流程调用）
# ---------------------------------------------------------------------------

def write_login_log(
    usercode: str,
    username: str = "",
    success: bool = True,
    client_ip: str = "",
    cost_ms: int = 0,
    remark: str = "",
    terminal: str = DEFAULT_TERMINAL,
) -> None:
    """
    写登录日志到 bidb.ops_login_log；登录成功时同步 upsert 在线人员表。
    日志写入失败不影响登录主流程。
    """
    uc = (usercode or "").strip()
    if not uc:
        return
    try:
        execute(
            f"""
            INSERT INTO {T_LOGIN_LOG}
              (usercode, username, terminal, product, device, success,
               client_ip, cost_ms, login_time, remark)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            """,
            (
                uc, username or "", terminal or DEFAULT_TERMINAL, DEFAULT_PRODUCT,
                "ops-management", 1 if success else 0,
                (client_ip or "")[:50], int(cost_ms or 0), (remark or "")[:255],
            ),
        )
        if success:
            _upsert_online(uc, username, client_ip, terminal, "ops-management")
    except Exception as exc:
        logger.warning("写登录日志/在线人员失败: usercode=%s err=%s", uc, exc)


# ---------------------------------------------------------------------------
# 登录日志查询
# ---------------------------------------------------------------------------

def login_logs(
    usercode: str = "",
    username: str = "",
    date_from: str = "",
    date_to: str = "",
    success: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """登录日志列表：账号 / 姓名 / 登录时间 过滤，按时间倒序分页。"""
    where = ["1=1"]
    params: List[Any] = []

    if usercode:
        where.append("usercode = %s")
        params.append(usercode.strip())
    if username:
        where.append("username LIKE %s")
        params.append(f"%{username.strip()}%")
    if date_from:
        where.append("login_time >= %s")
        params.append(f"{date_from[:10]} 00:00:00")
    if date_to:
        where.append("login_time < %s")
        params.append((datetime.strptime(date_to[:10], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00"))
    if success in (0, 1):
        where.append("success = %s")
        params.append(success)

    wsql = " AND ".join(where)
    total = fetch_one(f"SELECT COUNT(*) n FROM {T_LOGIN_LOG} WHERE {wsql}", tuple(params))["n"]

    rows = fetch_all(
        f"""
        SELECT id, usercode, username, terminal, product, device, success,
               client_ip, cost_ms, login_time, remark
        FROM {T_LOGIN_LOG}
        WHERE {wsql}
        ORDER BY login_time DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (page_size, (page - 1) * page_size),
    )

    items = []
    for i, r in enumerate(rows, start=(page - 1) * page_size + 1):
        items.append({
            "seq": i,
            "usercode": r.get("usercode") or "",
            "username": r.get("username") or "",
            "terminal": r.get("terminal") or "",
            "product": r.get("product") or "",
            "device": r.get("device") or "",
            "success": int(r.get("success") or 0),
            "client_ip": r.get("client_ip") or "",
            "cost": int(r.get("cost_ms") or 0),
            "log_time": _dt(r.get("login_time")),
            "remark": r.get("remark") or "",
        })

    return {"items": items, "total": int(total), "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# 在线人员
# ---------------------------------------------------------------------------

def online_users(
    usercode: str = "",
    username: str = "",
    minutes: int = ONLINE_WINDOW_MINUTES,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """在线人员：查 bidb.ops_online_user，status=1，可按最近 N 分钟过滤。"""
    minutes = max(1, min(int(minutes or ONLINE_WINDOW_MINUTES), 10080))
    cutoff = datetime.now() - timedelta(minutes=minutes)

    where = ["status = 1", "login_time >= %s"]
    params: List[Any] = [cutoff]
    if usercode:
        where.append("usercode = %s")
        params.append(usercode.strip())
    if username:
        where.append("username LIKE %s")
        params.append(f"%{username.strip()}%")
    wsql = " AND ".join(where)

    total = fetch_one(f"SELECT COUNT(*) n FROM {T_ONLINE} WHERE {wsql}", tuple(params))["n"]
    rows = fetch_all(
        f"""
        SELECT usercode, username, terminal, product, postname, deptname,
               client_ip, device, login_time
        FROM {T_ONLINE}
        WHERE {wsql}
        ORDER BY login_time DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (page_size, (page - 1) * page_size),
    )

    items = []
    for i, r in enumerate(rows, start=(page - 1) * page_size + 1):
        items.append({
            "seq": i,
            "usercode": r.get("usercode") or "",
            "username": r.get("username") or "",
            "terminal": r.get("terminal") or "",
            "postname": r.get("postname") or "",
            "deptname": r.get("deptname") or "",
            "client_ip": r.get("client_ip") or "",
            "login_time": _dt(r.get("login_time")),
            "device": r.get("device") or "",
        })

    return {
        "items": items, "total": int(total), "page": page, "page_size": page_size,
        "window_minutes": minutes,
    }


def kick_out(usercode: str, operator: str, remark: str = "") -> Dict[str, Any]:
    """后台退出：在线人员表置 status=0，记录退出时间与操作人。"""
    uc = (usercode or "").strip()
    if not uc:
        raise ValueError("账号不能为空")
    execute(
        f"""
        UPDATE {T_ONLINE}
        SET status = 0, logout_time = NOW(), logout_reason = %s
        WHERE usercode = %s AND status = 1
        """,
        ((remark or f"由 {operator} 强制退出")[:100], uc),
    )
    return {"usercode": uc, "kicked": True}


# ---------------------------------------------------------------------------
# 修改个人密码（只能改自己，由 token 提供 usercode / account_id）
# ---------------------------------------------------------------------------

def change_password(
    usercode: str,
    old_password_l1: str,
    new_password_l1: str,
    account_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    修改当前登录用户自己的密码。
    - usercode 来自 JWT，不接受前端传入，无法改他人密码
    - old_password_l1 / new_password_l1 均为第一层 SHA-256 哈希（64 位 hex）
    - 只更新当前登录匹配的那条账户记录（account_id 来自 JWT）
    - 保留原 salt，生成新 pwd
    """
    uc = (usercode or "").strip()
    if not uc:
        raise ValueError("未登录")
    if not new_password_l1 or len(new_password_l1) != 64:
        raise ValueError("新密码哈希格式不正确")

    where = "usercode=%s AND dbsplitcode='1'"
    params: List[Any] = [uc]
    if account_id:
        where += " AND id=%s"
        params.append(account_id)
    rows = fetch_all(
        f"SELECT id, usercode, accountname, pwd, salt, status FROM {T_ACCOUNT} WHERE {where} ORDER BY id",
        tuple(params),
    )
    if not rows:
        raise ValueError("账户不存在")

    matched = [r for r in rows if r.get("status") == 1
               and verify_password(old_password_l1, r.get("pwd") or "", uc, r.get("salt") or "")]
    if not matched:
        raise ValueError("原密码不正确")

    row = matched[0]
    salt = str(row.get("salt") or "").strip()
    new_pwd = stage2_hash(uc, new_password_l1, salt)

    execute(
        f"UPDATE {T_ACCOUNT} SET pwd=%s, modifier=%s, modifytime=NOW() "
        f"WHERE id=%s AND dbsplitcode='1'",
        (new_pwd.upper(), uc, row["id"]),
    )

    check = fetch_one(f"SELECT pwd FROM {T_ACCOUNT} WHERE id=%s", (row["id"],))
    if not check or (check.get("pwd") or "").lower() != new_pwd:
        raise RuntimeError("密码更新校验失败，请重试")

    return {
        "usercode": uc,
        "accountname": row.get("accountname") or "",
        "changed": True,
        "hint": "密码已修改，请使用新密码重新登录",
    }
