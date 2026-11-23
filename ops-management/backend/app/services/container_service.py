"""
集装箱数据访问服务：录入、查询、编辑、导入
"""
import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Any, Tuple

from app.core.database import fetch_all, fetch_one, execute, pool

logger = logging.getLogger(__name__)

TABLE = "transit_containers"

def _table_columns() -> set:
    """动态读取表实际字段，兼容 sn/voyage 等字段是否存在"""
    try:
        return {r["Field"] for r in fetch_all(f"SHOW COLUMNS FROM {TABLE}")}
    except Exception:
        return set()

COLUMNS = _table_columns()

def has_col(name: str) -> bool:
    return name in COLUMNS

# 录入字段 -> 表字段（sn/voyage 视实际情况启用）
FIELD_MAP = {
    "sn": "sn",
    "brand": "brand",
    "wh": "wh",
    "forwarder": "forwarder",
    "cargotype": "cargotype",
    "bl": "bl",
    "ship_co": "ship_co",
    "ship_name": "ship_name",
    "container_no": "container_no",
    "warehousebinno": "warehousebinno",
    "pol": "pol",
    "pod": "pod",
    "load_date": "load_date",
    "eta": "eta",
    "remark": "remark",
}

# 计算列
PERIOD_SQL = "DATEDIFF(eta, load_date) AS period"
# 实际天数 = 提柜日期(stcsdate) - 装船日期(loaddate)
# 计划天数 = 计划到达(plandate) - 装船日期(loaddate)，plandate 为空时为 NULL（不计算）
DAYS_SQL = (
    "DATEDIFF(stcsdate, loaddate) AS actual_days, "
    "DATEDIFF(plandate, loaddate) AS plan_days"
)
STATUS_SQL = (
    "CASE "
    "WHEN acdate IS NOT NULL AND rcvedate IS NOT NULL THEN '已完成' "
    "WHEN acdate IS NOT NULL AND stcsdate IS NULL THEN '待提柜' "
    "WHEN acdate IS NOT NULL THEN '已到港' "
    "WHEN eta IS NOT NULL AND eta < CURDATE() THEN '延误' "
    "ELSE '在途' END AS status"
)
DELAY_SQL = (
    "CASE WHEN acdate IS NULL AND eta IS NOT NULL AND eta < CURDATE() "
    "THEN DATEDIFF(CURDATE(), eta) ELSE 0 END AS delay_days"
)


def _row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """序列化日期为字符串"""
    if not row:
        return row
    out = dict(row)
    for k, v in list(out.items()):
        if isinstance(v, (datetime, date)):
            out[k] = v.strftime("%Y-%m-%d %H:%M:%S" if isinstance(v, datetime) else "%Y-%m-%d")
    return out


def compute_period(load_date, eta) -> Optional[int]:
    if load_date and eta:
        try:
            ld = load_date.date() if isinstance(load_date, datetime) else load_date
            ed = eta.date() if isinstance(eta, datetime) else eta
            return (ed - ld).days
        except Exception:
            return None
    return None


def exists_duplicate(brand: str, bl: Optional[str], container_no: str, exclude_id: int = 0) -> bool:
    """去重：brand + bl + container_no"""
    sql = (
        f"SELECT id FROM {TABLE} WHERE brand=%s AND container_no=%s "
        "AND ((bl=%s) OR (bl IS NULL AND %s IS NULL)) AND id<>%s LIMIT 1"
    )
    row = fetch_one(sql, (brand, container_no, bl, bl, exclude_id))
    return row is not None


def build_insert(data: Dict[str, Any], creator: str) -> Tuple[str, tuple]:
    """构建 INSERT SQL。creator 存 usercode，dbsplitcode 默认1，period 计算，flag 默认0"""
    fields = []
    values = []
    params = []
    for key, col in FIELD_MAP.items():
        if key in data and data[key] is not None and has_col(col):
            fields.append(col)
            values.append("%s")
            params.append(data[key])
    # period
    period = compute_period(data.get("load_date"), data.get("eta"))
    if period is not None and has_col("period"):
        fields.append("period")
        values.append("%s")
        params.append(period)
    # 系统字段
    fields += ["creator", "flag", "dbsplitcode"]
    values += ["%s", "%s", "%s"]
    params += [creator, 0, "1"]
    sql = f"INSERT INTO {TABLE} ({', '.join(fields)}) VALUES ({', '.join(values)})"
    return sql, tuple(params)


def build_update(data: Dict[str, Any], id: int) -> Tuple[str, tuple]:
    sets = []
    params = []
    for key, col in FIELD_MAP.items():
        if key in data and data[key] is not None and has_col(col):
            sets.append(f"{col}=%s")
            params.append(data[key])
    period = compute_period(data.get("load_date"), data.get("eta"))
    if period is not None and has_col("period"):
        sets.append("period=%s")
        params.append(period)
    if not sets:
        return "", ()
    params.append(id)
    return f"UPDATE {TABLE} SET {', '.join(sets)} WHERE id=%s", tuple(params)


