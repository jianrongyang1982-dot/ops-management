"""
菜单 / 角色 / 权限 / 个人收藏服务

权限模型：员工(ucsdb.account.usercode) -> 角色 -> 菜单
- 员工未分配任何角色：默认可见全部菜单（兼容升级，避免升级后无菜单可用）
- 员工分配了角色：取所有角色的菜单并集；任一角色 is_admin=1 则可见全部菜单
- 收藏夹只允许收藏当前用户有权限的菜单
"""
import logging
from typing import Any, Dict, List, Optional

from app.core.database import execute, fetch_all, fetch_one

logger = logging.getLogger(__name__)

T_MENU = "bidb.ops_menu"
T_ROLE = "bidb.ops_role"
T_USER_ROLE = "bidb.ops_user_role"
T_ROLE_MENU = "bidb.ops_role_menu"
T_FAV = "bidb.ops_user_favorite"
T_ACCOUNT = "ucsdb.account"

HOME_CODE = "/home"


def _val(row: Optional[Dict], key: str, default: Any = "") -> Any:
    if not row:
        return default
    v = row.get(key)
    return default if v is None else v


def _assert_ready() -> None:
    try:
        fetch_one(f"SELECT COUNT(*) n FROM {T_MENU} LIMIT 1")
    except Exception as exc:
        raise RuntimeError("菜单权限数据表尚未创建，请先执行 deploy/sql/bidb_menu_permission.sql") from exc


# ---------------------------------------------------------------------------
# 菜单定义
# ---------------------------------------------------------------------------

def _menu_item(r: Dict) -> Dict[str, Any]:
    return {
        "code": _val(r, "menu_code"),
        "name": _val(r, "menu_name"),
        "name_en": _val(r, "menu_name_en"),
        "path": _val(r, "path"),
        "icon": _val(r, "icon"),
        "group_code": _val(r, "group_code"),
        "group_name": _val(r, "group_name"),
        "group_name_en": _val(r, "group_name_en"),
        "group_sort": int(_val(r, "group_sort", 0)),
        "sort_no": int(_val(r, "sort_no", 0)),
        "status": int(_val(r, "status", 1)),
    }


def all_menus(include_home: bool = False) -> List[Dict[str, Any]]:
    """全部启用菜单（管理配置用）。默认排除首页（首页固定标签不参与配置）。"""
    _assert_ready()
    cond = "status=1" if include_home else "status=1 AND group_code<>'home'"
    rows = fetch_all(
        f"SELECT * FROM {T_MENU} WHERE {cond} ORDER BY group_sort, sort_no, id"
    )
    return [_menu_item(r) for r in rows]


