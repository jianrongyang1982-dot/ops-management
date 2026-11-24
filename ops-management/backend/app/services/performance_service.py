"""
绩效系数服务 - iscewmsdb.westlake_WorkPrice

业务键：(ownerid, cateid, workmode)
导入策略：键已存在只更新 price1/price2/price3，不存在则插入，不删除任何数据。
"""
import math
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any, Dict, List, Tuple

from openpyxl import Workbook, load_workbook

from app.core import wms_database

TABLE = "iscewmsdb.westlake_WorkPrice"
BASE_COLUMNS = (
    "id, ownerid, cateid, catename, price1, price2, price3, workmode, "
    "creator, createTime, modifier, modifytime"
)
WORKMODE_SQL = (
    "SELECT fieldvalue AS value, lookup AS label "
    "FROM iscemdmdb.lookupitem WHERE lookupid='Work_Mode' ORDER BY fieldvalue"
)
CATEGORY_SQL = (
    "SELECT DISTINCT cateid, catename FROM iscemdmdb.bmclassowner "
    "WHERE LENGTH(cateid)=3 ORDER BY cateid"
)
REQUIRED_COLUMNS = ["ownerid", "cateid", "catename", "price1", "price2", "price3"]
WORKMODE_OPTIONS = {"1": "Picking", "2": "Scanning", "3": "Replenishment"}
WORKMODE_ALIASES = {
    "1": "1", "picking": "1", "拣货": "1",
    "2": "2", "scanning": "2", "扫码": "2", "扫描": "2",
    "3": "3", "replenishment": "3", "补货": "3",
}
DEFAULT_WORKMODE = "1"
UPSERT_KEYS = ("ownerid", "cateid", "workmode")
UPDATE_COLUMNS = ("price1", "price2", "price3")
FIXED_DBSPLITCODE = 1
FIXED_USER = "sys"
EXPORT_HEADERS = [
    "id", "ownerid", "workmode", "cateid", "catename",
    "price1", "price2", "price3",
    "createTime", "modifytime", "creator", "modifier",
]


