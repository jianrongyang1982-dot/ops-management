"""
系统报障与需求管理服务

工单流转、角色解析、站内消息、附件管理。
所有业务表在 bidb 库；岗位信息来自 ucsdb（ent_account_dept_post / ent_post / ent_dept）。

角色解析：
  用户主岗位(ismain=1) -> 查 bidb.ops_issue_role_cfg -> IT_ADMIN / HANDLER
  未配置岗位的用户只有提交人权限。
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.database import execute, fetch_all, fetch_one

logger = logging.getLogger(__name__)

T_ISSUE = "bidb.ops_issue"
T_LOG = "bidb.ops_issue_log"
T_ATTACH = "bidb.ops_issue_attachment"
T_ROLE = "bidb.ops_issue_role_cfg"
T_MSG = "bidb.ops_issue_message"
T_ADP = "ucsdb.ent_account_dept_post"
T_POST = "ucsdb.ent_post"
T_DEPT = "ucsdb.ent_dept"
T_ACCOUNT = "ucsdb.account"

# 状态
ST_PENDING = 1      # 待处理
ST_ASSIGNED = 2     # 已指派
ST_PROCESSING = 3   # 处理中
ST_VERIFY = 4       # 待验证
ST_CLOSED = 5       # 已关闭
ST_CANCELLED = 6    # 已取消

STATUS_NAMES = {
    ST_PENDING: "待处理", ST_ASSIGNED: "已指派", ST_PROCESSING: "处理中",
    ST_VERIFY: "待验证", ST_CLOSED: "已关闭", ST_CANCELLED: "已取消",
}

TYPE_NAMES = {1: "需求", 2: "BUG"}
PRIORITY_NAMES = {1: "紧急", 2: "高", 3: "中", 4: "低"}

ACTION_NAMES = {
    "create": "创建", "assign": "指派", "start": "接手", "process": "提交结果",
    "verify": "验收通过", "reject": "验收不通过", "reopen": "重新打开", "cancel": "撤回",
}

MSG_TYPES = {
    "ASSIGNED": "工单指派", "PROCESSED": "处理完成", "VERIFIED": "验收通过",
    "REJECTED": "验收不通过", "REOPENED": "工单撤回",
}

# 需求结构化字段（图片模板）：键 -> 中文标签，用于后端校验提示
REQUIREMENT_FIELDS = {
    "background": "业务背景与现状",
    "pain_points": "业务问题与痛点",
    "scenario_5w1h": "需求场景(5W1H)",
    "detailed_description": "详细需求描述",
    "roles": "业务场景角色",
    "proposed_solution": "建议解决方案",
}
REQUIREMENT_REQUIRED = ("background", "pain_points", "scenario_5w1h",
                        "detailed_description", "roles")
REQUIREMENT_MAX_LEN = 20000  # 单个字段最大字符数

# 附件配置
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "issue"
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "pdf", "doc", "docx", "xls", "xlsx", "txt", "zip"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now()


def _dt(v: Any) -> str:
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return str(v) if v is not None else ""


def _val(row: Optional[Dict], key: str, default: Any = "") -> Any:
    if not row:
        return default
    v = row.get(key)
    return default if v is None else v


def _account_name(usercode: str) -> str:
    """从 ERP 账户表取姓名（取第一条即可）。"""
    if not usercode:
        return ""
    row = fetch_one(
        f"SELECT accountname FROM {T_ACCOUNT} WHERE usercode=%s AND dbsplitcode='1' ORDER BY id LIMIT 1",
        (usercode,),
    )
    return (row or {}).get("accountname") or ""


def _assert_table_ready() -> None:
    """表不存在时给出明确提示，方便用户知道要先执行 SQL。"""
    try:
        fetch_one(f"SELECT COUNT(*) n FROM {T_ISSUE} LIMIT 1")
    except Exception as exc:
        raise RuntimeError("报障模块数据表尚未创建，请先执行 deploy/sql/bidb_issue.sql") from exc


def _assert_requirement_column() -> None:
    """需求结构化字段列不存在时给出明确提示。"""
    row = fetch_one(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='bidb' AND TABLE_NAME='ops_issue' "
        "AND COLUMN_NAME='requirement_json' LIMIT 1"
    )
    if not row:
        raise RuntimeError(
            "需求字段尚未创建，请先执行 deploy/sql/bidb_issue_requirement_fields.sql"
        )


def _normalize_requirement(issue_type: int, requirement_json: Any) -> str:
    """
    校验并规范化需求结构化字段。
    - BUG 类型：忽略，返回空
    - 空值：兼容旧纯文本创建，不强制校验
    - 非空：必须是合法 JSON 对象，必填项不能为空
    """
    if issue_type != 1 or not requirement_json:
        return ""
    data = requirement_json
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (ValueError, TypeError) as exc:
            raise ValueError("需求字段格式不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("需求字段格式不正确")
    out: Dict[str, str] = {}
    for key, label in REQUIREMENT_FIELDS.items():
        value = data.get(key)
        value = "" if value is None else str(value).strip()
        if len(value) > REQUIREMENT_MAX_LEN:
            raise ValueError(f"「{label}」不能超过 {REQUIREMENT_MAX_LEN} 字符")
        out[key] = value
    for key in REQUIREMENT_REQUIRED:
        if not out[key]:
            raise ValueError(f"需求字段「{REQUIREMENT_FIELDS[key]}」不能为空")
    return json.dumps(out, ensure_ascii=False)


def _parse_requirement(raw: Any) -> Optional[Dict[str, str]]:
    """把库内 JSON 解析成前端展示用的字典；脏数据容错返回 None。"""
    if not raw:
        return None
    data = raw
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (ValueError, TypeError):
            return None
    if not isinstance(data, dict):
        return None
    return {key: str(data.get(key) or "") for key in REQUIREMENT_FIELDS}


# ---------------------------------------------------------------------------
# 角色解析
# ---------------------------------------------------------------------------

def user_roles(usercode: str) -> Dict[str, Any]:
    """
    解析用户角色：主岗位 -> 角色配置。
    返回 {usercode, accountname, postcode, postname, deptname, roles:[...], is_it_admin, is_handler}
    """
    uc = (usercode or "").strip()
    result = {
        "usercode": uc, "accountname": _account_name(uc),
        "postcode": "", "postname": "", "deptname": "",
        "roles": [], "is_it_admin": False, "is_handler": False,
    }
    if not uc:
        return result

    # 主岗位（ismain=1），兼容没有主岗位时取第一条
    post = fetch_one(
        f"""
        SELECT e.postcode, e.deptcode, p.postname, d.deptname
        FROM {T_ADP} e
        LEFT JOIN {T_POST} p ON e.postcode = p.postcode AND p.dbsplitcode = '1'
        LEFT JOIN {T_DEPT} d ON e.deptcode = d.deptcode AND d.dbsplitcode = '1'
        WHERE e.usercode = %s AND e.dbsplitcode = '1'
        ORDER BY e.ismain DESC, e.id LIMIT 1
        """,
        (uc,),
    )
    if post:
        result["postcode"] = _val(post, "postcode")
        result["postname"] = _val(post, "postname")
        result["deptname"] = _val(post, "deptname")

    # 角色配置（主岗位 + 所有岗位都算，取并集）
    rows = fetch_all(
        f"""
        SELECT DISTINCT c.role FROM {T_ROLE} c
        WHERE c.status = 1 AND c.postcode IN (
            SELECT postcode FROM {T_ADP} WHERE usercode = %s AND dbsplitcode = '1'
        )
        """,
        (uc,),
    )
    roles = [r["role"] for r in rows if r.get("role")]
    result["roles"] = roles
    result["is_it_admin"] = "IT_ADMIN" in roles
    result["is_handler"] = "HANDLER" in roles
    return result


def my_role(usercode: str) -> Dict[str, Any]:
    """供前端调用：返回当前用户的角色信息。"""
    _assert_table_ready()
    return user_roles(usercode)


def handler_options() -> List[Dict[str, str]]:
    """可选处理人：配置为 HANDLER 岗位的 ERP 用户。"""
    _assert_table_ready()
    rows = fetch_all(
        f"""SELECT DISTINCT e.usercode, a.accountname
            FROM {T_ADP} e
            JOIN {T_ROLE} c ON c.postcode = e.postcode AND c.status = 1 AND c.role = 'HANDLER'
            LEFT JOIN {T_ACCOUNT} a ON a.usercode = e.usercode AND a.dbsplitcode = '1'
            WHERE e.dbsplitcode = '1'
            ORDER BY e.usercode LIMIT 500"""
    )
    return [{"usercode": r["usercode"], "accountname": _val(r, "accountname")} for r in rows]


# ---------------------------------------------------------------------------
# 工单号
# ---------------------------------------------------------------------------

def _next_issue_no() -> str:
    day = _now().strftime("%Y%m%d")
    prefix = f"BK-{day}-"
    row = fetch_one(
        f"SELECT COUNT(*) n FROM {T_ISSUE} WHERE issue_no LIKE %s",
        (prefix + "%",),
    )
    seq = int(row["n"]) + 1 if row else 1
    # 若同日内有删除/并发，重试直到不冲突
    for attempt in range(20):
        no = f"{prefix}{seq:04d}"
        exists = fetch_one(f"SELECT id FROM {T_ISSUE} WHERE issue_no=%s", (no,))
        if not exists:
            return no
        seq += 1
    return f"{prefix}{uuid.uuid4().hex[:4].upper()}"


# ---------------------------------------------------------------------------
# 流转记录 / 站内消息
# ---------------------------------------------------------------------------

def _add_log(issue_id: int, action: str, operator: str, content: str = "") -> None:
    execute(
        f"""
        INSERT INTO {T_LOG} (issue_id, action, action_name, operator, operator_name, content, created_time)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """,
        (issue_id, action, ACTION_NAMES.get(action, action), operator,
         _account_name(operator), (content or "")[:2000]),
    )


def _send_msg(receiver: str, issue_id: int, mtype: str, title: str, content: str = "") -> None:
    if not receiver:
        return
    try:
        execute(
            f"""
            INSERT INTO {T_MSG} (receiver, issue_id, type, title, content, is_read, created_time)
            VALUES (%s, %s, %s, %s, %s, 0, NOW())
            """,
            (receiver, issue_id, mtype, (title or MSG_TYPES.get(mtype, "工单通知"))[:200],
             (content or "")[:500]),
        )
    except Exception as exc:
        logger.warning("发站内消息失败: receiver=%s issue=%s err=%s", receiver, issue_id, exc)


# ---------------------------------------------------------------------------
# 工单查询
# ---------------------------------------------------------------------------

def _row_to_item(r: Dict) -> Dict[str, Any]:
    return {
        "id": int(r["id"]),
        "issue_no": _val(r, "issue_no"),
        "issue_type": int(_val(r, "issue_type", 1)),
        "issue_type_name": TYPE_NAMES.get(int(_val(r, "issue_type", 1)), ""),
        "title": _val(r, "title"),
        "description": _val(r, "description"),
        "module": _val(r, "module"),
        "priority": int(_val(r, "priority", 3)),
        "priority_name": PRIORITY_NAMES.get(int(_val(r, "priority", 3)), ""),
        "status": int(_val(r, "status", 1)),
        "status_name": STATUS_NAMES.get(int(_val(r, "status", 1)), ""),
        "reporter": _val(r, "reporter"),
        "reporter_name": _val(r, "reporter_name"),
        "assignee": _val(r, "assignee"),
        "assignee_name": _val(r, "assignee_name"),
        "assigned_by": _val(r, "assigned_by"),
        "assigned_time": _dt(r.get("assigned_time")),
        "created_time": _dt(r.get("created_time")),
        "updated_time": _dt(r.get("updated_time")),
        "closed_time": _dt(r.get("closed_time")),
        "close_remark": _val(r, "close_remark"),
    }


def list_issues(
    scope: str = "my",
    usercode: str = "",
    status: Optional[int] = None,
    issue_type: Optional[int] = None,
    priority: Optional[int] = None,
    keyword: str = "",
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """scope: my=我提交的, monitor=全部(IT), assigned=指派给我的"""
    _assert_table_ready()
    where = ["1=1"]
    params: List[Any] = []
    uc = (usercode or "").strip()

    if scope == "my":
        where.append("reporter = %s")
        params.append(uc)
    elif scope == "assigned":
        where.append("assignee = %s")
        params.append(uc)
    # monitor: 全部

    if status in (1, 2, 3, 4, 5, 6):
        where.append("status = %s")
        params.append(status)
    if issue_type in (1, 2):
        where.append("issue_type = %s")
        params.append(issue_type)
    if priority in (1, 2, 3, 4):
        where.append("priority = %s")
        params.append(priority)
    if keyword:
        where.append("(issue_no LIKE %s OR title LIKE %s OR description LIKE %s OR module LIKE %s)")
        kw = f"%{keyword.strip()}%"
        params.extend([kw, kw, kw, kw])

    wsql = " AND ".join(where)
    total = fetch_one(f"SELECT COUNT(*) n FROM {T_ISSUE} WHERE {wsql}", tuple(params))["n"]
    rows = fetch_all(
        f"""SELECT * FROM {T_ISSUE} WHERE {wsql}
            ORDER BY
              CASE status WHEN 1 THEN 0 WHEN 2 THEN 1 WHEN 3 THEN 2 WHEN 4 THEN 3 ELSE 9 END,
              FIELD(priority, 1, 2, 3, 4),
              created_time DESC
            LIMIT %s OFFSET %s""",
        tuple(params) + (page_size, (page - 1) * page_size),
    )
    return {
        "items": [_row_to_item(r) for r in rows],
        "total": int(total), "page": page, "page_size": page_size,
    }


def issue_detail(issue_id: int) -> Dict[str, Any]:
    _assert_table_ready()
    row = fetch_one(f"SELECT * FROM {T_ISSUE} WHERE id=%s", (issue_id,))
    if not row:
        raise ValueError("工单不存在")
    item = _row_to_item(row)
    # 需求类型：把结构化字段解析成字典返回；BUG 或旧数据返回 None
    item["requirement"] = (
        _parse_requirement(row.get("requirement_json"))
        if int(_val(row, "issue_type", 1)) == 1 else None
    )

    logs = fetch_all(
        f"SELECT action, action_name, operator, operator_name, content, created_time "
        f"FROM {T_LOG} WHERE issue_id=%s ORDER BY created_time ASC, id ASC", (issue_id,),
    )
    item["logs"] = [{
        "action": l.get("action"), "action_name": l.get("action_name"),
        "operator": l.get("operator"), "operator_name": l.get("operator_name"),
        "content": l.get("content") or "", "created_time": _dt(l.get("created_time")),
    } for l in logs]

    atts = fetch_all(
        f"SELECT id, file_name, file_path, file_size, file_type, uploader, created_time "
        f"FROM {T_ATTACH} WHERE issue_id=%s ORDER BY id", (issue_id,),
    )
    item["attachments"] = [{
        "id": int(a["id"]), "file_name": a.get("file_name") or "",
        "file_size": int(a.get("file_size") or 0),
        "file_type": a.get("file_type") or "",
        "uploader": a.get("uploader") or "",
        "created_time": _dt(a.get("created_time")),
    } for a in atts]
    return item


def dashboard_counts(usercode: str, is_it_admin: bool = False) -> Dict[str, int]:
    """统计卡片：IT 看全部，其他人看自己提交的。"""
    _assert_table_ready()
    if is_it_admin:
        cond, params = "1=1", ()
    else:
        cond, params = "reporter = %s", (usercode,)
    rows = fetch_all(f"SELECT status, COUNT(*) n FROM {T_ISSUE} WHERE {cond} GROUP BY status", params)
    d = {STATUS_NAMES.get(k, str(k)): 0 for k in STATUS_NAMES}
    d["全部"] = 0
    for r in rows:
        s = int(r["status"])
        d[STATUS_NAMES.get(s, str(s))] = int(r["n"])
        d["全部"] += int(r["n"])
    return d


# ---------------------------------------------------------------------------
# 工单操作
# ---------------------------------------------------------------------------

def create_issue(
    usercode: str, title: str, description: str, issue_type: int = 1,
    module: str = "", priority: int = 3, requirement_json: Any = "",
) -> Dict[str, Any]:
    _assert_table_ready()
    uc = (usercode or "").strip()
    title = (title or "").strip()
    if not uc:
        raise ValueError("未登录")
    if not title:
        raise ValueError("标题不能为空")
    if issue_type not in (1, 2):
        raise ValueError("类型只能为需求或BUG")
    if priority not in (1, 2, 3, 4):
        priority = 3
    req_json = _normalize_requirement(issue_type, requirement_json)
    _assert_requirement_column()

    no = _next_issue_no()
    name = _account_name(uc)
    now = _now()
    execute(
        f"""
        INSERT INTO {T_ISSUE}
          (issue_no, issue_type, title, description, requirement_json, module, priority, status,
           reporter, reporter_name, created_time, updated_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (no, issue_type, title, (description or "")[:10000], req_json, (module or "")[:100],
         priority, ST_PENDING, uc, name, now, now),
    )
    row = fetch_one(f"SELECT id FROM {T_ISSUE} WHERE issue_no=%s", (no,))
    iid = int(row["id"])
    _add_log(iid, "create", uc, f"提交{TYPE_NAMES.get(issue_type, '')}：{title}")

    # 通知所有 IT 管理员
    admins = fetch_all(
        f"""SELECT DISTINCT e.usercode FROM {T_ADP} e
            JOIN {T_ROLE} c ON c.postcode = e.postcode AND c.status = 1
            WHERE c.role = 'IT_ADMIN' AND e.dbsplitcode = '1'"""
    )
    for a in admins:
        _send_msg(a["usercode"], iid, "ASSIGNED", f"新报障待处理：{title[:50]}", f"提交人：{name}")

    return {"id": iid, "issue_no": no, "created": True}


