"""
Excel 导入服务 - 按 container templete.xlsx 的 14 列解析
列顺序：SN / Brand / WH / Forwarder / BL / SHIP CO / SHIP NAME /
        CONTAINER NO. / POL / POD / Load date / ETA / period / Remark
period 为公式列，由系统计算；container_no 为空拒绝；重复跳过
备注(remark)含 shopfitting 的行默认为非商品(cargotype=1)
"""
import io
import logging
from datetime import datetime, date
from typing import Dict, List, Tuple, Any

from openpyxl import load_workbook

from app.core.database import fetch_one
from app.services import container_service
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)

HEADERS = [
    "sn", "brand", "wh", "forwarder", "bl", "ship_co", "ship_name",
    "container_no", "pol", "pod", "load_date", "eta", "period", "remark",
]


def _cell_value(cell) -> Any:
    v = cell.value
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip()
    return v


def _to_datetime(v) -> Any:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if isinstance(v, (int, float)):
        # Excel 序列号
        try:
            from openpyxl.utils.datetime import from_excel
            return from_excel(v)
        except Exception:
            return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_excel(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """解析 Excel 文件，返回 (有效行数据列表, 错误列表)"""
    errors = []
    try:
        wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    except Exception as e:
        return [], [f"无法读取 Excel 文件：{e}"]

    ws = wb.active
    rows = list(ws.iter_rows(values_only=False))
    if not rows:
        return [], ["Excel 文件为空"]

    # 校验表头（容错：按位置取，不强求表头文字一致）
    header_cells = [_cell_value(c) for c in rows[0]]
    data_rows = rows[1:]

    records = []
    for idx, row in enumerate(data_rows, start=2):
        cells = [_cell_value(c) for c in row]
        if not any(c is not None and c != "" for c in cells):
            continue
        rec: Dict[str, Any] = {}
        for i, key in enumerate(HEADERS):
            rec[key] = cells[i] if i < len(cells) else None

        # 必填校验
        container_no = rec.get("container_no")
        brand = rec.get("brand")
        if not container_no or not str(container_no).strip():
            errors.append(f"第{idx}行：集装箱号为空，已跳过")
            continue
        if not brand or not str(brand).strip():
            errors.append(f"第{idx}行：品牌为空，已跳过")
            continue

        # 类型转换
        rec["container_no"] = str(container_no).strip()
        rec["brand"] = str(brand).strip()
        for key in ("wh", "forwarder", "bl", "ship_co", "ship_name", "pol", "pod", "remark"):
            if rec.get(key) is not None:
                rec[key] = str(rec[key]).strip()
        try:
            rec["sn"] = int(rec["sn"]) if rec.get("sn") is not None else None
        except (ValueError, TypeError):
            rec["sn"] = None
        try:
            rec["cargotype"] = int(rec["cargotype"]) if rec.get("cargotype") not in (None, "") else None
        except (ValueError, TypeError):
            rec["cargotype"] = None
        # 备注含 shopfitting（忽略大小写）默认判为非商品(cargotype=1)，显式 cargotype 优先
        if rec.get("cargotype") is None and "shopfitting" in str(rec.get("remark") or "").lower():
            rec["cargotype"] = 1
        rec["load_date"] = _to_datetime(rec.get("load_date"))
        rec["eta"] = _to_datetime(rec.get("eta"))
        rec.pop("period", None)  # 由系统计算

        # 清理 None 值
        rec = {k: v for k, v in rec.items() if v is not None}
        records.append(rec)
    return records, errors


def import_records(records: List[Dict[str, Any]], creator: str) -> Dict[str, Any]:
    """执行导入：重复跳过"""
    imported = 0
    skipped = 0
    errors = []
    for rec in records:
        try:
            if container_service.exists_duplicate(
                rec["brand"], rec.get("bl"), rec["container_no"]
            ):
                skipped += 1
                continue
            container_service.create_container(rec, creator)
            imported += 1
        except Exception as e:
            errors.append(f"{rec.get('container_no')}: {e}")
            logger.exception("导入失败")
    return {
        "total_rows": len(records),
        "imported": imported,
        "skipped_duplicate": skipped,
        "skipped_invalid": len(errors),
        "errors": errors,
    }