# ---------------------------------------------------------------------------
# 数据清洗
# ---------------------------------------------------------------------------
def to_str(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip()
    return s or None


def to_decimal(val: Any) -> Decimal:
    if val is None:
        return Decimal("0")
    if isinstance(val, float) and math.isnan(val):
        return Decimal("0")
    try:
        return Decimal(str(val).strip() or "0")
    except (InvalidOperation, ValueError):
        raise ValueError("价格必须为数字：%s" % val)


def to_workmode(val: Any) -> Tuple[str, str | None]:
    if val is None:
        return DEFAULT_WORKMODE, None
    if isinstance(val, float):
        if math.isnan(val):
            return DEFAULT_WORKMODE, None
        s = str(int(val)) if val.is_integer() else str(val)
    else:
        s = str(val).strip()
    if not s:
        return DEFAULT_WORKMODE, None
    normalized = WORKMODE_ALIASES.get(s.lower(), s)
    if normalized not in WORKMODE_OPTIONS:
        return normalized, "workmode='%s' 不是 1/2/3，已保留原值" % s
    return normalized, None


def key_value(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


def make_key(rec: Dict[str, Any]) -> Tuple[str, str, str]:
    return tuple(key_value(rec.get(c)) for c in UPSERT_KEYS)


def get_workmode_options() -> List[Dict[str, str]]:
    rows = wms_database.fetch_all(WORKMODE_SQL)
    return [
        {"value": str(r["value"]).strip(), "label": str(r["label"]).strip()}
        for r in rows
        if r.get("value") and r.get("label")
    ]


def get_category_options() -> List[Dict[str, str]]:
    rows = wms_database.fetch_all(CATEGORY_SQL)
    return [
        {"cateid": str(r["cateid"]).strip(), "catename": str(r.get("catename") or "").strip()}
        for r in rows
        if r.get("cateid")
    ]


def _row_out(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    for key in ("price1", "price2", "price3"):
        if out.get(key) is not None:
            out[key] = float(out[key])
    for key in ("createTime", "modifytime"):
        value = out.get(key)
        if hasattr(value, "strftime"):
            out[key] = value.strftime("%Y-%m-%d %H:%M:%S")
    return out


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    ownerid = to_str(payload.get("ownerid"))
    if not ownerid:
        raise ValueError("ownerid 不能为空")
    cateid = to_str(payload.get("cateid"))
    if cateid and len(cateid) > 3:
        raise ValueError("cateid 最多 3 个字符")
    workmode, warning = to_workmode(payload.get("workmode"))
    return {
        "ownerid": ownerid,
        "cateid": cateid,
        "catename": to_str(payload.get("catename")),
        "price1": to_decimal(payload.get("price1")),
        "price2": to_decimal(payload.get("price2")),
        "price3": to_decimal(payload.get("price3")),
        "workmode": workmode,
        "_warning": warning,
    }


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------
def _where(filters: Dict[str, Any]) -> Tuple[str, tuple]:
    clauses: List[str] = []
    params: List[Any] = []
    for field in ("ownerid", "cateid", "workmode"):
        value = filters.get(field)
        if value not in (None, ""):
            clauses.append(f"{field} = %s")
            params.append(str(value).strip())
    catename = filters.get("catename")
    if catename not in (None, ""):
        clauses.append("catename LIKE %s")
        params.append("%" + str(catename).strip() + "%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, tuple(params)


def query(filters: Dict[str, Any], page: int, page_size: int) -> Tuple[int, List[Dict[str, Any]]]:
    where, params = _where(filters)
    total = wms_database.fetch_one(
        f"SELECT COUNT(*) AS n FROM {TABLE}{where}", params
    )["n"]
    rows = wms_database.fetch_all(
        f"SELECT {BASE_COLUMNS} FROM {TABLE}{where} ORDER BY id LIMIT %s OFFSET %s",
        params + (page_size, (page - 1) * page_size),
    )
    return total, [_row_out(r) for r in rows]


def query_all(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    where, params = _where(filters)
    rows = wms_database.fetch_all(
        f"SELECT {BASE_COLUMNS} FROM {TABLE}{where} ORDER BY id", params
    )
    return [_row_out(r) for r in rows]


def get_by_id(id: int) -> Dict[str, Any] | None:
    row = wms_database.fetch_one(
        f"SELECT {BASE_COLUMNS} FROM {TABLE} WHERE id = %s", (id,)
    )
    return _row_out(row) if row else None


def _find_by_key(conn, rec: Dict[str, Any]):
    if rec.get("cateid") is None:
        sql = (
            f"SELECT {BASE_COLUMNS} FROM {TABLE} "
            "WHERE ownerid=%s AND cateid IS NULL AND workmode=%s LIMIT 1"
        )
        params = (key_value(rec["ownerid"]), key_value(rec["workmode"]))
    else:
        sql = (
            f"SELECT {BASE_COLUMNS} FROM {TABLE} "
            "WHERE ownerid=%s AND cateid=%s AND workmode=%s LIMIT 1"
        )
        params = (
            key_value(rec["ownerid"]),
            key_value(rec["cateid"]),
            key_value(rec["workmode"]),
        )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


# ---------------------------------------------------------------------------
# 增删改
# ---------------------------------------------------------------------------
def create(payload: Dict[str, Any]) -> Dict[str, Any]:
    rec = _normalize_payload(payload)
    with wms_database.transaction() as conn:
        if _find_by_key(conn, rec):
            raise ValueError("业务键(ownerid + cateid + workmode)已存在")
        with conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {TABLE}")
            new_id = cur.fetchone()["max_id"] + 1
            cur.execute(
                f"INSERT INTO {TABLE} "
                "(id, ownerid, cateid, catename, price1, price2, price3, "
                "dbsplitcode, creator, modifier, createTime, modifytime, workmode) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)",
                (
                    new_id, rec["ownerid"], rec["cateid"], rec["catename"],
                    rec["price1"], rec["price2"], rec["price3"],
                    FIXED_DBSPLITCODE, FIXED_USER, FIXED_USER, rec["workmode"],
                ),
            )
    return get_by_id(new_id)


def update(id: int, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    rec = _normalize_payload(payload)
    with wms_database.transaction() as conn:
        if not get_by_id(id):
            return None
        duplicate = _find_by_key(conn, rec)
        if duplicate and int(duplicate["id"]) != id:
            raise ValueError("业务键(ownerid + cateid + workmode)已存在")
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {TABLE} SET ownerid=%s, cateid=%s, catename=%s, "
                "price1=%s, price2=%s, price3=%s, workmode=%s, modifier=%s, "
                "modifytime=NOW() WHERE id=%s",
                (
                    rec["ownerid"], rec["cateid"], rec["catename"],
                    rec["price1"], rec["price2"], rec["price3"],
                    rec["workmode"], FIXED_USER, id,
                ),
            )
    return get_by_id(id)


def delete(id: int) -> bool:
    return wms_database.execute(f"DELETE FROM {TABLE} WHERE id = %s", (id,)) > 0


# ---------------------------------------------------------------------------
# Excel 导入 / 导出
# ---------------------------------------------------------------------------
def _read_excel(content: bytes) -> List[Dict[str, Any]]:
    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        raise ValueError("Excel 文件为空，缺少表头")
    col_index = {}
    for i, name in enumerate(header):
        if name is not None:
            col_index[str(name).strip().lower()] = i
    missing = [c for c in REQUIRED_COLUMNS if c not in col_index]
    if missing:
        raise ValueError("Excel 缺少必要列：" + ", ".join(missing))
    records = []
    for row in rows_iter:
        def cell(name):
            idx = col_index.get(name)
            return row[idx] if idx is not None and idx < len(row) else None
        records.append({
            "ownerid": cell("ownerid"),
            "cateid": cell("cateid"),
            "catename": cell("catename"),
            "price1": cell("price1"),
            "price2": cell("price2"),
            "price3": cell("price3"),
            "workmode": cell("workmode"),
        })
    wb.close()
    return records


def _sanitize(records: List[Dict[str, Any]]):
    clean = []
    warnings = []
    skipped = 0
    for i, rec in enumerate(records, start=2):
        ownerid = to_str(rec.get("ownerid"))
        if not ownerid:
            warnings.append("第%d行：ownerid 为空，已跳过" % i)
            skipped += 1
            continue
        cateid = to_str(rec.get("cateid"))
        if cateid and len(cateid) > 3:
            warnings.append("第%d行：cateid 超过3字符，已截断" % i)
            cateid = cateid[:3]
        workmode, warning = to_workmode(rec.get("workmode"))
        if warning:
            warnings.append("第%d行：%s" % (i, warning))
        clean.append({
            "ownerid": ownerid,
            "cateid": cateid,
            "catename": to_str(rec.get("catename")),
            "price1": to_decimal(rec.get("price1")),
            "price2": to_decimal(rec.get("price2")),
            "price3": to_decimal(rec.get("price3")),
            "workmode": workmode,
        })
    return clean, warnings, skipped


def import_excel(content: bytes) -> Dict[str, Any]:
    records = _read_excel(content)
    clean, warnings, skipped = _sanitize(records)
    inserted = 0
    updated = 0
    if clean:
        with wms_database.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT ownerid, cateid, workmode FROM {TABLE}"
                )
                existing_keys = {
                    (key_value(r["ownerid"]), key_value(r["cateid"]), key_value(r["workmode"]))
                    for r in cur.fetchall()
                }
                cur.execute(f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {TABLE}")
                next_id = cur.fetchone()["max_id"] + 1

                set_clause = ", ".join(f"{c}=%s" for c in UPDATE_COLUMNS)
                for rec in clean:
                    key = make_key(rec)
                    if rec["cateid"] is None:
                        where = "ownerid=%s AND cateid IS NULL AND workmode=%s"
                        key_params = (key_value(rec["ownerid"]), key_value(rec["workmode"]))
                    else:
                        where = "ownerid=%s AND cateid=%s AND workmode=%s"
                        key_params = (
                            key_value(rec["ownerid"]),
                            key_value(rec["cateid"]),
                            key_value(rec["workmode"]),
                        )
                    if key in existing_keys:
                        cur.execute(
                            f"UPDATE {TABLE} SET {set_clause} WHERE {where}",
                            tuple(rec[c] for c in UPDATE_COLUMNS) + key_params,
                        )
                        updated += 1
                    else:
                        cur.execute(
                            f"INSERT INTO {TABLE} "
                            "(id, ownerid, cateid, catename, price1, price2, price3, "
                            "dbsplitcode, creator, modifier, createTime, modifytime, workmode) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)",
                            (
                                next_id, rec["ownerid"], rec["cateid"], rec["catename"],
                                rec["price1"], rec["price2"], rec["price3"],
                                FIXED_DBSPLITCODE, FIXED_USER, FIXED_USER, rec["workmode"],
                            ),
                        )
                        next_id += 1
                        inserted += 1
                        existing_keys.add(key)
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "warnings": warnings[:50],
    }


def export_excel(filters: Dict[str, Any]) -> bytes:
    rows = query_all(filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "WorkPrice"
    ws.append(EXPORT_HEADERS)
    for row in rows:
        ws.append([
            row.get("id"),
            row.get("ownerid"),
            row.get("workmode"),
            row.get("cateid"),
            row.get("catename"),
            row.get("price1"),
            row.get("price2"),
            row.get("price3"),
            row.get("createTime"),
            row.get("modifytime"),
            row.get("creator"),
            row.get("modifier"),
        ])
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()