def _can_operate(issue_id: int, usercode: str, roles: List[str], allow: List[str]) -> Tuple[Dict, bool]:
    """判断用户是否有权操作工单：IT_ADMIN 恒可；否则按 allow 中的角色 + 提交人/处理人判断。"""
    row = fetch_one(f"SELECT * FROM {T_ISSUE} WHERE id=%s", (issue_id,))
    if not row:
        raise ValueError("工单不存在")
    ok = "IT_ADMIN" in roles
    if not ok:
        if "reporter" in allow and row.get("reporter") == usercode:
            ok = True
        if "assignee" in allow and row.get("assignee") == usercode:
            ok = True
        if any(r in roles for r in allow if r in ("IT_ADMIN", "HANDLER")):
            ok = True
    return row, ok


def assign_issue(issue_id: int, assignee: str, operator: str, roles: List[str]) -> Dict[str, Any]:
    """IT 指派处理人。"""
    _assert_table_ready()
    assignee = (assignee or "").strip()
    if not assignee:
        raise ValueError("请选择处理人")
    row, ok = _can_operate(issue_id, operator, roles, ["IT_ADMIN"])
    if not ok:
        raise ValueError("只有 IT 管理员可以指派")
    if int(row["status"]) not in (ST_PENDING, ST_ASSIGNED, ST_PROCESSING):
        raise ValueError("当前状态不允许指派")

    aname = _account_name(assignee)
    execute(
        f"""UPDATE {T_ISSUE}
            SET assignee=%s, assignee_name=%s, assigned_by=%s, assigned_time=NOW(),
                status=%s, updated_time=NOW()
            WHERE id=%s""",
        (assignee, aname, operator, ST_ASSIGNED, issue_id),
    )
    _add_log(issue_id, "assign", operator, f"指派给 {assignee} {aname}")
    _send_msg(assignee, issue_id, "ASSIGNED", f"工单已指派给你：{_val(row, 'title')[:50]}",
              f"指派人：{_account_name(operator)}")
    return {"id": issue_id, "assigned": True}


