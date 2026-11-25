"""
BU 业务单元服务 - bidb.bu_def / bidb.bu_brand_rel

功能：
  1. BU 定义 CRUD + 分页查询 + Excel 导入导出
  2. BU-品牌关系查询 / 批量保存（品牌源实时读 mdmbasedb.brand）

导入策略：按 bu_code 判断，存在则更新、不存在则插入，不删除已有数据。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict, List, Optional

from openpyxl import Workbook, load_workbook

from app.core import bidb_database as db

T_BU = "bidb.bu_def"
T_REL = "bidb.bu_brand_rel"

DEFAULT_USER = "sys"
DEFAULT_ENTID = "X-BEAUTY"

# 定义表字段
BU_COLUMNS = ("bu_code", "bu_name", "bu_name_en", "status", "sort_no", "remark")
# 导入导出 Excel 表头（中英兼容由 _get 处理）
IMPORT_HEADERS = ["bu_code", "bu_name", "bu_name_en", "status", "sort_no", "remark"]
EXPORT_HEADERS = ["bu_code", "bu_name", "bu_name_en", "status", "sort_no", "remark",
                  "creator", "createtime", "modifier", "modifytime"]


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _s(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _row_out(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    out = dict(row)
    for k, v in list(out.items()):
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif hasattr(v, "strftime"):
            out[k] = v.strftime("%Y-%m-%d %H:%M:%S")
    return out


def _rows_out(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_row_out(r) for r in rows]


# ---------------------------------------------------------------------------
# 1. BU 定义 CRUD / 查询
# ---------------------------------------------------------------------------
def bu_list(keyword: str = None, status: Optional[int] = None,
            page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    clauses = []
    params: List[Any] = []
    if keyword:
        clauses.append("(bu_code LIKE %s OR bu_name LIKE %s OR bu_name_en LIKE %s)")
        kw = f"%{keyword.strip()}%"
        params.extend([kw, kw, kw])
    if status is not None:
        clauses.append("status=%s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    total = db.fetch_one(f"SELECT COUNT(*) AS n FROM {T_BU}{where}", tuple(params))["n"]
    rows = db.fetch_all(
        f"SELECT * FROM {T_BU}{where} ORDER BY sort_no, bu_code LIMIT %s OFFSET %s",
        tuple(params) + (page_size, (page - 1) * page_size),
    )
    items = _rows_out(rows)

    # 附带每个 BU 的品牌数
    if items:
        codes = [r["bu_code"] for r in items]
        ph = ",".join(["%s"] * len(codes))
        cnt_rows = db.fetch_all(
            f"SELECT bu_code, COUNT(*) AS n FROM {T_REL} WHERE bu_code IN ({ph}) GROUP BY bu_code",
            tuple(codes),
        )
        cnt_map = {r["bu_code"]: r["n"] for r in cnt_rows}
        for r in items:
            r["brand_count"] = cnt_map.get(r["bu_code"], 0)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def bu_options(enabled_only: bool = True) -> List[Dict[str, Any]]:
    where = " WHERE status=1" if enabled_only else ""
    rows = db.fetch_all(
        f"SELECT bu_code, bu_name, bu_name_en FROM {T_BU}{where} ORDER BY sort_no, bu_code"
    )
    return [{"bu_code": _s(r["bu_code"]),
             "label": _s(r["bu_name"]) or _s(r["bu_name_en"]) or _s(r["bu_code"])}
            for r in rows]


def bu_get(row_id: int) -> Optional[Dict[str, Any]]:
    return _row_out(db.fetch_one(f"SELECT * FROM {T_BU} WHERE id=%s", (row_id,)))


def bu_get_by_code(bu_code: str) -> Optional[Dict[str, Any]]:
    return _row_out(db.fetch_one(f"SELECT * FROM {T_BU} WHERE bu_code=%s", (bu_code,)))


def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    """规整 BU 字段：bu_code 必填，status/sort_no 数值化"""
    return {
        "bu_code": _s(data.get("bu_code")),
        "bu_name": _s(data.get("bu_name")) or None,
        "bu_name_en": _s(data.get("bu_name_en")) or None,
        "status": int(data.get("status") or 0) if str(data.get("status") or "0").strip() in ("0", "1") else 1,
        "sort_no": int(data.get("sort_no") or 0),
        "remark": _s(data.get("remark")) or None,
    }


def bu_create(data: Dict[str, Any], user: str = DEFAULT_USER) -> Dict[str, Any]:
    d = _normalize(data)
    if not d["bu_code"]:
        raise ValueError("BU代码不能为空")
    if bu_get_by_code(d["bu_code"]):
        raise ValueError(f"BU代码 {d['bu_code']} 已存在")
    new_id = db.execute(
        f"INSERT INTO {T_BU} (bu_code, bu_name, bu_name_en, status, sort_no, remark, "
        f"entid, dbsplitcode, creator, modifier) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (d["bu_code"], d["bu_name"], d["bu_name_en"], d["status"], d["sort_no"], d["remark"],
         DEFAULT_ENTID, "1", user, user),
    )
    return bu_get(new_id)


def bu_update(row_id: int, data: Dict[str, Any], user: str = DEFAULT_USER) -> Optional[Dict[str, Any]]:
    old = bu_get(row_id)
    if not old:
        return None
    merged = dict(old)
    merged.update({k: v for k, v in data.items() if k in BU_COLUMNS})
    d = _normalize(merged)
    if not d["bu_code"]:
        raise ValueError("BU代码不能为空")
    dup = bu_get_by_code(d["bu_code"])
    if dup and dup["id"] != row_id:
        raise ValueError(f"BU代码 {d['bu_code']} 已存在")
    # 若 bu_code 变更，同步更新关系表
    if d["bu_code"] != old["bu_code"]:
        db.execute(f"UPDATE {T_REL} SET bu_code=%s, modifier=%s WHERE bu_code=%s",
                   (d["bu_code"], user, old["bu_code"]))
    db.execute(
        f"UPDATE {T_BU} SET bu_code=%s, bu_name=%s, bu_name_en=%s, status=%s, "
        f"sort_no=%s, remark=%s, modifier=%s WHERE id=%s",
        (d["bu_code"], d["bu_name"], d["bu_name_en"], d["status"], d["sort_no"],
         d["remark"], user, row_id),
    )
    return bu_get(row_id)


def bu_delete(row_id: int) -> Dict[str, Any]:
    row = bu_get(row_id)
    if not row:
        return {"id": row_id, "deleted": 0, "rel_deleted": 0}
    with db.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {T_REL} WHERE bu_code=%s", (row["bu_code"],))
            rel_deleted = cur.rowcount
            cur.execute(f"DELETE FROM {T_BU} WHERE id=%s", (row_id,))
            deleted = cur.rowcount
    return {"id": row_id, "deleted": deleted, "rel_deleted": rel_deleted}


# ---------------------------------------------------------------------------
# 2. Excel 导入 / 导出
# ---------------------------------------------------------------------------
def _header_map(headers: List[str]) -> Dict[str, int]:
    """表头 -> 列序号，支持中英表头"""
    aliases = {
        "bu_code": ["bu_code", "bu代码", "bu编码", "代码", "code"],
        "bu_name": ["bu_name", "bu名称", "名称", "name"],
        "bu_name_en": ["bu_name_en", "bu英文名", "英文名", "name_en"],
        "status": ["status", "状态"],
        "sort_no": ["sort_no", "排序", "顺序"],
        "remark": ["remark", "备注"],
    }
    mapping = {}
    normalized = [_s(h).lower() for h in headers]
    for field, names in aliases.items():
        for i, h in enumerate(normalized):
            if h in [n.lower() for n in names]:
                mapping[field] = i
                break
    return mapping


def _cell_to_status(val: Any) -> int:
    s = _s(val).lower()
    if s in ("0", "停用", "禁用", "disable", "disabled", "inactive", "false"):
        return 0
    return 1


def _cell_to_int(val: Any) -> int:
    try:
        return int(float(_s(val)))
    except (ValueError, TypeError):
        return 0


def import_excel(content: bytes, user: str = DEFAULT_USER) -> Dict[str, Any]:
    wb = load_workbook(BytesIO(content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel 为空")
    hmap = _header_map([c for c in rows[0]])
    if "bu_code" not in hmap:
        raise ValueError("Excel 缺少 bu_code 列（或中文表头 BU代码/代码）")

    records = []
    for r in rows[1:]:
        if not r or all(c is None or _s(c) == "" for c in r):
            continue
        def get(field):
            idx = hmap.get(field)
            return r[idx] if idx is not None and idx < len(r) else None
        code = _s(get("bu_code"))
        if not code or code.lower() == "bu_code":
            continue
        records.append({
            "bu_code": code,
            "bu_name": _s(get("bu_name")) or None,
            "bu_name_en": _s(get("bu_name_en")) or None,
            "status": _cell_to_status(get("status")) if "status" in hmap else 1,
            "sort_no": _cell_to_int(get("sort_no")) if "sort_no" in hmap else 0,
            "remark": _s(get("remark")) or None,
        })

    inserted = updated = 0
    for rec in records:
        existing = bu_get_by_code(rec["bu_code"])
        if existing:
            merged = dict(existing)
            merged.update(rec)
            d = _normalize(merged)
            db.execute(
                f"UPDATE {T_BU} SET bu_name=%s, bu_name_en=%s, status=%s, sort_no=%s, "
                f"remark=%s, modifier=%s WHERE id=%s",
                (d["bu_name"], d["bu_name_en"], d["status"], d["sort_no"],
                 d["remark"], user, existing["id"]),
            )
            updated += 1
        else:
            bu_create(rec, user)
            inserted += 1
    return {"inserted": inserted, "updated": updated, "skipped": 0, "warnings": []}


def export_excel(keyword: str = None, status: Optional[int] = None) -> bytes:
    # 导出全部符合条件的数据（不走分页）
    clauses, params = [], []
    if keyword:
        clauses.append("(bu_code LIKE %s OR bu_name LIKE %s OR bu_name_en LIKE %s)")
        kw = f"%{keyword.strip()}%"
        params.extend([kw, kw, kw])
    if status is not None:
        clauses.append("status=%s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = db.fetch_all(f"SELECT * FROM {T_BU}{where} ORDER BY sort_no, bu_code", tuple(params))

    wb = Workbook()
    ws = wb.active
    ws.title = "BU"
    ws.append(["BU代码", "BU名称", "BU英文名", "状态", "排序", "备注",
               "创建人", "创建时间", "修改人", "修改时间"])
    for r in _rows_out(rows):
        ws.append([
            r.get("bu_code"), r.get("bu_name"), r.get("bu_name_en"),
            "启用" if r.get("status") == 1 else "停用", r.get("sort_no"), r.get("remark"),
            r.get("creator"), r.get("createtime"), r.get("modifier"), r.get("modifytime"),
        ])
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


# ---------------------------------------------------------------------------
# 3. BU-品牌关系
# ---------------------------------------------------------------------------
def brand_options() -> List[Dict[str, Any]]:
    """品牌下拉：实时读 mdmbasedb.brand（3 位 dbsplitcode=1），供关系设定"""
    rows = db.fetch_all(
        "SELECT brandid, brandname, note FROM mdmbasedb.brand "
        "WHERE dbsplitcode=1 ORDER BY brandid"
    )
    out = []
    for r in rows:
        name = _s(r.get("brandname"))
        if not name:
            continue
        out.append({
            "brand_name": name,
            "brandid": _s(r.get("brandid")) or None,
            "note": _s(r.get("note")) or None,
        })
    return out


def bu_brand_list(bu_code: str = None, brand_name: str = None) -> List[Dict[str, Any]]:
    clauses, params = [], []
    if bu_code:
        clauses.append("bu_code=%s")
        params.append(bu_code)
    if brand_name:
        clauses.append("brand_name=%s")
        params.append(brand_name)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = db.fetch_all(
        f"SELECT * FROM {T_REL}{where} ORDER BY bu_code, is_primary DESC, sort_no, brand_name",
        tuple(params),
    )
    return _rows_out(rows)


def bu_brand_save(payload: Dict[str, Any], user: str = DEFAULT_USER) -> Dict[str, Any]:
    """按 BU 批量保存品牌关系（全量替换该 BU 的关系），含主BU唯一校验"""
    bu_code = _s(payload.get("bu_code"))
    if not bu_code:
        raise ValueError("bu_code 不能为空")
    items = payload.get("items") or []
    primary_count = sum(1 for i in items if int(i.get("is_primary") or 0) == 1)
    if primary_count > 1:
        raise ValueError("一个 BU 内最多只能标记一个主品牌")

    # 主BU语义：每个品牌全局只有一个主BU。
    # 本 BU 设为 is_primary=1 的品牌，需先清除其它 BU 下的主标记，保证唯一。
    primary_names = [_s(i.get("brand_name")) for i in items if int(i.get("is_primary") or 0) == 1]
    with db.transaction() as conn:
        with conn.cursor() as cur:
            for name in primary_names:
                if name:
                    cur.execute(
                        f"UPDATE {T_REL} SET is_primary=0, modifier=%s "
                        f"WHERE brand_name=%s AND bu_code<>%s AND is_primary=1",
                        (user, name, bu_code),
                    )
            cur.execute(f"DELETE FROM {T_REL} WHERE bu_code=%s", (bu_code,))
            for idx, i in enumerate(items):
                name = _s(i.get("brand_name"))
                if not name:
                    continue
                cur.execute(
                    f"INSERT INTO {T_REL} "
                    "(bu_code, brand_name, brandid, brand_note, is_primary, sort_no, remark, "
                    "entid, dbsplitcode, creator, modifier) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (bu_code, name, _s(i.get("brandid")) or None, _s(i.get("brand_note")) or None,
                     1 if int(i.get("is_primary") or 0) == 1 else 0,
                     int(i.get("sort_no") or idx), _s(i.get("remark")) or None,
                     DEFAULT_ENTID, "1", user, user),
                )
    return {"bu_code": bu_code, "count": len(items)}


def bu_brand_delete(row_id: int) -> Dict[str, Any]:
    affected = db.execute(f"DELETE FROM {T_REL} WHERE id=%s", (row_id,))
    return {"id": row_id, "deleted": affected}