def create_container(data: Dict[str, Any], creator: str) -> Dict[str, Any]:
    sql, params = build_insert(data, creator)
    with pool.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            new_id = cur.lastrowid
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {TABLE} WHERE id=%s", (new_id,))
            row = cur.fetchone()
    return _row_to_dict(row)


def update_container(data: Dict[str, Any], id: int) -> Optional[Dict[str, Any]]:
    sql, params = build_update(data, id)
    if not sql:
        return fetch_one(f"SELECT * FROM {TABLE} WHERE id=%s", (id,))
    execute(sql, params)
    return _row_to_dict(fetch_one(f"SELECT * FROM {TABLE} WHERE id=%s", (id,)))


def get_container(id: int) -> Optional[Dict[str, Any]]:
    return _row_to_dict(fetch_one(f"SELECT * FROM {TABLE} WHERE id=%s", (id,)))


def delete_container(id: int) -> bool:
    return execute(f"DELETE FROM {TABLE} WHERE id=%s", (id,)) > 0


def reset_flag(id: int) -> bool:
    """把 flag 从 100 重置为 0，使记录恢复自动同步"""
    return execute(f"UPDATE {TABLE} SET flag=0 WHERE id=%s AND flag=100", (id,)) > 0


def query_containers(
    filters: Dict[str, Any], page: int = 1, page_size: int = 20
) -> Tuple[int, List[Dict[str, Any]]]:
    where = []
    params: List[Any] = []

    def eq(col, val):
        if val is not None and str(val).strip() != "":
            where.append(f"{col}=%s")
            params.append(val)

    eq("brand", filters.get("brand"))
    eq("wh", filters.get("wh"))
    eq("forwarder", filters.get("forwarder"))
    eq("ship_co", filters.get("ship_co"))
    eq("cargotype", filters.get("cargotype"))
    eq("flag", filters.get("flag"))

    for key in ("bl", "container_no", "ship_name", "warehousebinno"):
        val = filters.get(key)
        if val and str(val).strip():
            where.append(f"{key} LIKE %s")
            params.append(f"%{val}%")

    if filters.get("pol"):
        where.append("pol LIKE %s")
        params.append(f"%{filters['pol']}%")
    if filters.get("pod"):
        where.append("pod LIKE %s")
        params.append(f"%{filters['pod']}%")

    if filters.get("load_date_from"):
        where.append("load_date>=%s")
        params.append(filters["load_date_from"])
    if filters.get("load_date_to"):
        where.append("load_date<=%s")
        params.append(filters["load_date_to"] + " 23:59:59")
    if filters.get("eta_from"):
        where.append("eta>=%s")
        params.append(filters["eta_from"])
    if filters.get("eta_to"):
        where.append("eta<=%s")
        params.append(filters["eta_to"] + " 23:59:59")

    status = filters.get("status")
    if status:
        status_map = {
            "在途": "acdate IS NULL AND (eta IS NULL OR eta>=CURDATE())",
            "延误": "acdate IS NULL AND eta<CURDATE()",
            "已到港": "acdate IS NOT NULL AND stcsdate IS NOT NULL",
            "待提柜": "acdate IS NOT NULL AND stcsdate IS NULL",
            "已完成": "rcvedate IS NOT NULL",
        }
        if status in status_map:
            where.append(status_map[status])

    where_sql = " AND ".join(where) if where else "1=1"
    total = fetch_one(f"SELECT COUNT(*) AS cnt FROM {TABLE} WHERE {where_sql}", tuple(params))["cnt"]

    cols = (
        "*, (SELECT brandname FROM mdmbasedb.brand b "
        f"WHERE (b.note={TABLE}.brand OR b.brandid={TABLE}.brand) "
        "AND b.dbsplitcode=1 LIMIT 1) AS brand_name, "
        f"{PERIOD_SQL}, {DAYS_SQL}, {STATUS_SQL}, {DELAY_SQL} "
    )
    offset = (page - 1) * page_size
    sql = (
        f"SELECT {cols} FROM {TABLE} WHERE {where_sql} "
        f"ORDER BY id DESC LIMIT %s OFFSET %s"
    )
    rows = fetch_all(sql, tuple(params) + (page_size, offset))
    return total, [_row_to_dict(r) for r in rows]


def get_all_for_sync() -> List[Dict[str, Any]]:
    """获取待同步数据：未关单（acdate 为空）且未完成（flag<>100）"""
    return fetch_all(
        f"SELECT id, brand, bl, container_no FROM {TABLE} "
        "WHERE acdate IS NULL AND (flag IS NULL OR flag<>100) "
        "AND bl IS NOT NULL AND bl<>'' "
        "ORDER BY bl, id"
    )


def get_all_for_logistics_sync() -> List[Dict[str, Any]]:
    """获取待物流同步数据：仅商品(cargotype=0)且未完成(flag<>100)"""
    return fetch_all(
        f"SELECT id, brand, container_no FROM {TABLE} "
        "WHERE (cargotype=0) AND (flag IS NULL OR flag<>100) "
        "AND container_no IS NOT NULL AND container_no<>'' "
        "ORDER BY id"
    )