def start_issue(issue_id: int, operator: str, roles: List[str]) -> Dict[str, Any]:
    """处理人接手。"""
    _assert_table_ready()
    row, ok = _can_operate(issue_id, operator, roles, ["assignee", "HANDLER"])
    if not ok:
        raise ValueError("只有处理人可以接手")
    if int(row["status"]) != ST_ASSIGNED:
        raise ValueError("只有已指派状态的工单可以接手")
    if row.get("assignee") != operator and "IT_ADMIN" not in roles:
        raise ValueError("该工单指派给了其他人")

    execute(f"UPDATE {T_ISSUE} SET status=%s, updated_time=NOW() WHERE id=%s", (ST_PROCESSING, issue_id))
    _add_log(issue_id, "start", operator, "开始处理")
    return {"id": issue_id, "started": True}


def process_issue(issue_id: int, operator: str, roles: List[str], content: str = "") -> Dict[str, Any]:
    """处理人提交结果 -> 待验证。"""
    _assert_table_ready()
    row, ok = _can_operate(issue_id, operator, roles, ["assignee", "HANDLER"])
    if not ok:
        raise ValueError("只有处理人可以提交结果")
    if int(row["status"]) != ST_PROCESSING:
        raise ValueError("只有处理中状态的工单可以提交结果")
    if row.get("assignee") != operator and "IT_ADMIN" not in roles:
        raise ValueError("该工单指派给了其他人")

    execute(f"UPDATE {T_ISSUE} SET status=%s, updated_time=NOW() WHERE id=%s", (ST_VERIFY, issue_id))
    _add_log(issue_id, "process", operator, content or "提交处理结果")
    _send_msg(_val(row, "reporter"), issue_id, "PROCESSED",
              f"工单处理完成，请验收：{_val(row, 'title')[:50]}", (content or "")[:200])
    return {"id": issue_id, "submitted": True}