def _groups_from(menus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for m in menus:
        g = groups.setdefault(m["group_code"], {
            "code": m["group_code"],
            "name": m["group_name"],
            "name_en": m["group_name_en"],
            "sort": m["group_sort"],
            "menus": [],
        })
        g["menus"].append(m)
    return sorted(groups.values(), key=lambda g: (g["sort"], g["code"]))


# ---------------------------------------------------------------------------
# 权限判定
# ---------------------------------------------------------------------------

def user_role_codes(usercode: str) -> List[str]:
    rows = fetch_all(
        f"""SELECT ur.role_code FROM {T_USER_ROLE} ur
            JOIN {T_ROLE} r ON r.role_code=ur.role_code AND r.status=1
            WHERE ur.usercode=%s""",
        (usercode,),
    )
    return [r["role_code"] for r in rows]


def accessible_menus(usercode: str) -> List[Dict[str, Any]]:
    """当前用户有权限的菜单（已排除首页）。"""
    _assert_ready()
    roles = user_role_codes(usercode)
    if not roles:
        # 未分配角色：兼容升级，全部菜单
        return all_menus()
    marks = ",".join(["%s"] * len(roles))
    admin = fetch_one(
        f"SELECT id FROM {T_ROLE} WHERE is_admin=1 AND status=1 AND role_code IN ({marks}) LIMIT 1",
        tuple(roles),
    )
    if admin:
        return all_menus()
    rows = fetch_all(
        f"""SELECT DISTINCT m.* FROM {T_MENU} m
            JOIN {T_ROLE_MENU} rm ON rm.menu_code=m.menu_code
            WHERE rm.role_code IN ({marks}) AND m.status=1 AND m.group_code<>'home'
            ORDER BY m.group_sort, m.sort_no, m.id""",
        tuple(roles),
    )
    return [_menu_item(r) for r in rows]


def accessible_codes(usercode: str) -> List[str]:
    return [m["code"] for m in accessible_menus(usercode)]


def my_menus(usercode: str) -> Dict[str, Any]:
    """左侧动态菜单 + 收藏夹配置可选菜单。"""
    menus = accessible_menus(usercode)
    return {
        "groups": _groups_from(menus),
        "menus": menus,
        "codes": [m["code"] for m in menus],
        "has_role_limit": bool(user_role_codes(usercode)),
    }


def require_menu_access(usercode: str, menu_code: str) -> None:
    if menu_code not in accessible_codes(usercode):
        raise ValueError("无权访问该菜单")


# ---------------------------------------------------------------------------
# 个人收藏
# ---------------------------------------------------------------------------

def my_favorites(usercode: str) -> List[Dict[str, Any]]:
    """返回当前用户收藏菜单（仅保留其仍有权限的项）。"""
    _assert_ready()
    allowed = set(accessible_codes(usercode))
    rows = fetch_all(
        f"""SELECT f.menu_code, f.sort_no, f.created_time,
                   m.menu_name, m.menu_name_en, m.path, m.icon
            FROM {T_FAV} f
            LEFT JOIN {T_MENU} m ON m.menu_code=f.menu_code
            WHERE f.usercode=%s
            ORDER BY f.sort_no, f.id""",
        (usercode,),
    )
    out = []
    for r in rows:
        code = _val(r, "menu_code")
        if code not in allowed:
            continue
        out.append({
            "code": code,
            "name": _val(r, "menu_name"),
            "name_en": _val(r, "menu_name_en"),
            "path": _val(r, "path"),
            "icon": _val(r, "icon"),
            "sort_no": int(_val(r, "sort_no", 0)),
        })
    return out


def save_favorites(usercode: str, menu_codes: List[str]) -> List[Dict[str, Any]]:
    """批量保存收藏（全量替换）。只允许收藏有权限的菜单。"""
    _assert_ready()
    allowed = set(accessible_codes(usercode))
    codes = []
    for c in menu_codes or []:
        c = str(c).strip()
        if c and c in allowed and c not in codes:
            codes.append(c)
    execute(f"DELETE FROM {T_FAV} WHERE usercode=%s", (usercode,))
    for i, code in enumerate(codes):
        execute(
            f"""INSERT INTO {T_FAV} (usercode, menu_code, sort_no, created_time)
                VALUES (%s, %s, %s, NOW())""",
            (usercode, code, i),
        )
    return my_favorites(usercode)


# ---------------------------------------------------------------------------
# 角色管理
# ---------------------------------------------------------------------------

def _role_item(r: Dict) -> Dict[str, Any]:
    return {
        "id": int(r["id"]),
        "role_code": _val(r, "role_code"),
        "role_name": _val(r, "role_name"),
        "role_name_en": _val(r, "role_name_en"),
        "remark": _val(r, "remark"),
        "is_admin": bool(int(_val(r, "is_admin", 0))),
        "status": int(_val(r, "status", 1)),
        "menu_count": int(_val(r, "menu_count", 0)),
        "user_count": int(_val(r, "user_count", 0)),
    }


def roles() -> List[Dict[str, Any]]:
    _assert_ready()
    rows = fetch_all(
        f"""SELECT r.*,
              (SELECT COUNT(*) FROM {T_ROLE_MENU} rm WHERE rm.role_code=r.role_code) menu_count,
              (SELECT COUNT(*) FROM {T_USER_ROLE} ur WHERE ur.role_code=r.role_code) user_count
            FROM {T_ROLE} r ORDER BY r.id"""
    )
    return [_role_item(r) for r in rows]


def add_role(role_code: str, role_name: str, role_name_en: str = "",
             remark: str = "", is_admin: bool = False) -> Dict[str, Any]:
    _assert_ready()
    role_code = (role_code or "").strip()
    role_name = (role_name or "").strip()
    if not role_code or not role_name:
        raise ValueError("角色编码和名称不能为空")
    if fetch_one(f"SELECT id FROM {T_ROLE} WHERE role_code=%s", (role_code,)):
        raise ValueError("角色编码已存在")
    execute(
        f"""INSERT INTO {T_ROLE} (role_code, role_name, role_name_en, remark, is_admin, status, created_time, updated_time)
            VALUES (%s, %s, %s, %s, %s, 1, NOW(), NOW())""",
        (role_code, role_name, role_name_en or "", remark or "", 1 if is_admin else 0),
    )
    return {"role_code": role_code, "created": True}


def update_role(role_id: int, role_name: str, role_name_en: str = "",
                remark: str = "", status: int = 1, is_admin: bool = False) -> Dict[str, Any]:
    _assert_ready()
    row = fetch_one(f"SELECT * FROM {T_ROLE} WHERE id=%s", (role_id,))
    if not row:
        raise ValueError("角色不存在")
    execute(
        f"""UPDATE {T_ROLE} SET role_name=%s, role_name_en=%s, remark=%s,
            status=%s, is_admin=%s, updated_time=NOW() WHERE id=%s""",
        (role_name or "", role_name_en or "", remark or "", int(status),
         1 if is_admin else 0, role_id),
    )
    return {"id": role_id, "updated": True}


def delete_role(role_id: int) -> Dict[str, Any]:
    _assert_ready()
    row = fetch_one(f"SELECT * FROM {T_ROLE} WHERE id=%s", (role_id,))
    if not row:
        raise ValueError("角色不存在")
    code = row["role_code"]
    execute(f"DELETE FROM {T_ROLE_MENU} WHERE role_code=%s", (code,))
    execute(f"DELETE FROM {T_USER_ROLE} WHERE role_code=%s", (code,))
    execute(f"DELETE FROM {T_ROLE} WHERE id=%s", (role_id,))
    return {"id": role_id, "deleted": True}


def role_menus(role_code: str) -> List[str]:
    _assert_ready()
    role = fetch_one(f"SELECT * FROM {T_ROLE} WHERE role_code=%s", (role_code,))
    if not role:
        raise ValueError("角色不存在")
    if int(_val(role, "is_admin", 0)) == 1:
        return [m["code"] for m in all_menus()]
    rows = fetch_all(
        f"SELECT menu_code FROM {T_ROLE_MENU} WHERE role_code=%s", (role_code,)
    )
    return [r["menu_code"] for r in rows]


def save_role_menus(role_code: str, menu_codes: List[str]) -> Dict[str, Any]:
    _assert_ready()
    role = fetch_one(f"SELECT * FROM {T_ROLE} WHERE role_code=%s", (role_code,))
    if not role:
        raise ValueError("角色不存在")
    if int(_val(role, "is_admin", 0)) == 1:
        raise ValueError("超级管理员默认拥有全部菜单，无需配置")
    valid = set(m["code"] for m in all_menus())
    codes = [c for c in dict.fromkeys(menu_codes or []) if c in valid]
    execute(f"DELETE FROM {T_ROLE_MENU} WHERE role_code=%s", (role_code,))
    for code in codes:
        execute(
            f"INSERT INTO {T_ROLE_MENU} (role_code, menu_code, created_time) VALUES (%s, %s, NOW())",
            (role_code, code),
        )
    return {"role_code": role_code, "count": len(codes)}


# ---------------------------------------------------------------------------
# 员工-角色分配
# ---------------------------------------------------------------------------

def user_roles(usercode: str) -> List[str]:
    _assert_ready()
    return user_role_codes(usercode)


def assign_user_roles(usercode: str, role_codes: List[str]) -> Dict[str, Any]:
    _assert_ready()
    usercode = (usercode or "").strip()
    if not usercode:
        raise ValueError("员工账号不能为空")
    if not fetch_one(f"SELECT id FROM {T_ACCOUNT} WHERE usercode=%s AND dbsplitcode='1' LIMIT 1", (usercode,)):
        raise ValueError("员工账号不存在")
    codes = [c for c in dict.fromkeys(role_codes or []) if c]
    if codes:
        marks = ",".join(["%s"] * len(codes))
        valid = set(r["role_code"] for r in fetch_all(
            f"SELECT role_code FROM {T_ROLE} WHERE status=1 AND role_code IN ({marks})", tuple(codes)
        ))
        codes = [c for c in codes if c in valid]
    execute(f"DELETE FROM {T_USER_ROLE} WHERE usercode=%s", (usercode,))
    for code in codes:
        execute(
            f"INSERT INTO {T_USER_ROLE} (usercode, role_code, created_time) VALUES (%s, %s, NOW())",
            (usercode, code),
        )
    return {"usercode": usercode, "roles": codes}


def search_users(keyword: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    _assert_ready()
    where = "dbsplitcode='1'"
    params: List[Any] = []
    if keyword:
        kw = f"%{keyword.strip()}%"
        where += " AND (usercode LIKE %s OR accountname LIKE %s)"
        params.extend([kw, kw])
    total = fetch_one(f"SELECT COUNT(*) n FROM {T_ACCOUNT} WHERE {where}", tuple(params))["n"]
    rows = fetch_all(
        f"""SELECT usercode, accountname FROM {T_ACCOUNT}
            WHERE {where} ORDER BY usercode LIMIT %s OFFSET %s""",
        tuple(params) + (page_size, (page - 1) * page_size),
    )
    items = []
    for r in rows:
        uc = r["usercode"]
        items.append({
            "usercode": uc,
            "accountname": _val(r, "accountname"),
            "roles": user_role_codes(uc),
        })
    return {"items": items, "total": int(total), "page": page, "page_size": page_size}