def verify_issue(issue_id: int, operator: str, roles: List[str], passed: bool, remark: str = "") -> Dict[str, Any]:
    """提交人验收：通过 -> 关闭；不通过 -> 退回处理中。"""
    _assert_table_ready()
    row, ok = _can_operate(issue_id, operator, roles, ["reporter"])
    if not ok:
        raise ValueError("只有提交人可以验收")
    if int(row["status"]) != ST_VERIFY:
        raise ValueError("只有待验证状态的工单可以验收")

    if passed:
        execute(
            f"UPDATE {T_ISSUE} SET status=%s, closed_time=NOW(), close_remark=%s, updated_time=NOW() WHERE id=%s",
            (ST_CLOSED, (remark or "验收通过")[:500], issue_id),
        )
        _add_log(issue_id, "verify", operator, remark or "验收通过")
        _send_msg(_val(row, "assignee"), issue_id, "VERIFIED", f"工单已验收通过：{_val(row, 'title')[:50]}")
        _send_msg(_val(row, "assigned_by"), issue_id, "VERIFIED", f"工单已验收通过：{_val(row, 'title')[:50]}")
        return {"id": issue_id, "closed": True}
    else:
        execute(
            f"UPDATE {T_ISSUE} SET status=%s, close_remark=%s, updated_time=NOW() WHERE id=%s",
            (ST_PROCESSING, (remark or "验收不通过")[:500], issue_id),
        )
        _add_log(issue_id, "reject", operator, remark or "验收不通过，退回处理")
        _send_msg(_val(row, "assignee"), issue_id, "REJECTED",
                  f"工单验收不通过：{_val(row, 'title')[:50]}", (remark or "")[:200])
        return {"id": issue_id, "reopened": True}


def cancel_issue(issue_id: int, operator: str, roles: List[str], remark: str = "") -> Dict[str, Any]:
    """提交人撤回（仅待处理/已指派）。"""
    _assert_table_ready()
    row, ok = _can_operate(issue_id, operator, roles, ["reporter"])
    if not ok:
        raise ValueError("只有提交人可以撤回")
    if int(row["status"]) not in (ST_PENDING, ST_ASSIGNED):
        raise ValueError("当前状态不允许撤回")

    execute(
        f"UPDATE {T_ISSUE} SET status=%s, close_remark=%s, closed_time=NOW(), updated_time=NOW() WHERE id=%s",
        (ST_CANCELLED, (remark or "提交人撤回")[:500], issue_id),
    )
    _add_log(issue_id, "cancel", operator, remark or "提交人撤回")
    if row.get("assignee"):
        _send_msg(row["assignee"], issue_id, "REOPENED", f"工单已撤回：{_val(row, 'title')[:50]}")
    return {"id": issue_id, "cancelled": True}


def force_close(issue_id: int, operator: str, roles: List[str], remark: str = "") -> Dict[str, Any]:
    """IT 管理员强制关闭。"""
    _assert_table_ready()
    row, ok = _can_operate(issue_id, operator, roles, ["IT_ADMIN"])
    if not ok:
        raise ValueError("只有 IT 管理员可以强制关闭")
    if int(row["status"]) in (ST_CLOSED, ST_CANCELLED):
        raise ValueError("工单已结束")

    execute(
        f"UPDATE {T_ISSUE} SET status=%s, closed_time=NOW(), close_remark=%s, updated_time=NOW() WHERE id=%s",
        (ST_CLOSED, (remark or "IT强制关闭")[:500], issue_id),
    )
    _add_log(issue_id, "verify", operator, remark or "IT强制关闭")
    _send_msg(_val(row, "reporter"), issue_id, "VERIFIED", f"工单已关闭：{_val(row, 'title')[:50]}")
    return {"id": issue_id, "closed": True}


# ---------------------------------------------------------------------------
# 附件
# ---------------------------------------------------------------------------

def create_issue_with_files(
    usercode: str, title: str, description: str, issue_type: int,
    module: str, priority: int, files: List[Tuple[str, bytes]],
    requirement_json: Any = "",
) -> Dict[str, Any]:
    """
    新建工单并同时上传附件（一次性提交）。
    任一附件校验或写入失败时，补偿删除已创建的工单及已写入的文件/附件记录。
    """
    # 1. 先校验所有附件，避免建了工单才发现文件不合法
    for file_name, data in files:
        ext = (file_name or "").rsplit(".", 1)[-1].lower() if "." in (file_name or "") else ""
        if ext not in ALLOWED_EXT:
            raise ValueError(f"不支持的文件类型：{ext or '无扩展名'}")
        if len(data) > MAX_FILE_SIZE:
            raise ValueError(f"文件 {file_name} 超过 10MB")

    # 2. 创建工单
    created = create_issue(
        usercode, title, description, issue_type, module, priority, requirement_json
    )
    iid = int(created["id"])
    saved_rel_paths: List[str] = []

    try:
        for file_name, data in files:
            ext = file_name.rsplit(".", 1)[-1].lower()
            day = _now().strftime("%Y%m%d")
            folder = UPLOAD_DIR / day
            folder.mkdir(parents=True, exist_ok=True)
            saved = f"{uuid.uuid4().hex}.{ext}"
            path = folder / saved
            path.write_bytes(data)
            rel = f"uploads/issue/{day}/{saved}"
            saved_rel_paths.append(rel)
            execute(
                f"""
                INSERT INTO {T_ATTACH} (issue_id, file_name, file_path, file_size, file_type, uploader, created_time)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (iid, file_name[:255], rel, len(data), ext, usercode),
            )
        if files:
            _add_log(iid, "create", usercode, f"随工单上传 {len(files)} 个附件")
    except Exception:
        # 补偿：删除已写文件、附件记录、工单及其日志/消息
        for rel in saved_rel_paths:
            try:
                (Path(__file__).resolve().parents[2] / rel).unlink(missing_ok=True)
            except Exception:
                pass
        try:
            execute(f"DELETE FROM {T_ATTACH} WHERE issue_id=%s", (iid,))
            execute(f"DELETE FROM {T_LOG} WHERE issue_id=%s", (iid,))
            execute(f"DELETE FROM {T_MSG} WHERE issue_id=%s", (iid,))
            execute(f"DELETE FROM {T_ISSUE} WHERE id=%s", (iid,))
        except Exception as exc:
            logger.error("新建报障补偿清理失败: issue=%s err=%s", iid, exc)
        raise

    return created


def save_attachment(issue_id: int, file_name: str, data: bytes, uploader: str) -> Dict[str, Any]:
    _assert_table_ready()
    if not fetch_one(f"SELECT id FROM {T_ISSUE} WHERE id=%s", (issue_id,)):
        raise ValueError("工单不存在")
    ext = (file_name or "").rsplit(".", 1)[-1].lower() if "." in (file_name or "") else ""
    if ext not in ALLOWED_EXT:
        raise ValueError(f"不支持的文件类型：{ext or '无扩展名'}")
    if len(data) > MAX_FILE_SIZE:
        raise ValueError("文件大小不能超过 10MB")

    day = _now().strftime("%Y%m%d")
    folder = UPLOAD_DIR / day
    folder.mkdir(parents=True, exist_ok=True)
    saved = f"{uuid.uuid4().hex}.{ext}"
    path = folder / saved
    path.write_bytes(data)
    rel = f"uploads/issue/{day}/{saved}"

    execute(
        f"""
        INSERT INTO {T_ATTACH} (issue_id, file_name, file_path, file_size, file_type, uploader, created_time)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """,
        (issue_id, (file_name or saved)[:255], rel, len(data), ext, uploader),
    )
    _add_log(issue_id, "create", uploader, f"上传附件：{file_name}")
    return {"file_name": file_name, "file_size": len(data)}


def attachment_path(attach_id: int) -> Tuple[str, str]:
    """返回 (绝对路径, 原始文件名)。"""
    row = fetch_one(f"SELECT file_path, file_name FROM {T_ATTACH} WHERE id=%s", (attach_id,))
    if not row:
        raise ValueError("附件不存在")
    rel = row["file_path"]
    base = Path(__file__).resolve().parents[2]
    path = base / rel
    if not path.exists():
        raise ValueError("附件文件已丢失")
    return str(path), row["file_name"] or "attachment"


# ---------------------------------------------------------------------------
# 角色配置
# ---------------------------------------------------------------------------

def erp_posts(keyword: str = "") -> List[Dict[str, Any]]:
    """从 ERP 取岗位列表，供配置页面勾选。"""
    where, params = ["p.dbsplitcode='1'", "p.status=1"], []
    if keyword:
        where.append("(p.postcode LIKE %s OR p.postname LIKE %s)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    rows = fetch_all(
        f"""SELECT p.postcode, p.postname,
                   (SELECT COUNT(*) FROM {T_ADP} e WHERE e.postcode=p.postcode AND e.usercode IS NOT NULL) user_count
            FROM {T_POST} p
            WHERE {' AND '.join(where)}
            ORDER BY p.postcode LIMIT 500""",
        tuple(params),
    )
    return [{"postcode": r["postcode"], "postname": r["postname"] or "",
             "user_count": int(r["user_count"] or 0)} for r in rows]


def role_configs() -> List[Dict[str, Any]]:
    _assert_table_ready()
    rows = fetch_all(f"SELECT id, postcode, postname, role, status, created_time FROM {T_ROLE} ORDER BY role, postcode")
    return [{
        "id": int(r["id"]), "postcode": r["postcode"], "postname": r["postname"] or "",
        "role": r["role"], "status": int(r["status"]), "created_time": _dt(r["created_time"]),
    } for r in rows]


def add_role_config(postcode: str, postname: str, role: str) -> Dict[str, Any]:
    _assert_table_ready()
    postcode = (postcode or "").strip()
    if not postcode:
        raise ValueError("岗位编码不能为空")
    if role not in ("IT_ADMIN", "HANDLER"):
        raise ValueError("角色只能是 IT_ADMIN 或 HANDLER")
    exists = fetch_one(f"SELECT id FROM {T_ROLE} WHERE postcode=%s AND role=%s", (postcode, role))
    if exists:
        raise ValueError("该岗位已配置此角色")
    execute(
        f"INSERT INTO {T_ROLE} (postcode, postname, role, status, created_time) VALUES (%s, %s, %s, 1, NOW())",
        (postcode, (postname or "")[:200], role),
    )
    return {"postcode": postcode, "role": role, "added": True}


def delete_role_config(cfg_id: int) -> Dict[str, Any]:
    _assert_table_ready()
    execute(f"DELETE FROM {T_ROLE} WHERE id=%s", (cfg_id,))
    return {"id": cfg_id, "deleted": True}


# ---------------------------------------------------------------------------
# 站内消息
# ---------------------------------------------------------------------------

def messages(usercode: str, unread_only: bool = False, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    _assert_table_ready()
    where, params = ["receiver = %s"], [usercode]
    if unread_only:
        where.append("is_read = 0")
    wsql = " AND ".join(where)
    total = fetch_one(f"SELECT COUNT(*) n FROM {T_MSG} WHERE {wsql}", tuple(params))["n"]
    rows = fetch_all(
        f"""SELECT m.*, i.title issue_title, i.status issue_status
            FROM {T_MSG} m LEFT JOIN {T_ISSUE} i ON m.issue_id=i.id
            WHERE {wsql} ORDER BY m.created_time DESC
            LIMIT %s OFFSET %s""",
        tuple(params) + (page_size, (page - 1) * page_size),
    )
    return {
        "items": [{
            "id": int(r["id"]), "issue_id": int(r["issue_id"]),
            "type": r["type"], "type_name": MSG_TYPES.get(r["type"], r["type"]),
            "title": r["title"] or "", "content": r["content"] or "",
            "is_read": int(r["is_read"]), "created_time": _dt(r["created_time"]),
            "issue_title": r["issue_title"] or "", "issue_status": r["issue_status"],
        } for r in rows],
        "total": int(total), "page": page, "page_size": page_size,
        "unread": int(fetch_one("SELECT COUNT(*) n FROM " + T_MSG + " WHERE receiver=%s AND is_read=0", (usercode,))["n"]),
    }


def mark_read(msg_id: int, usercode: str) -> Dict[str, Any]:
    execute(f"UPDATE {T_MSG} SET is_read=1 WHERE id=%s AND receiver=%s", (msg_id, usercode))
    return {"id": msg_id, "read": True}


def mark_all_read(usercode: str) -> Dict[str, Any]:
    execute(f"UPDATE {T_MSG} SET is_read=1 WHERE receiver=%s AND is_read=0", (usercode,))
    return {"read_all": True}


def can_view_issue(issue_id: int, usercode: str, roles: List[str]) -> bool:
    """IT 可看全部；其他人只能看自己提交或处理的。"""
    if "IT_ADMIN" in roles:
        return True
    row = fetch_one(f"SELECT reporter, assignee FROM {T_ISSUE} WHERE id=%s", (issue_id,))
    if not row:
        return False
    return row.get("reporter") == usercode or row.get("assignee") == usercode
