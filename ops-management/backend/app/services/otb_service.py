"""
OTB 采买与商品补货 - 核心业务服务

表均在 bidb 库，通过 bidb.表名 全限定访问（复用现有连接池）。
包含：
  1. 11 张表的 CRUD
  2. OTB 主公式与 12 个月拆解计算引擎（纯函数）
  3. 商品补货建议计算引擎
  4. FY2027 Excel 底稿导入
"""
from __future__ import annotations

import math
import re
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook

from app.core import bidb_database as db

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
def T(name: str) -> str:
    """bidb 库表全限定名"""
    return f"bidb.{name}"


T_HEADER = T("otb_header")
T_MONTHLY = T("otb_monthly")
T_PARAM = T("otb_param_config")
T_MIX = T("sales_mix_config")
T_CATEGORY = T("category_summary")
T_BRAND = T("brand_summary")
T_BRAND_MIX = T("brand_monthly_mix")
T_ITEM = T("item_plan")
T_WEEKLY = T("item_weekly_sales")
T_STOCK = T("item_stock_snapshot")
T_REPLEN = T("replenishment_suggestion")
# 品牌-品类 / BU-品牌 关系表
T_BRAND_CAT = T("brand_category_rel")
T_BU_BRAND = T("bu_brand_rel")
T_BU_DEF = T("bu_def")

DEFAULT_USER = "sys"
DEFAULT_ENTID = "X-BEAUTY"

# 财年 Apr->Mar 对应的月份标签（OTB 看板期间使用）
FY_MONTHS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
# 自然月标签：month_seq 1-12 -> Jan-Dec（品牌月度拆解使用）
CALENDAR_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# FY2027 默认 Sales Mix: 6,6,9,8,8,8,9,9,9,9,9,10 (%)
DEFAULT_SALES_MIX = [0.06, 0.06, 0.09, 0.08, 0.08, 0.08, 0.09, 0.09, 0.09, 0.09, 0.09, 0.10]


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def D(val: Any, default: str = "0") -> Decimal:
    """安全转 Decimal"""
    if val is None or val == "":
        return Decimal(default)
    if isinstance(val, float) and math.isnan(val):
        return Decimal(default)
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def q2(val: Decimal) -> Decimal:
    """保留 2 位小数（四舍五入）"""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def q4(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def f2(val) -> Optional[float]:
    return float(q2(D(val))) if val is not None else None


def num(val) -> Optional[float]:
    """通用数值转 float"""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def fmt_dt(val) -> Optional[str]:
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val) if val else None


def row_out(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """序列化数据库行：Decimal/日期转可 JSON 化类型"""
    if row is None:
        return None
    out = dict(row)
    for k, v in list(out.items()):
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime,)):
            out[k] = fmt_dt(v)
        elif hasattr(v, "strftime") and "time" in type(v).__name__.lower():
            out[k] = fmt_dt(v)
    return out


def rows_out(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row_out(r) for r in rows]


def new_batch_id() -> str:
    return "OTB" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6].upper()


def audit_fields(user: str = DEFAULT_USER) -> Dict[str, Any]:
    return {"creator": user, "modifier": user}


# ---------------------------------------------------------------------------
# 1. OTB 主参数表
# ---------------------------------------------------------------------------
HEADER_FIELDS = [
    "fiscal_year", "bu_code", "opening_stock_cost", "planned_sales_cost",
    "planned_sales_total_retail", "planned_markdown_cost", "target_closing_stock_cost",
    "good_in_transit_cost", "otb_cost", "stock_cover_months", "gp_pct", "cogs_rate",
    "cost_rate", "calc_batch_id", "entid", "dbsplitcode", "creator", "modifier",
]


def header_list(fiscal_year: str = None) -> List[Dict[str, Any]]:
    if fiscal_year:
        rows = db.fetch_all(f"SELECT * FROM {T_HEADER} WHERE fiscal_year=%s ORDER BY id", (fiscal_year,))
    else:
        rows = db.fetch_all(f"SELECT * FROM {T_HEADER} ORDER BY id")
    return rows_out(rows)


def header_get(row_id: int) -> Optional[Dict[str, Any]]:
    return row_out(db.fetch_one(f"SELECT * FROM {T_HEADER} WHERE id=%s", (row_id,)))


def header_upsert(payload: Dict[str, Any], user: str = DEFAULT_USER) -> Dict[str, Any]:
    """新增或更新主参数（按 id 判断）"""
    data = {k: payload.get(k) for k in HEADER_FIELDS}
    data["creator"] = payload.get("creator") or user
    data["modifier"] = user
    data.setdefault("entid", DEFAULT_ENTID)
    row_id = payload.get("id")
    if row_id:
        sets = ", ".join(f"{k}=%s" for k in HEADER_FIELDS)
        db.execute(f"UPDATE {T_HEADER} SET {sets} WHERE id=%s", tuple(data[k] for k in HEADER_FIELDS) + (row_id,))
        return header_get(int(row_id))
    cols = ", ".join(HEADER_FIELDS)
    placeholders = ", ".join(["%s"] * len(HEADER_FIELDS))
    new_id = db.execute(f"INSERT INTO {T_HEADER} ({cols}) VALUES ({placeholders})",
                        tuple(data[k] for k in HEADER_FIELDS))
    return header_get(new_id)


# ---------------------------------------------------------------------------
# 2. 参数配置 / Sales Mix 配置
# ---------------------------------------------------------------------------
def param_list(fiscal_year: str = None) -> List[Dict[str, Any]]:
    if fiscal_year:
        rows = db.fetch_all(
            f"SELECT * FROM {T_PARAM} WHERE fiscal_year=%s OR fiscal_year IS NULL ORDER BY config_key",
            (fiscal_year,),
        )
    else:
        rows = db.fetch_all(f"SELECT * FROM {T_PARAM} ORDER BY config_key")
    return rows_out(rows)


def param_set(key: str, value: str, fiscal_year: str = None, desc: str = None,
              user: str = DEFAULT_USER) -> Dict[str, Any]:
    existing = db.fetch_one(
        f"SELECT id FROM {T_PARAM} WHERE config_key=%s AND fiscal_year <=> %s",
        (key, fiscal_year),
    )
    if existing:
        db.execute(
            f"UPDATE {T_PARAM} SET config_value=%s, modifier=%s WHERE id=%s",
            (value, user, existing["id"]),
        )
    else:
        db.execute(
            f"INSERT INTO {T_PARAM} (config_key, config_value, config_desc, fiscal_year, creator, modifier) "
            f"VALUES (%s,%s,%s,%s,%s,%s)",
            (key, value, desc, fiscal_year, user, user),
        )
    return {"config_key": key, "config_value": value, "fiscal_year": fiscal_year}


def param_get(key: str, fiscal_year: str = None, default: str = None) -> Optional[str]:
    row = db.fetch_one(
        f"SELECT config_value FROM {T_PARAM} WHERE config_key=%s AND fiscal_year <=> %s",
        (key, fiscal_year),
    )
    if row:
        return row["config_value"]
    row = db.fetch_one(
        f"SELECT config_value FROM {T_PARAM} WHERE config_key=%s AND fiscal_year IS NULL", (key,)
    )
    return row["config_value"] if row else default


def mix_list(fiscal_year: str, version: str = "v1") -> List[Dict[str, Any]]:
    rows = db.fetch_all(
        f"SELECT * FROM {T_MIX} WHERE fiscal_year=%s AND version=%s ORDER BY month_seq",
        (fiscal_year, version),
    )
    return rows_out(rows)


def mix_save(fiscal_year: str, items: List[Dict[str, Any]], version: str = "v1",
             user: str = DEFAULT_USER) -> Dict[str, Any]:
    """整体保存 12 个月 Sales Mix，先删后插（同版本幂等）"""
    total = sum(D(i.get("mix_pct")) for i in items)
    if abs(float(total) - 1.0) > 0.005 and len(items) == 12:
        raise ValueError(f"Sales Mix 合计必须为 100%，当前为 {float(total) * 100:.2f}%")
    with db.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {T_MIX} WHERE fiscal_year=%s AND version=%s", (fiscal_year, version))
            for i in sorted(items, key=lambda x: int(x.get("month_seq", 0))):
                cur.execute(
                    f"INSERT INTO {T_MIX} (fiscal_year, month_seq, mix_pct, version, creator, modifier) "
                    f"VALUES (%s,%s,%s,%s,%s,%s)",
                    (fiscal_year, int(i["month_seq"]), float(D(i.get("mix_pct"))), version, user, user),
                )
    return {"fiscal_year": fiscal_year, "version": version, "count": len(items)}


# ---------------------------------------------------------------------------
# 3. 计算引擎（纯函数）
# ---------------------------------------------------------------------------
def compute_otb(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    OTB 主公式（纯函数，不落库）
    otb_cost = planned_sales_cost + planned_markdown_cost + target_closing_stock_cost
             - (opening_stock_cost + good_in_transit_cost)
    """
    psc = D(params.get("planned_sales_cost"))
    markdown = D(params.get("planned_markdown_cost"))
    cover = D(params.get("stock_cover_months"))
    opening = D(params.get("opening_stock_cost"))
    in_transit = D(params.get("good_in_transit_cost"))
    gp = D(params.get("gp_pct"), "0.65")
    cogs_rate = D(params.get("cogs_rate"), "0.35")
    cost_rate = D(params.get("cost_rate"), "0.3240")

    if gp == 0:
        gp = Decimal("0.65")
    if cogs_rate == 0:
        cogs_rate = Decimal("1") - gp
    target_closing = q2(psc / Decimal(12) * cover)
    otb_cost = q2(psc + markdown + target_closing - (opening + in_transit))

    return {
        "planned_sales_cost": float(psc),
        "planned_markdown_cost": float(markdown),
        "planned_sales_total_retail": float(D(params.get("planned_sales_total_retail"))),
        "target_closing_stock_cost": float(target_closing),
        "opening_stock_cost": float(opening),
        "good_in_transit_cost": float(in_transit),
        "otb_cost": float(otb_cost),
        "stock_cover_months": float(cover),
        "gp_pct": float(gp),
        "cogs_rate": float(cogs_rate),
        "cost_rate": float(cost_rate),
    }


def compute_monthly(params: Dict[str, Any], mix: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    12 个月拆解（纯函数）
    retail = planned_sales_total_retail * mix
    cogs = retail * cogs_rate
    intake = otb_cost * mix * q4_factor
    closing = opening - cogs + intake；下月 opening = 本月 closing
    """
    otb_cost = D(params.get("otb_cost"))
    retail_total = D(params.get("planned_sales_total_retail"))
    cogs_rate = D(params.get("cogs_rate"), "0.35")
    gp = D(params.get("gp_pct"), "0.65")
    if cogs_rate == 0:
        cogs_rate = Decimal("1") - gp
    # Q4 旺季系数：原始底稿中仅用于额外 3 个月（次年 Apr/May/Jun）的追加拆解，
    # 本 12 个月明细按纯 Sales Mix 分摊，故默认系数为 1（合计=计划总额）。
    # 如业务需要对 12 个月内某几个月加权，可显式传入 q4_retail_factor/q4_intake_factor。
    q4_retail = D(params.get("q4_retail_factor"), "1")
    q4_intake = D(params.get("q4_intake_factor"), "1")
    opening = D(params.get("opening_stock_cost"))

    if not mix or len(mix) != 12:
        mix = [{"month_seq": i + 1, "mix_pct": str(m)} for i, m in enumerate(DEFAULT_SALES_MIX)]
    mix_map = {int(m["month_seq"]): D(m["mix_pct"]) for m in mix}

    rows: List[Dict[str, Any]] = []
    cur_opening = opening
    for seq in range(1, 13):
        pct = mix_map.get(seq, Decimal("0"))
        # 财年 Apr->Mar：月序 10/11/12 = Jan/Feb/Mar 为 Q4 旺季
        in_q4 = seq >= 10
        rf = q4_retail if in_q4 else Decimal("1")
        inf = q4_intake if in_q4 else Decimal("1")
        retail = q2(retail_total * pct * rf)
        cogs = q2(retail * cogs_rate)
        intake = q2(otb_cost * pct * inf)
        closing = q2(cur_opening - cogs + intake)
        rows.append({
            "month_seq": seq,
            "period_label": FY_MONTHS[seq - 1],  # Apr, May ... Mar（财年自然标签）
            "sales_mix_pct": float(pct),
            "retail_q4_factor": float(rf),
            "intake_q4_factor": float(inf),
            "opening_stock": float(cur_opening),
            "retail_sales": float(retail),
            "cogs": float(cogs),
            "gp_pct": float(gp),
            "intake_value_cost": float(intake),
            "closing_stock": float(closing),
        })
        cur_opening = closing

    sum_intake = q2(sum(D(r["intake_value_cost"]) for r in rows))
    sum_cogs = q2(sum(D(r["cogs"]) for r in rows))
    # 校验一（自洽）：Σ Intake 是否等于按 mix × Q4系数 展开后的理论合计
    # 说明：启用 Q4 旺季系数(1.2x)后，Σ Intake 会高于基础 OTB Cost，属正常业务口径
    #       （与原始底稿一致：S1=103,719,381 vs OTB=103,666,667）
    theoretical_intake = q2(sum(
        otb_cost * mix_map.get(seq, Decimal("0")) *
        (q4_intake if seq >= 10 else Decimal("1"))
        for seq in range(1, 13)
    ))
    return {
        "monthly": rows,
        "summary": {
            "sum_intake": float(sum_intake),
            "sum_cogs": float(sum_cogs),
            "opening_first": float(D(rows[0]["opening_stock"])),
            "closing_last": float(rows[-1]["closing_stock"]),
            "base_otb_cost": float(otb_cost),
            "q4_factor_applied": float(q4_intake) != 1.0,
            "check_budget": abs(float(sum_intake - theoretical_intake)) < 1000,
            "check_funds": abs(float((sum_intake - sum_cogs) - (D(rows[-1]["closing_stock"]) - D(rows[0]["opening_stock"])))) < 1000,
        },
    }


def compute_replenishment(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    商品补货公式（纯函数）
    total_stock = 六地库存之和
    ros = W1..W52 平均
    spot_week_cover = total_stock / ros
    propose = ROUND(ros * (forecasted - spot) - in_transit)
    """
    stock_fields = ["uae_wh", "uae_stores", "qtr_wh", "qtr_stores", "bah_wh", "bah_stores"]
    total_stock = sum(int(D(item.get(f))) for f in stock_fields)
    ros = D(item.get("ros_wk_ytd"))
    in_transit = int(D(item.get("stocks_in_transit")))
    forecasted = D(item.get("forecasted_wk_cover"), "20")
    spot = q2(total_stock / ros) if ros > 0 else None
    if ros > 0 and spot is not None:
        propose = int((ros * (forecasted - spot) - in_transit).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    else:
        propose = None
    remarks = ("Ok to Order" if propose > 0 else "Not to Order") if propose is not None else "N/A"
    return {
        "total_stock": total_stock,
        "ros_wk_ytd": float(ros),
        "spot_week_cover": float(spot) if spot is not None else None,
        "propose_the_qty": propose,
        "order_remarks": remarks,
    }


def calculate_and_save(header_id: int, fiscal_year: str, user: str = DEFAULT_USER) -> Dict[str, Any]:
    """触发测算：读主参数 -> 计算 -> 落 otb_header/otb_monthly，返回校验结果"""
    header = header_get(header_id)
    if not header:
        raise ValueError("OTB 主参数不存在")
    mix_rows = mix_list(fiscal_year)
    mix = mix_rows if mix_rows else None
    otb = compute_otb(header)
    monthly = compute_monthly(otb, mix)

    batch = new_batch_id()
    with db.transaction() as conn:
        with conn.cursor() as cur:
            # 更新主表计算结果与批次
            cur.execute(
                f"UPDATE {T_HEADER} SET otb_cost=%s, target_closing_stock_cost=%s, "
                f"gp_pct=%s, cogs_rate=%s, cost_rate=%s, calc_batch_id=%s, modifier=%s WHERE id=%s",
                (otb["otb_cost"], otb["target_closing_stock_cost"], otb["gp_pct"],
                 otb["cogs_rate"], otb["cost_rate"], batch, user, header_id),
            )
            # 先删旧明细（按 header + 公司级 brand_id IS NULL）
            cur.execute(f"DELETE FROM {T_MONTHLY} WHERE otb_header_id=%s AND brand_id IS NULL", (header_id,))
            for r in monthly["monthly"]:
                period = f"{fiscal_year.replace('FY', '')}-{int(r['month_seq']) + 3:02d}"
                # 月序 1 -> 04, ..., 12 -> 15? 用财年 Apr 起：seq1=Apr(04) ... seq9=Dec(12) seq10=Jan(01)...
                month_num = ((3 + int(r["month_seq"]) - 1) % 12) + 1
                period = f"{fiscal_year.replace('FY', '')}-{month_num:02d}"
                cur.execute(
                    f"INSERT INTO {T_MONTHLY} "
                    f"(otb_header_id, brand_id, fiscal_year, month_seq, period, sales_mix_pct, "
                    f"retail_sales, cogs, gp_pct, intake_value_cost, opening_stock, closing_stock, "
                    f"forward_month_cover, retail_q4_factor, intake_q4_factor, amount_basis, calc_batch_id, creator, modifier) "
                    f"VALUES (%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,'COST',%s,%s,%s)",
                    (header_id, fiscal_year, r["month_seq"], period, r["sales_mix_pct"],
                     r["retail_sales"], r["cogs"], r["gp_pct"], r["intake_value_cost"],
                     r["opening_stock"], r["closing_stock"], r["retail_q4_factor"],
                     r["intake_q4_factor"], batch, user, user),
                )
    return {
        "header_id": header_id,
        "calc_batch_id": batch,
        "otb": otb,
        "summary": monthly["summary"],
        "monthly": monthly["monthly"],
    }


MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month_label(seq: int, fiscal_year: str) -> str:
    """月序 -> 展示标签，如 month_seq=1, FY2027 -> Jan-27（与用户 Excel 底稿一致）"""
    yy = fiscal_year.replace("FY", "")[-2:] if fiscal_year else "27"
    return f"{MONTH_LABELS[int(seq) - 1]}-{yy}" if 1 <= int(seq) <= 12 else str(seq)


def monthly_list(header_id: int, fiscal_year: str = "FY2027") -> List[Dict[str, Any]]:
    rows = db.fetch_all(
        f"SELECT * FROM {T_MONTHLY} WHERE otb_header_id=%s ORDER BY month_seq", (header_id,)
    )
    out = rows_out(rows)
    # 补充展示用月份标签（表内仅存 period；标签按用户 Excel 口径 Jan-27..Dec-27 生成）
    for r in out:
        r["month_label"] = month_label(r.get("month_seq") or 1, fiscal_year)
    return out


def monthly_pivot(header_id: int, fiscal_year: str = "FY2027") -> Dict[str, Any]:
    """
    生成 Excel 风格的转置明细：月份作横向列（Jan-27..Dec-27 + FY2027 合计），
    指标作行（Opening/Retail/COGS/GP%/Intake/Closing/Forward Cover/Sales Mix%/Newness/Replenishment/Total/Check）。
    """
    rows = monthly_list(header_id, fiscal_year)
    if not rows:
        return {"columns": [], "rows": []}

    columns = [month_label(r.get("month_seq") or 1, fiscal_year) for r in rows] + ["FY2027"]

    def series(field: str, pct: bool = False):
        vals = []
        for r in rows:
            v = r.get(field)
            vals.append(f"{float(v) * 100:.0f}%" if (pct and v is not None) else v)
        return vals

    # 合计列：金额类求和，比率/库存类取末值或固定值
    def with_total(vals, total_mode="sum"):
        if total_mode == "sum":
            t = sum(D(v) for v in vals if v is not None)
            return vals + [float(q2(t))]
        if total_mode == "last":
            return vals + [vals[-1] if vals else None]
        return vals + [None]

    intake_vals = [r.get("intake_value_cost") for r in rows]
    # Newness 30% / Replenishment 70%（Excel 2027 OTB sheet Row14-17）
    newness = [float(q2(D(v) * Decimal("0.30"))) for v in intake_vals]
    replen = [float(q2(D(v) * Decimal("0.70"))) for v in intake_vals]
    total_row = [float(q2(D(n) + D(p))) for n, p in zip(newness, replen)]
    check_row = ["TRUE" if abs(D(total_row[i]) - D(intake_vals[i])) < 1 else "FALSE"
                 for i in range(len(rows))]

    data_rows = [
        {"label": "Opening Stock", "values": with_total(series("opening_stock"), "last"), "emphasis": False},
        {"label": "Retail Sales", "values": with_total(series("retail_sales"), "sum"), "emphasis": True},
        {"label": "COGS", "values": with_total(series("cogs"), "sum"), "emphasis": False},
        {"label": "GP%", "values": [f"{float(r.get('gp_pct') or 0) * 100:.0f}%" for r in rows] + [f"{float(rows[-1].get('gp_pct') or 0) * 100:.0f}%"], "emphasis": False},
        {"label": "Intake Value Cost", "values": with_total(intake_vals, "sum"), "emphasis": True},
        {"label": "Closing Stock", "values": with_total(series("closing_stock"), "last"), "emphasis": False},
        {"label": "Forward Month Cover", "values": with_total(series("forward_month_cover"), "last"), "emphasis": False},
        {"label": "Sales Mix %", "values": series("sales_mix_pct", pct=True) + ["100%"], "emphasis": False},
        {"label": "Newness", "values": with_total(newness, "sum"), "emphasis": False},
        {"label": "Replenishment", "values": with_total(replen, "sum"), "emphasis": False},
        {"label": "Total", "values": with_total(total_row, "sum"), "emphasis": False},
        {"label": "Check", "values": check_row + ["TRUE"], "emphasis": False},
    ]
    return {"columns": columns, "rows": data_rows}


# ---------------------------------------------------------------------------
# 4. 品类汇总表
# ---------------------------------------------------------------------------
def category_list(fiscal_year: str = None, bu_code: str = None,
                  brand_name: str = None) -> List[Dict[str, Any]]:
    clauses, params = [], []
    if fiscal_year:
        clauses.append("fiscal_year=%s")
        params.append(fiscal_year)
    if bu_code:
        clauses.append("bu_code=%s")
        params.append(bu_code)
    if brand_name:
        clauses.append("brand_name=%s")
        params.append(brand_name)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = db.fetch_all(
        f"SELECT * FROM {T_CATEGORY}{where} "
        f"ORDER BY bu_code, brand_name, sale_mix_pct DESC, category_code", tuple(params)
    )
    return rows_out(rows)


def planned_sales_total(fiscal_year: str) -> Decimal:
    """读取 OTB 主参数的 Planned Sales Total（全年总零售），用于品类 Sales Retail 自动计算"""
    headers = header_list(fiscal_year)
    h = headers[0] if headers else {}
    return D(h.get("planned_sales_total_retail")) or D("320000000")


def planned_sales_cost(fiscal_year: str) -> Decimal:
    """读取 OTB 主参数的 Planned Sales Cost（全年计划销售成本），用于品类 FC Buy Plan 自动计算"""
    headers = header_list(fiscal_year)
    h = headers[0] if headers else {}
    return D(h.get("planned_sales_cost")) or D("112000000")


def otb_cost(fiscal_year: str) -> Decimal:
    """读取 OTB 主参数的 OTB Cost（采买预算），用于品牌 FC Buy Plan 自动计算"""
    headers = header_list(fiscal_year)
    h = headers[0] if headers else {}
    return D(h.get("otb_cost")) or D("103666666.67")


def monthly_mix_curve(fiscal_year: str) -> List[Decimal]:
    """获取12个月采买曲线占比：全局 sales_mix_config（v1）优先，缺失则用默认曲线。
    返回长度12的 Decimal 列表，合计约为1。"""
    rows = mix_list(fiscal_year, "v1")
    if len(rows) == 12:
        by_seq = {int(r["month_seq"]): D(r["mix_pct"]) for r in rows}
        return [by_seq.get(i, D(0)) for i in range(1, 13)]
    return [D(x) for x in DEFAULT_SALES_MIX]


def brand_monthly_curve(brand_id: int, fiscal_year: str,
                        fallback: List[Decimal] = None) -> List[Decimal]:
    """获取某品牌的12个月采买曲线：品牌级 brand_monthly_mix（v1）优先，否则回退全局曲线。"""
    rows = db.fetch_all(
        f"SELECT month_seq, mix_pct FROM {T_BRAND_MIX} "
        f"WHERE brand_id=%s AND fiscal_year=%s AND version=%s ORDER BY month_seq",
        (brand_id, fiscal_year, "v1"),
    )
    if len(rows) == 12:
        by_seq = {int(r["month_seq"]): D(r["mix_pct"]) for r in rows}
        return [by_seq.get(i, D(0)) for i in range(1, 13)]
    return fallback if fallback is not None else monthly_mix_curve(fiscal_year)


def split_monthly_buy(total: Decimal, curve: List[Decimal]) -> List[float]:
    """把全年采买金额按12个月曲线拆解，返回12个金额；差额归入最后一个月确保闭合。"""
    amounts = [q2(total * curve[i]) for i in range(12)]
    amounts[-1] = q2(total - sum(amounts[:-1]))
    return [float(a) for a in amounts]


def category_upsert(payload: Dict[str, Any], user: str = DEFAULT_USER) -> Dict[str, Any]:
    fy = payload.get("fiscal_year")
    code = payload.get("category_code")
    if not fy or not code:
        raise ValueError("fiscal_year 与 category_code 不能为空")
    brand = str(payload.get("brand_name") or "").strip()
    mix = D(payload.get("sale_mix_pct"))
    cost_rate = D(payload.get("cost_rate")) or D("0.3240")
    # Sales Retail / FC Buy Plan 不可手工输入：自动按 Planned Sales Total / Planned Sales Cost × Sale Mix%
    sales_retail = q2(planned_sales_total(fy) * mix)
    fc_buy_plan = q2(planned_sales_cost(fy) * mix)
    values = (
        str(payload.get("bu_code") or "").strip() or None,
        str(payload.get("brandid") or "").strip() or None,
        brand or None,
        payload.get("category_name"), float(sales_retail),
        float(mix), float(fc_buy_plan),
        float(cost_rate), user,
    )
    existing = db.fetch_one(
        f"SELECT id FROM {T_CATEGORY} WHERE fiscal_year=%s AND brand_name<=>%s AND category_code=%s",
        (fy, brand or None, code),
    )
    if existing:
        db.execute(
            f"UPDATE {T_CATEGORY} SET bu_code=%s, brandid=%s, brand_name=%s, category_name=%s, "
            f"sales_retail=%s, sale_mix_pct=%s, fc_buy_plan=%s, cost_rate=%s, modifier=%s WHERE id=%s",
            values + (existing["id"],),
        )
        row_id = existing["id"]
    else:
        row_id = db.execute(
            f"INSERT INTO {T_CATEGORY} (fiscal_year, bu_code, brandid, brand_name, category_code, "
            f"category_name, sales_retail, sale_mix_pct, fc_buy_plan, cost_rate, creator, modifier) "
            f"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (fy,) + values[:8] + (user, user),
        )
    return row_out(db.fetch_one(f"SELECT * FROM {T_CATEGORY} WHERE id=%s", (row_id,)))


def category_check(fiscal_year: str, bu_code: str = None) -> Dict[str, Any]:
    """闭合校验：各品类 Sales Retail 汇总必须 = OTB 主参数 Planned Sales Total。
    Sales Retail = Planned Sales Total × Sale Mix%，等价于 Sale Mix% 合计 = 100%（容差 ±0.5%）。
    """
    rows = category_list(fiscal_year, bu_code=bu_code)
    target = planned_sales_total(fiscal_year)
    cost_target = planned_sales_cost(fiscal_year)
    retail_total = sum((D(r.get("sales_retail")) for r in rows), D(0))
    buy_total = sum((D(r.get("fc_buy_plan")) for r in rows), D(0))
    mix_total = sum((D(r.get("sale_mix_pct")) for r in rows), D(0))
    diff = q2(retail_total - target)
    cost_diff = q2(buy_total - cost_target)
    # 容差：总额 ±1 或占比 ±0.5%
    valid = (abs(float(diff)) <= 1.0 and abs(float(cost_diff)) <= 1.0
             and abs(float(mix_total) - 1.0) <= 0.005)
    return {
        "fiscal_year": fiscal_year,
        "bu_code": bu_code,
        "count": len(rows),
        "sale_mix_total": float(mix_total),
        "sales_retail_total": float(q2(retail_total)),
        "planned_sales_total": float(q2(target)),
        "diff": float(diff),
        "fc_buy_plan_total": float(q2(buy_total)),
        "planned_sales_cost": float(q2(cost_target)),
        "cost_diff": float(cost_diff),
        "valid": valid,
        "check_sales_retail": abs(float(diff)) <= 1.0,
        "check_fc_buy_plan": abs(float(cost_diff)) <= 1.0,
    }


def category_generate_by_bu(fiscal_year: str, bu_code: str,
                            user: str = DEFAULT_USER) -> Dict[str, Any]:
    """按 BU 自动生成品牌×品类明细行：BU→该BU下品牌→品牌关联品类。
    已存在的组合跳过，不覆盖已设定的 Sale Mix。
    """
    bu = db.fetch_one(f"SELECT bu_code, bu_name FROM {T_BU_DEF} WHERE bu_code=%s", (bu_code,))
    if not bu:
        raise ValueError(f"BU {bu_code} 不存在")
    # BU 下品牌（含 brandid）
    brands = db.fetch_all(
        f"SELECT r.brand_name, r.brandid, d.brandname, d.note "
        f"FROM {T_BU_BRAND} r "
        f"LEFT JOIN mdmbasedb.brand d ON r.brandid=d.brandid "
        f"WHERE r.bu_code=%s ORDER BY r.brand_name", (bu_code,),
    )
    if not brands:
        return {"bu_code": bu_code, "brands": 0, "created": 0, "skipped": 0,
                "message": "该 BU 下暂无品牌，请先在「BU-品牌关系」设定"}
    brand_names = list(dict.fromkeys(
        str(b["brand_name"]).strip() for b in brands if b.get("brand_name")
    ))
    if not brand_names:
        return {"bu_code": bu_code, "brands": 0, "created": 0, "skipped": 0}
    ph = ",".join(["%s"] * len(brand_names))
    rels = db.fetch_all(
        f"SELECT brand_name, brandid, categoryid, categoryname, category_note, is_primary, sort_no "
        f"FROM {T_BRAND_CAT} WHERE brand_name IN ({ph}) "
        f"ORDER BY brand_name, is_primary DESC, sort_no, categoryid", tuple(brand_names),
    )
    # 已存在的组合
    existing = db.fetch_all(
        f"SELECT brand_name, category_code FROM {T_CATEGORY} WHERE fiscal_year=%s",
        (fiscal_year,),
    )
    exist_keys = {(str(r.get("brand_name") or "").upper(), str(r.get("category_code") or ""))
                  for r in existing}

    id_names = _category_id_names()
    created = skipped = 0
    brandid_map = {str(b["brand_name"]).strip().upper(): str(b.get("brandid") or "").strip() or None
                   for b in brands}
    with db.transaction() as conn:
        with conn.cursor() as cur:
            for r in rels:
                bname = str(r.get("brand_name") or "").strip()
                cid = str(r.get("categoryid") or "").strip()
                cname = str(r.get("categoryname") or "").strip() or id_names.get(cid, "")
                # 品类代码用主数据 3 位数字 categoryid（如 502），品类名称用英文名
                key = (bname.upper(), cid)
                if key in exist_keys:
                    skipped += 1
                    continue
                bid = str(r.get("brandid") or "").strip() or brandid_map.get(bname.upper()) or None
                cur.execute(
                    f"INSERT INTO {T_CATEGORY} (fiscal_year, bu_code, brandid, brand_name, "
                    f"category_code, category_name, sales_retail, sale_mix_pct, fc_buy_plan, "
                    f"cost_rate, creator, modifier) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (fiscal_year, bu_code, bid, bname, cid, cname,
                     0, 0, 0, 0.3240, user, user),
                )
                exist_keys.add(key)
                created += 1
    return {"bu_code": bu_code, "brands": len(brand_names),
            "created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# 5. 品牌汇总表 / 品牌月度曲线
# ---------------------------------------------------------------------------
BRAND_FIELDS = [
    "fiscal_year", "category_code", "brand_name", "sub_brand_id", "item_count",
    "total_sales_value", "sale_mix_pct", "total_sales_qty_ytd", "total_sales_cost_ytd",
    "gp_pct", "business_soh_cost", "spot_month_cover", "fc_sales_plan", "fc_buy_plan",
    "actual_buy_ytd", "monthly_mix_version", "calc_batch_id", "entid", "dbsplitcode",
    "creator", "modifier",
]


def brand_list(fiscal_year: str = None, keyword: str = None, page: int = 1,
               page_size: int = 50, bu_code: str = None) -> Dict[str, Any]:
    where, params = db.build_where(
        {"fiscal_year": fiscal_year, "brand_name": keyword},
        exact_fields=("fiscal_year",), like_fields=("brand_name",),
    )
    # 可选按 BU 过滤（通过 bu_brand_rel 关联，品牌名匹配）
    if bu_code:
        where += (f" AND EXISTS (SELECT 1 FROM {T_BU_BRAND} r "
                  f"WHERE r.bu_code=%s AND r.brand_name={T_BRAND}.brand_name)")
        params = params + (bu_code,)
    total = db.fetch_one(f"SELECT COUNT(*) AS n FROM {T_BRAND}{where}", params)["n"]
    rows = db.fetch_all(
        f"SELECT * FROM {T_BRAND}{where} ORDER BY sale_mix_pct DESC LIMIT %s OFFSET %s",
        params + (page_size, (page - 1) * page_size),
    )
    items = rows_out(rows)
    # FC Sales Plan = OTB主参数 Planned Sales Total × Sale Mix%
    # FC Buy Plan   = OTB主参数 OTB Cost × Sale Mix%
    fy = fiscal_year or "FY2027"
    target_retail = planned_sales_total(fy)
    target_cost = otb_cost(fy)
    global_curve = monthly_mix_curve(fy)
    # 一次性批量读取该财年所有品牌月度曲线，避免逐行查询(N+1)
    curve_rows = db.fetch_all(
        f"SELECT brand_id, month_seq, mix_pct FROM {T_BRAND_MIX} "
        f"WHERE fiscal_year=%s AND version=%s ORDER BY brand_id, month_seq",
        (fy, "v1"),
    )
    curves_by_brand: Dict[int, Dict[int, Decimal]] = {}
    for cr in curve_rows:
        curves_by_brand.setdefault(int(cr["brand_id"]), {})[int(cr["month_seq"])] = D(cr["mix_pct"])
    for r in items:
        mix = D(r.get("sale_mix_pct"))
        fc_buy = q2(target_cost * mix)
        r["fc_sales_plan"] = float(q2(target_retail * mix))
        r["fc_buy_plan"] = float(fc_buy)
        # 1-12月采买值：按品牌月度曲线（品牌级优先，否则全局）自动拆解
        seq_map = curves_by_brand.get(int(r["id"]))
        if seq_map and len(seq_map) == 12:
            curve = [seq_map.get(i, D(0)) for i in range(1, 13)]
        else:
            curve = global_curve
        r["monthly_mix"] = [float(q4(c)) for c in curve]
        r["monthly_buy"] = split_monthly_buy(fc_buy, curve)
    # 带出系统链路：所属BU / 主品类（来自前置设定关系）
    if items and fiscal_year:
        rel_map = brand_relations(fiscal_year)
        for r in items:
            rel = rel_map.get(str(r.get("brand_name") or "").strip().upper(), {})
            r["bus"] = rel.get("bus", [])
            r["primary_category"] = rel.get("primary_category")
            r["bu_label"] = "、".join(
                (b["bu_name"] or b["bu_code"]) for b in rel.get("bus", [])
            ) or None
            pc = rel.get("primary_category")
            r["primary_category_name"] = pc.get("categoryname") if pc else None
    # 全量汇总（不受分页影响）：从所有匹配行计算 Sale Mix / FC 计划 / 12月采买合计
    all_rows = db.fetch_all(
        f"SELECT id, sale_mix_pct FROM {T_BRAND}{where}", params
    )
    mix_sum = D(0)
    monthly_sum = [D(0)] * 12
    for ar in all_rows:
        m = D(ar.get("sale_mix_pct"))
        mix_sum += m
        fc_buy = q2(target_cost * m)
        seq_map = curves_by_brand.get(int(ar["id"]))
        curve = ([seq_map.get(i, D(0)) for i in range(1, 13)]
                 if seq_map and len(seq_map) == 12 else global_curve)
        month_vals = split_monthly_buy(fc_buy, curve)
        for idx in range(12):
            monthly_sum[idx] += D(str(month_vals[idx]))
    fc_buy_total = q2(target_cost * mix_sum)
    # 汇总的12月合计强制闭合到 FC Buy Plan 合计（消除逐行拆分的累积舍入差）
    month_totals = [q2(v) for v in monthly_sum]
    month_totals[-1] = q2(fc_buy_total - sum(month_totals[:-1]))
    summary = {
        "count": len(all_rows),
        "sale_mix_total": float(q4(mix_sum)),
        "fc_sales_plan_total": float(q2(target_retail * mix_sum)),
        "fc_buy_plan_total": float(fc_buy_total),
        "monthly_buy_total": [float(v) for v in month_totals],
    }

    return {
        "total": total, "page": page, "page_size": page_size, "items": items,
        "planned_sales_total": float(target_retail),
        "otb_cost": float(target_cost),
        "summary": summary,
    }


def brand_get(brand_id: int) -> Optional[Dict[str, Any]]:
    return row_out(db.fetch_one(f"SELECT * FROM {T_BRAND} WHERE id=%s", (brand_id,)))


def brand_upsert(payload: Dict[str, Any], user: str = DEFAULT_USER) -> Dict[str, Any]:
    data = {k: payload.get(k) for k in BRAND_FIELDS}
    data["creator"] = payload.get("creator") or user
    data["modifier"] = user
    data.setdefault("entid", DEFAULT_ENTID)
    # FC Sales Plan / FC Buy Plan 不可手工输入：按 OTB主参数 × Sale Mix% 自动计算
    fy = data.get("fiscal_year") or "FY2027"
    mix = D(data.get("sale_mix_pct"))
    data["fc_sales_plan"] = float(q2(planned_sales_total(fy) * mix))
    data["fc_buy_plan"] = float(q2(otb_cost(fy) * mix))
    row_id = payload.get("id")
    if row_id:
        sets = ", ".join(f"{k}=%s" for k in BRAND_FIELDS)
        db.execute(f"UPDATE {T_BRAND} SET {sets} WHERE id=%s",
                   tuple(data[k] for k in BRAND_FIELDS) + (row_id,))
        return brand_get(int(row_id))
    cols = ", ".join(BRAND_FIELDS)
    ph = ", ".join(["%s"] * len(BRAND_FIELDS))
    new_id = db.execute(f"INSERT INTO {T_BRAND} ({cols}) VALUES ({ph})",
                        tuple(data[k] for k in BRAND_FIELDS))
    return brand_get(new_id)


def brand_batch_sale_mix(fiscal_year: str, items: List[Dict[str, Any]],
                         user: str = DEFAULT_USER) -> Dict[str, Any]:
    """批量保存品牌 Sale Mix%（行内编辑）。FC Sales Plan / FC Buy Plan 按公式自动重算。
    items: [{id, sale_mix_pct}, ...]，sale_mix_pct 为 0-1 小数。
    """
    target_retail = planned_sales_total(fiscal_year)
    target_cost = otb_cost(fiscal_year)
    updated = 0
    with db.transaction() as conn:
        with conn.cursor() as cur:
            for i in items:
                row_id = i.get("id")
                if not row_id:
                    continue
                mix = D(i.get("sale_mix_pct"))
                cur.execute(
                    f"UPDATE {T_BRAND} SET sale_mix_pct=%s, fc_sales_plan=%s, "
                    f"fc_buy_plan=%s, modifier=%s WHERE id=%s",
                    (float(q4(mix)), float(q2(target_retail * mix)),
                     float(q2(target_cost * mix)), user, row_id),
                )
                updated += 1
    return {"fiscal_year": fiscal_year, "updated": updated}


def brand_monthly_split(brand_id: int, fiscal_year: str, user: str = DEFAULT_USER) -> Dict[str, Any]:
    """品牌 FC Buy Plan 按品牌级月度曲线拆 12 个月（Cost 口径）"""
    brand = brand_get(brand_id)
    if not brand:
        raise ValueError("品牌不存在")
    mix_rows = db.fetch_all(
        f"SELECT * FROM {T_BRAND_MIX} WHERE brand_id=%s AND fiscal_year=%s ORDER BY month_seq",
        (brand_id, fiscal_year),
    )
    if not mix_rows:
        mix = DEFAULT_SALES_MIX
        mix_rows = [{"month_seq": i + 1, "mix_pct": str(m)} for i, m in enumerate(mix)]
    # FC Buy Plan = OTB主参数 OTB Cost × Sale Mix%（与品牌列表口径一致）
    buy_plan = q2(otb_cost(fiscal_year) * D(brand.get("sale_mix_pct")))
    amounts = []
    for m in mix_rows:
        seq = int(m["month_seq"])
        pct = D(m["mix_pct"])
        amounts.append({
            "month_seq": seq,
            "month_label": CALENDAR_MONTHS[seq - 1] if 1 <= seq <= 12 else "",
            "mix_pct": float(pct),
            "buy_amount": float(q2(buy_plan * pct)),
            "amount_basis": "COST",
        })
    total = q2(sum(D(a["buy_amount"]) for a in amounts))
    return {
        "brand_id": brand_id,
        "brand_name": brand.get("brand_name"),
        "fc_buy_plan": float(buy_plan),
        "monthly": amounts,
        "total": float(total),
        "diff": float(q2(total - buy_plan)),
        "note": "该行为采买金额(Cost 口径)，非零售额",
    }


def brand_mix_list(brand_id: int, fiscal_year: str) -> List[Dict[str, Any]]:
    rows = db.fetch_all(
        f"SELECT * FROM {T_BRAND_MIX} WHERE brand_id=%s AND fiscal_year=%s ORDER BY month_seq",
        (brand_id, fiscal_year),
    )
    return rows_out(rows)


def brand_mix_save(brand_id: int, fiscal_year: str, items: List[Dict[str, Any]],
                   version: str = "v1", user: str = DEFAULT_USER) -> Dict[str, Any]:
    total = sum(D(i.get("mix_pct")) for i in items)
    if abs(float(total) - 1.0) > 0.005 and len(items) == 12:
        raise ValueError(f"品牌月度曲线合计必须为 100%，当前为 {float(total) * 100:.2f}%")
    with db.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {T_BRAND_MIX} WHERE brand_id=%s AND fiscal_year=%s AND version=%s",
                        (brand_id, fiscal_year, version))
            for i in sorted(items, key=lambda x: int(x.get("month_seq", 0))):
                cur.execute(
                    f"INSERT INTO {T_BRAND_MIX} (brand_id, fiscal_year, month_seq, mix_pct, source, version, creator, modifier) "
                    f"VALUES (%s,%s,%s,%s,'brand_override',%s,%s,%s)",
                    (brand_id, fiscal_year, int(i["month_seq"]), float(D(i.get("mix_pct"))), version, user, user),
                )
    # 更新品牌曲线版本
    db.execute(f"UPDATE {T_BRAND} SET monthly_mix_version=%s, modifier=%s WHERE id=%s",
               (version, user, brand_id))
    return {"brand_id": brand_id, "fiscal_year": fiscal_year, "version": version, "count": len(items)}


# ---------------------------------------------------------------------------
# 5c. 系统链路：BU → BU品牌 → 品牌品类，品牌 Sale Mix 按品类分摊
# ---------------------------------------------------------------------------
def _norm_category(name: Any) -> str:
    """品类名标准化：去掉空格/下划线/连接符/&/AND，统一大写，用于跨体系匹配
    Excel 用 MAKE_UP / BEAUTY_AND_CLEANING，主数据用 MAKE UP / BEAUTY & CLEANING。
    """
    s = str(name or "").upper().strip()
    for ch in (" ", "_", "-", "&", "/", ".", "'", "（", "）", "(", ")"):
        s = s.replace(ch, "")
    s = s.replace("AND", "")
    return s


def _category_id_names() -> Dict[str, str]:
    """categoryid(3位) -> categoryname，来自主数据，去重取首个"""
    rows = db.fetch_all(
        "SELECT categoryid, categoryname FROM mdmbasedb.category "
        "WHERE dbsplitcode='1' AND LENGTH(categoryid)=3 ORDER BY categoryid"
    )
    out: Dict[str, str] = {}
    for r in rows:
        cid = str(r.get("categoryid") or "").strip()
        if cid and cid not in out:
            out[cid] = str(r.get("categoryname") or "").strip()
    return out


def brand_relations(fiscal_year: str = "FY2027") -> Dict[str, Dict[str, Any]]:
    """一次返回所有品牌的关联映射，供品牌列表带出 BU / 主品类。
    key = brand_name(大写)，value = {bus:[...], primary_category:{...}, categories:[...]}
    """
    id_names = _category_id_names()

    # 品类 Sale Mix（按标准化 code 索引）
    cat_rows = db.fetch_all(
        f"SELECT category_code, category_name, sale_mix_pct FROM {T_CATEGORY} "
        f"WHERE fiscal_year=%s", (fiscal_year,),
    )
    cat_mix = {_norm_category(r.get("category_code")): D(r.get("sale_mix_pct"))
               for r in cat_rows if r.get("category_code")}

    # 品牌-品类关系（全局主数据，不按财年；is_primary 优先，sort_no 次之）
    rels = db.fetch_all(
        f"SELECT brand_name, categoryid, categoryname, category_note, is_primary, sort_no "
        f"FROM {T_BRAND_CAT} "
        f"ORDER BY brand_name, is_primary DESC, sort_no, categoryid",
    )
    brand_cat: Dict[str, Dict[str, Any]] = {}
    for r in rels:
        bn = str(r.get("brand_name") or "").strip()
        if not bn:
            continue
        key = bn.upper()
        cid = str(r.get("categoryid") or "").strip()
        cname = str(r.get("categoryname") or "").strip() or id_names.get(cid, "")
        entry = brand_cat.setdefault(key, {"primary": None, "categories": []})
        entry["categories"].append({
            "categoryid": cid, "categoryname": cname,
            "category_note": str(r.get("category_note") or "").strip(),
            "is_primary": int(r.get("is_primary") or 0),
            "sale_mix_pct": float(cat_mix.get(_norm_category(cname), D(0))),
        })
        if int(r.get("is_primary") or 0) == 1 and entry["primary"] is None:
            entry["primary"] = {"categoryid": cid, "categoryname": cname}

    # 如果没有主品类，按 sort_no 取第一个作为默认主品类
    for key, entry in brand_cat.items():
        if entry["primary"] is None and entry["categories"]:
            first = entry["categories"][0]
            entry["primary"] = {"categoryid": first["categoryid"], "categoryname": first["categoryname"]}

    # BU-品牌关系（含 BU 名称）
    bu_rows = db.fetch_all(
        f"SELECT r.brand_name, r.bu_code, r.is_primary, d.bu_name, d.bu_name_en "
        f"FROM {T_BU_BRAND} r LEFT JOIN {T_BU_DEF} d ON r.bu_code=d.bu_code "
        f"ORDER BY r.brand_name, r.is_primary DESC"
    )
    brand_bu: Dict[str, List[Dict[str, Any]]] = {}
    for r in bu_rows:
        bn = str(r.get("brand_name") or "").strip()
        if not bn:
            continue
        brand_bu.setdefault(bn.upper(), []).append({
            "bu_code": str(r.get("bu_code") or "").strip(),
            "bu_name": str(r.get("bu_name") or r.get("bu_name_en") or "").strip(),
            "is_primary": int(r.get("is_primary") or 0),
        })

    out: Dict[str, Dict[str, Any]] = {}
    for key in set(brand_cat) | set(brand_bu):
        out[key] = {
            "bus": brand_bu.get(key, []),
            "primary_category": brand_cat.get(key, {}).get("primary"),
            "categories": brand_cat.get(key, {}).get("categories", []),
        }
    return out


def _brand_mix_allocation(fiscal_year: str) -> Dict[str, Any]:
    """计算品牌 Sale Mix（不落库）。
    新口径：品类 Sale Mix 已是品牌×品类明细，品牌 Sale Mix = 该品牌各品类 Sale Mix 之和。
    用户约束：全部品类 Sale Mix 合计不超过 100%。
    """
    rows = db.fetch_all(
        f"SELECT brand_name, brandid, category_code, category_name, sale_mix_pct, bu_code "
        f"FROM {T_CATEGORY} WHERE fiscal_year=%s AND brand_name IS NOT NULL "
        f"ORDER BY brand_name, category_code", (fiscal_year,),
    )
    brand_mix: Dict[str, Decimal] = {}
    brand_meta: Dict[str, Dict[str, Any]] = {}
    cat_summary: Dict[str, Dict[str, Any]] = {}
    allocations: List[Dict[str, Any]] = []
    for r in rows:
        bn = str(r.get("brand_name") or "").strip()
        if not bn:
            continue
        key = bn.upper()
        mix = D(r.get("sale_mix_pct"))
        brand_mix[key] = brand_mix.get(key, D(0)) + mix
        brand_meta[key] = {"brand_name": bn, "brandid": str(r.get("brandid") or "").strip() or None}
        cc = str(r.get("category_code") or "").strip()
        cs = cat_summary.setdefault(cc, {
            "category_code": cc, "category_sale_mix_pct": D(0), "brand_count": 0,
        })
        cs["category_sale_mix_pct"] += mix
        cs["brand_count"] += 1
        allocations.append({
            "brand_name": bn,
            "brandid": brand_meta[key]["brandid"],
            "category_code": cc,
            "category_name": str(r.get("category_name") or "").strip(),
            "category_sale_mix_pct": float(q4(mix)),
            "sale_mix_pct": float(q4(mix)),  # 明细行即该品牌该品类 Sale Mix
            "bu_code": str(r.get("bu_code") or "").strip() or None,
        })

    # 品牌 Sale Mix 明细（按品牌汇总）
    brand_rows = []
    for key, mix in brand_mix.items():
        brand_rows.append({
            "brand_name": brand_meta[key]["brand_name"],
            "brandid": brand_meta[key]["brandid"],
            "sale_mix_pct": float(q4(mix)),
        })
    total = sum(brand_mix.values(), D(0))
    return {
        "fiscal_year": fiscal_year,
        "allocations": brand_rows,  # 品牌级明细（供品牌页回写用）
        "category_details": allocations,  # 品牌×品类明细
        "categories": [
            {
                "category_code": v["category_code"],
                "category_sale_mix_pct": float(q4(v["category_sale_mix_pct"])),
                "brand_count": v["brand_count"],
                "allocated_total_pct": float(q4(v["category_sale_mix_pct"])),
            }
            for v in cat_summary.values()
        ],
        "unmatched_brands": [],
        "total_allocated_pct": float(q4(total)),
        "over_limit": total > D("1.005"),  # 超过100%标记
    }


def brand_sale_mix_preview(fiscal_year: str = "FY2027") -> Dict[str, Any]:
    """按品类关系预览品牌 Sale Mix 分摊（不落库）"""
    return _brand_mix_allocation(fiscal_year)


def brand_sale_mix_recalc(fiscal_year: str = "FY2027",
                          user: str = DEFAULT_USER) -> Dict[str, Any]:
    """按品类 Sale Mix 明细汇总，回写品牌 Sale Mix 及 FC 计划。
    品牌 Sale Mix = 该品牌各品类 Sale Mix 之和；品类合计不得超过 100%。
    FC Sales Plan = SaleMix × 全年总零售；FC Buy Plan = SaleMix × OTB Cost。
    """
    result = _brand_mix_allocation(fiscal_year)
    if result["over_limit"]:
        raise ValueError(
            f"品类 Sale Mix 合计 {result['total_allocated_pct']*100:.2f}% 超过 100%，请先调整"
        )
    allocations = result["allocations"]

    headers = header_list(fiscal_year)
    h = headers[0] if headers else {}
    total_retail = D(h.get("planned_sales_total_retail")) or D("320000000")
    otb_cost = D(h.get("otb_cost")) or D("103666667")

    # 品牌名 -> brand_summary.id（该财年）
    brand_rows = db.fetch_all(
        f"SELECT id, UPPER(brand_name) AS bk FROM {T_BRAND} WHERE fiscal_year=%s", (fiscal_year,)
    )
    brand_ids = {str(r["bk"]): r["id"] for r in brand_rows}

    updated = 0
    with db.transaction() as conn:
        with conn.cursor() as cur:
            for a in allocations:
                bid = brand_ids.get(str(a["brand_name"]).upper())
                if not bid:
                    continue
                mix = D(a["sale_mix_pct"])
                fc_sales = q2(total_retail * mix)
                fc_buy = q2(otb_cost * mix)
                cur.execute(
                    f"UPDATE {T_BRAND} SET sale_mix_pct=%s, fc_sales_plan=%s, "
                    f"fc_buy_plan=%s, modifier=%s WHERE id=%s",
                    (a["sale_mix_pct"], float(fc_sales), float(fc_buy), user, bid),
                )
                updated += 1
    return {
        "fiscal_year": fiscal_year,
        "updated": updated,
        "total_allocated_pct": result["total_allocated_pct"],
        "total_retail": float(total_retail),
        "otb_cost": float(otb_cost),
        "categories": result["categories"],
    }


# ---------------------------------------------------------------------------
# 5a-bis. 按 BRANDCHILD 字典生成品牌汇总
#   数据源：glsdb.lookupitem (locale='zh-CN', lookupid='BRANDCHILD') 全部子品牌
#   Sale Mix 沿用现有 Excel 导入值（按品牌名匹配，匹配不到则为 0）
#   生成前需选择 BU + 财务年；生成时把品牌关联到所选 BU
# ---------------------------------------------------------------------------
def brandchild_options() -> List[Dict[str, Any]]:
    """BRANDCHILD 子品牌字典：Sub_Brand_ID / Sub_Brand_Name（全部，不分页）"""
    rows = db.fetch_all(
        "SELECT fieldvalue, lookup FROM glsdb.lookupitem "
        "WHERE locale=%s AND lookupid=%s ORDER BY fieldvalue",
        ('zh-CN', 'BRANDCHILD'),
    )
    out: List[Dict[str, Any]] = []
    seen = set()
    for r in rows:
        sid = str(r.get("fieldvalue") or "").strip()
        name = str(r.get("lookup") or "").strip()
        if not sid or not name:
            continue
        key = sid.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append({"sub_brand_id": sid, "sub_brand_name": name})
    return out


def _name_key(value: Any) -> str:
    """品牌名归一化：去所有空白 + 大写，用于 BRANDCHILD 与 Excel 品牌名匹配"""
    return re.sub(r"\s+", "", str(value or "")).upper()


def _brand_generate_rows(fiscal_year: str, bu_code: Optional[str]) -> Tuple[List[Dict[str, Any]], int, Decimal]:
    """构造 BRANDCHILD 全部子品牌的生成行，并从现有 Excel 导入值带出 Sale Mix。
    返回 (rows, matched_count, sale_mix_total)
    """
    children = brandchild_options()
    existing = db.fetch_all(
        f"SELECT id, brand_name, sub_brand_id, sale_mix_pct, fc_sales_plan, fc_buy_plan, "
        f"item_count, total_sales_value FROM {T_BRAND} WHERE fiscal_year=%s",
        (fiscal_year,),
    )
    exist_map = {_name_key(r["brand_name"]): r for r in existing}
    target_retail = planned_sales_total(fiscal_year)
    target_cost = otb_cost(fiscal_year)

    rows: List[Dict[str, Any]] = []
    matched = 0
    mix_total = D(0)
    for c in children:
        hit = exist_map.get(_name_key(c["sub_brand_name"]))
        mix = D(hit["sale_mix_pct"]) if hit else D(0)
        mix_total += mix
        if hit:
            matched += 1
        rows.append({
            "sub_brand_id": c["sub_brand_id"],
            "brand_name": c["sub_brand_name"],
            "sale_mix_pct": float(q4(mix)),
            "fc_sales_plan": float(q2(target_retail * mix)),
            "fc_buy_plan": float(q2(target_cost * mix)),
            "item_count": int(hit["item_count"] or 0) if hit else 0,
            "total_sales_value": float(D(hit["total_sales_value"])) if hit else 0.0,
            "matched": bool(hit),
            "existing_id": hit["id"] if hit else None,
            "bu_code": bu_code,
        })
    return rows, matched, mix_total


def brand_generate_preview(fiscal_year: str = "FY2027",
                           bu_code: Optional[str] = None) -> Dict[str, Any]:
    """预览按 BRANDCHILD 字典生成的品牌数据（不落库）"""
    rows, matched, mix_total = _brand_generate_rows(fiscal_year, bu_code)
    return {
        "fiscal_year": fiscal_year,
        "bu_code": bu_code,
        "total": len(rows),
        "matched": matched,
        "unmatched": len(rows) - matched,
        "sale_mix_total": float(q4(mix_total)),
        "over_limit": mix_total > D("1.005"),
        "rows": rows,
    }


def brand_generate(fiscal_year: str = "FY2027", bu_code: Optional[str] = None,
                   user: str = DEFAULT_USER) -> Dict[str, Any]:
    """按 BRANDCHILD 全部子品牌生成品牌汇总，并关联到所选 BU。
    已存在的品牌（该财年+品牌名）只补 sub_brand_id、保留 Excel 导入数值；
    不存在的品牌新建（数值为 0）。Sale Mix 合计超过 100% 时拒绝生成。
    """
    if not bu_code:
        raise ValueError("请先选择 BU")
    rows, matched, mix_total = _brand_generate_rows(fiscal_year, bu_code)
    if mix_total > D("1.005"):
        raise ValueError(
            f"现有品牌 Sale Mix 合计 {float(mix_total)*100:.2f}% 超过 100%，请先调整"
        )

    created = 0
    linked = 0
    with db.transaction() as conn:
        with conn.cursor() as cur:
            for r in rows:
                if r["existing_id"]:
                    cur.execute(
                        f"UPDATE {T_BRAND} SET sub_brand_id=COALESCE(sub_brand_id,%s), "
                        f"modifier=%s WHERE id=%s",
                        (r["sub_brand_id"], user, r["existing_id"]),
                    )
                else:
                    cur.execute(
                        f"INSERT INTO {T_BRAND} "
                        f"(fiscal_year, brand_name, sub_brand_id, creator, modifier, entid, dbsplitcode) "
                        f"VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (fiscal_year, r["brand_name"], r["sub_brand_id"],
                         user, user, DEFAULT_ENTID, "1"),
                    )
                    created += 1
                # 关联到所选 BU（已存在则忽略，不破坏既有主 BU 设定）
                cur.execute(
                    f"INSERT IGNORE INTO {T_BU_BRAND} "
                    f"(bu_code, brand_name, brandid, creator, modifier, entid, dbsplitcode) "
                    f"VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (bu_code, r["brand_name"], r["sub_brand_id"],
                     user, user, DEFAULT_ENTID, "1"),
                )
                linked += cur.rowcount
    return {
        "fiscal_year": fiscal_year,
        "bu_code": bu_code,
        "total": len(rows),
        "created": created,
        "reused": len(rows) - created,
        "matched_sale_mix": matched,
        "bu_linked": linked,
        "sale_mix_total": float(q4(mix_total)),
    }


# ---------------------------------------------------------------------------
# 5b. 品牌-品类关系（多对多 + 主品类）
#     品类实时直读 mdmbasedb.category，不落地快照表
# ---------------------------------------------------------------------------
def category_options() -> List[Dict[str, Any]]:
    """品类下拉：实时读 mdmbasedb.category 的 3 位业务品类（无需快照表）"""
    rows = db.fetch_all(
        "SELECT categoryid, categoryname, note FROM mdmbasedb.category "
        "WHERE dbsplitcode='1' AND LENGTH(categoryid)=3 ORDER BY categoryid"
    )
    out = []
    for r in rows:
        cid = str(r.get("categoryid") or "").strip()
        if not cid:
            continue
        cname = str(r.get("categoryname") or "").strip()
        note = str(r.get("note") or "").strip()
        out.append({
            "categoryid": cid,
            "categoryname": cname,
            "note": note,
            "label": f"{cname}（{note}）" if note else (cname or cid),
        })
    return out


def brand_options(fiscal_year: str = None, main_only: bool = True) -> List[Dict[str, Any]]:
    """品牌列表。
    默认 main_only=True：仅返回主数据 mdmbasedb.brand 的主品牌（品牌-品类关系设定用）。
    main_only=False：合并主数据与 OTB 品牌汇总（含 BRANDCHILD 子品牌），按品牌名去重。
    """
    merged: Dict[str, Dict[str, Any]] = {}

    # 1) 主数据品牌（带 brandid 与简称 note）
    try:
        mrows = db.fetch_all(
            "SELECT brandid, brandname, note FROM mdmbasedb.brand "
            "WHERE dbsplitcode=1 ORDER BY brandid"
        )
        for r in mrows:
            name = str(r.get("brandname") or "").strip()
            if not name:
                continue
            merged[name.upper()] = {
                "brand_name": name,
                "brandid": str(r.get("brandid") or "").strip() or None,
                "note": str(r.get("note") or "").strip() or None,
            }
    except Exception:
        pass  # 主数据不可用

    # 仅主品牌时，直接返回主数据结果，不混入 OTB 品牌汇总（BRANDCHILD 子品牌）
    if main_only:
        return sorted(merged.values(), key=lambda x: x["brand_name"].upper())

    # 2) OTB 品牌汇总（导入 Excel 后可能产生主数据之外的品牌）
    if fiscal_year:
        rows = db.fetch_all(
            f"SELECT DISTINCT brand_name FROM {T_BRAND} "
            f"WHERE fiscal_year=%s AND brand_name IS NOT NULL ORDER BY brand_name",
            (fiscal_year,),
        )
    else:
        rows = db.fetch_all(
            f"SELECT DISTINCT brand_name FROM {T_BRAND} "
            f"WHERE brand_name IS NOT NULL ORDER BY brand_name"
        )
    for r in rows:
        name = str(r.get("brand_name") or "").strip()
        if name and name.upper() not in merged:
            merged[name.upper()] = {"brand_name": name, "brandid": None, "note": None}

    return sorted(merged.values(), key=lambda x: x["brand_name"].upper())


def brand_category_list(brand_name: str = None) -> List[Dict[str, Any]]:
    """查询品牌-品类关系（全局，不按财年）；不传品牌时返回全部"""
    where = ""
    params: List[Any] = []
    if brand_name:
        where = " WHERE brand_name=%s"
        params.append(brand_name)
    rows = db.fetch_all(
        f"SELECT * FROM {T_BRAND_CAT}{where} "
        f"ORDER BY brand_name, is_primary DESC, sort_no, categoryid",
        tuple(params),
    )
    return rows_out(rows)


def brand_category_save(payload: Dict[str, Any], user: str = DEFAULT_USER) -> Dict[str, Any]:
    """按品牌批量保存品类关系（全量替换该品牌的关系），含主品类唯一校验。全局，不按财年。"""
    brand = payload.get("brand_name")
    if not brand:
        raise ValueError("brand_name 不能为空")
    items = payload.get("items") or []
    primary_count = sum(1 for i in items if int(i.get("is_primary") or 0) == 1)
    if primary_count > 1:
        raise ValueError("一个品牌最多只能设置一个主品类")
    brandid = payload.get("brandid") or None
    with db.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {T_BRAND_CAT} WHERE brand_name=%s",
                (brand,),
            )
            for idx, i in enumerate(items):
                cid = str(i.get("categoryid") or "").strip()
                if not cid:
                    continue
                cur.execute(
                    f"INSERT INTO {T_BRAND_CAT} "
                    "(brand_name, brandid, categoryid, categoryname, category_note, "
                    "is_primary, sort_no, remark, entid, dbsplitcode, creator, modifier) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (brand, brandid, cid,
                     i.get("categoryname") or None, i.get("category_note") or None,
                     1 if int(i.get("is_primary") or 0) == 1 else 0,
                     int(i.get("sort_no") or idx), i.get("remark") or None,
                     DEFAULT_ENTID, "1", user, user),
                )
    return {"brand_name": brand, "count": len(items)}


def brand_category_delete(row_id: int) -> Dict[str, Any]:
    affected = db.execute(f"DELETE FROM {T_BRAND_CAT} WHERE id=%s", (row_id,))
    return {"id": row_id, "deleted": affected}


# ---------------------------------------------------------------------------
# 6. 商品表 / 周销量 / 库存 / 补货建议
# ---------------------------------------------------------------------------
ITEM_FIELDS = [
    "brand_id", "item_code", "product_name", "sale_mix_pct", "fc_sales_plan_retail",
    "fc_buy_plan_cost", "uae_wh", "uae_stores", "qtr_wh", "qtr_stores", "bah_wh",
    "bah_stores", "total_stock", "ros_wk_ytd", "spot_week_cover", "stocks_in_transit",
    "propose_the_qty", "forecasted_wk_cover", "order_remarks", "calc_batch_id",
    "entid", "dbsplitcode", "creator", "modifier",
]


def item_list(brand_id: int = None, keyword: str = None, page: int = 1,
              page_size: int = 100) -> Dict[str, Any]:
    where, params = db.build_where(
        {"brand_id": brand_id, "item_code": keyword},
        exact_fields=("brand_id",), like_fields=("item_code", "product_name"),
    )
    total = db.fetch_one(f"SELECT COUNT(*) AS n FROM {T_ITEM}{where}", params)["n"]
    rows = db.fetch_all(
        f"SELECT * FROM {T_ITEM}{where} ORDER BY fc_sales_plan_retail DESC LIMIT %s OFFSET %s",
        params + (page_size, (page - 1) * page_size),
    )
    return {"total": total, "page": page, "page_size": page_size, "items": rows_out(rows)}


def item_get(item_code: str) -> Optional[Dict[str, Any]]:
    return row_out(db.fetch_one(f"SELECT * FROM {T_ITEM} WHERE item_code=%s", (item_code,)))


def item_upsert(payload: Dict[str, Any], user: str = DEFAULT_USER) -> Dict[str, Any]:
    data = {k: payload.get(k) for k in ITEM_FIELDS}
    data["creator"] = payload.get("creator") or user
    data["modifier"] = user
    data.setdefault("entid", DEFAULT_ENTID)
    code = data["item_code"]
    if not code:
        raise ValueError("item_code 不能为空")
    existing = db.fetch_one(f"SELECT id FROM {T_ITEM} WHERE item_code=%s", (code,))
    if existing:
        sets = ", ".join(f"{k}=%s" for k in ITEM_FIELDS)
        db.execute(f"UPDATE {T_ITEM} SET {sets} WHERE id=%s",
                   tuple(data[k] for k in ITEM_FIELDS) + (existing["id"],))
    else:
        cols = ", ".join(ITEM_FIELDS)
        ph = ", ".join(["%s"] * len(ITEM_FIELDS))
        db.execute(f"INSERT INTO {T_ITEM} ({cols}) VALUES ({ph})",
                   tuple(data[k] for k in ITEM_FIELDS))
    return item_get(code)


def item_weekly(item_code: str) -> List[Dict[str, Any]]:
    rows = db.fetch_all(f"SELECT * FROM {T_WEEKLY} WHERE item_code=%s ORDER BY week_seq", (item_code,))
    return rows_out(rows)


def item_recalc(item_code: str, user: str = DEFAULT_USER) -> Dict[str, Any]:
    """重算单商品补货建议：ROS 用 W1-W52 平均，公式链计算后落库"""
    item = item_get(item_code)
    if not item:
        raise ValueError("商品不存在")
    weekly = item_weekly(item_code)
    if weekly:
        qty_sum = sum(D(w.get("sales_qty")) for w in weekly)
        ros = q2(qty_sum / len(weekly))
    else:
        ros = D(item.get("ros_wk_ytd"))
    enriched = dict(item)
    enriched["ros_wk_ytd"] = float(ros)
    result = compute_replenishment(enriched)
    db.execute(
        f"UPDATE {T_ITEM} SET total_stock=%s, ros_wk_ytd=%s, spot_week_cover=%s, "
        f"propose_the_qty=%s, order_remarks=%s, modifier=%s WHERE item_code=%s",
        (result["total_stock"], result["ros_wk_ytd"], result["spot_week_cover"],
         result["propose_the_qty"], result["order_remarks"], user, item_code),
    )
    return {"item_code": item_code, **result}


def replenishment_list(status: str = None, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    where, params = db.build_where({"status": status}, exact_fields=("status",))
    total = db.fetch_one(f"SELECT COUNT(*) AS n FROM {T_REPLEN}{where}", params)["n"]
    rows = db.fetch_all(
        f"SELECT * FROM {T_REPLEN}{where} ORDER BY id DESC LIMIT %s OFFSET %s",
        params + (page_size, (page - 1) * page_size),
    )
    return {"total": total, "page": page, "page_size": page_size, "items": rows_out(rows)}


def replenishment_generate(fiscal_year: str = None, user: str = DEFAULT_USER) -> Dict[str, Any]:
    """基于 item_plan 现有计算结果生成补货建议清单"""
    items = db.fetch_all(f"SELECT * FROM {T_ITEM} WHERE propose_the_qty IS NOT NULL ORDER BY brand_id, item_code")
    batch = new_batch_id()
    created = 0
    with db.transaction() as conn:
        with conn.cursor() as cur:
            for it in items:
                propose = it.get("propose_the_qty")
                cur.execute(
                    f"INSERT INTO {T_REPLEN} "
                    f"(sku_id, brand_id, otb_header_id, suggest_date, available_stock, "
                    f"current_cover_months, suggest_qty, reason, status, item_code, "
                    f"propose_the_qty, order_remarks, calc_batch_id, creator, modifier) "
                    f"VALUES (%s,%s,NULL,CURDATE(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (it.get("id"), it.get("brand_id"), it.get("total_stock") or 0,
                     it.get("spot_week_cover"), propose, "ROS*(Forecasted-Spot)-InTransit",
                     "待确认", it.get("item_code"), propose, it.get("order_remarks"),
                     batch, user, user),
                )
                created += 1
    return {"calc_batch_id": batch, "created": created}


def replenishment_decision(row_id: int, status: str, user: str = DEFAULT_USER) -> Optional[Dict[str, Any]]:
    if status not in ("已确认", "已采纳", "已否决"):
        raise ValueError("status 必须为 已确认/已采纳/已否决")
    db.execute(f"UPDATE {T_REPLEN} SET status=%s, modifier=%s WHERE id=%s", (status, user, row_id))
    return row_out(db.fetch_one(f"SELECT * FROM {T_REPLEN} WHERE id=%s", (row_id,)))


# ---------------------------------------------------------------------------
# 7. FY2027 Excel 底稿导入（X-Beauty_OTB.xlsx 5 个 sheet）
# ---------------------------------------------------------------------------
def _num(cell) -> Optional[float]:
    v = cell
    if v is None or v == "":
        return None
    if isinstance(v, str):
        v = v.strip().replace(",", "").replace("%", "")
        if not v:
            return None
        try:
            f = float(v)
            return f / 100 if "%" in str(cell) else f
        except ValueError:
            return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return None
        return float(v)
    return None


def import_excel(content: bytes, fiscal_year: str = "FY2027",
                 user: str = DEFAULT_USER) -> Dict[str, Any]:
    """
    导入 X-Beauty_OTB.xlsx：
      OTB_X-Beauty -> otb_header；Category -> category_summary；
      Brand Summary -> brand_summary；Brand Item -> item_plan + item_weekly_sales + item_stock_snapshot
    返回各表导入条数。
    """
    wb = load_workbook(BytesIO(content), data_only=True)
    result: Dict[str, Any] = {"fiscal_year": fiscal_year, "sheets": list(wb.sheetnames)}

    def cell(ws, row, col):
        return ws.cell(row=row, column=col).value

    # --- OTB_X-Beauty ---
    if "OTB_X-Beauty" in wb.sheetnames:
        ws = wb["OTB_X-Beauty"]
        # Row1 表头；Row2 数据
        payload = {
            "fiscal_year": fiscal_year,
            "bu_code": str(cell(ws, 2, 1) or "X-Beauty").replace("X-Beaury", "X-Beauty"),
            "opening_stock_cost": _num(cell(ws, 2, 3)) or 0,
            "planned_sales_cost": _num(cell(ws, 2, 4)) or 0,
            "planned_markdown_cost": _num(cell(ws, 2, 5)) or 0,
            "target_closing_stock_cost": _num(cell(ws, 2, 6)) or 0,
            "good_in_transit_cost": _num(cell(ws, 2, 7)) or 0,
            "otb_cost": _num(cell(ws, 2, 8)) or 0,
            "stock_cover_months": int(_num(cell(ws, 2, 9)) or 5),
            "planned_sales_total_retail": _num(cell(ws, 3, 4)) or 0,
            "gp_pct": _num(cell(ws, 4, 4)) or 0.65,
        }
        otb = compute_otb(payload)
        payload.update(otb)
        hdr = header_upsert(payload, user)
        result["otb_header"] = 1
        result["otb_cost"] = otb["otb_cost"]

    # --- Category ---
    if "Category" in wb.sheetnames:
        ws = wb["Category"]
        count = 0
        for r in range(2, ws.max_row + 1):
            cname = cell(ws, r, 1)
            if not cname or str(cname).strip() in ("合计", "Total"):
                continue
            code = str(cname).strip().replace("&", "AND")
            category_upsert({
                "fiscal_year": fiscal_year,
                "category_code": code,
                "category_name": str(cname).strip(),
                "sales_retail": _num(cell(ws, r, 2)) or 0,
                "sale_mix_pct": (_num(cell(ws, r, 3)) or 0),
                "fc_buy_plan": _num(cell(ws, r, 4)) or 0,
            }, user)
            count += 1
        result["category_summary"] = count

    # --- Brand Summary ---
    if "Brand Summary" in wb.sheetnames:
        ws = wb["Brand Summary"]
        count = 0
        for r in range(3, ws.max_row + 1):
            name = cell(ws, r, 1)
            if not name or str(name).strip().lower() in ("nan", "none", "total", "合计"):
                continue
            name = str(name).strip()
            total_sales = _num(cell(ws, r, 3)) or 0
            if total_sales <= 0:
                continue
            brand_upsert({
                "fiscal_year": fiscal_year,
                "brand_name": name,
                "item_count": int(_num(cell(ws, r, 2)) or 0),
                "total_sales_value": total_sales,
                "sale_mix_pct": _num(cell(ws, r, 4)) or 0,
                "total_sales_qty_ytd": int(_num(cell(ws, r, 5)) or 0),
                "total_sales_cost_ytd": _num(cell(ws, r, 6)) or 0,
                "gp_pct": _num(cell(ws, r, 7)) or 0,
                "business_soh_cost": _num(cell(ws, r, 8)) or 0,
                "spot_month_cover": _num(cell(ws, r, 9)),
                "fc_sales_plan": _num(cell(ws, r, 10)) or total_sales,
                "fc_buy_plan": _num(cell(ws, r, 11)) or 0,
                "actual_buy_ytd": _num(cell(ws, r, 12)) or 0,
            }, user)
            count += 1
        result["brand_summary"] = count

    # --- Brand Item ---
    if "Brand Item" in wb.sheetnames:
        ws = wb["Brand Item"]
        # 先建立品牌名 -> brand_id 映射（从 product_name 前缀推断）
        brand_rows = db.fetch_all(f"SELECT id, brand_name FROM {T_BRAND} WHERE fiscal_year=%s", (fiscal_year,))
        brand_map = {b["brand_name"].upper(): b["id"] for b in brand_rows}

        item_count = 0
        weekly_count = 0
        stock_count = 0
        for r in range(3, ws.max_row + 1):
            code = cell(ws, r, 1)
            pname = cell(ws, r, 2)
            if not code or not pname:
                continue
            code = str(code).strip()
            pname = str(pname).strip()
            # 品牌归属：product_name 形如 "XB-MEDICUBE xxx"
            brand_id = None
            upper = pname.upper()
            for bname, bid in brand_map.items():
                if bname in upper:
                    brand_id = bid
                    break
            mix = _num(cell(ws, r, 3)) or 0
            fc_sales = _num(cell(ws, r, 4)) or 0
            fc_buy = _num(cell(ws, r, 5)) or 0
            stock_vals = [_num(cell(ws, r, c)) or 0 for c in range(6, 12)]
            total_stock = int(sum(stock_vals))
            ros = _num(cell(ws, r, 13))
            spot = _num(cell(ws, r, 14))
            in_transit = int(_num(cell(ws, r, 15)) or 0)
            forecasted = _num(cell(ws, r, 17)) or 20

            item_upsert({
                "brand_id": brand_id, "item_code": code, "product_name": pname,
                "sale_mix_pct": mix, "fc_sales_plan_retail": fc_sales,
                "fc_buy_plan_cost": fc_buy,
                "uae_wh": int(stock_vals[0]), "uae_stores": int(stock_vals[1]),
                "qtr_wh": int(stock_vals[2]), "qtr_stores": int(stock_vals[3]),
                "bah_wh": int(stock_vals[4]), "bah_stores": int(stock_vals[5]),
                "total_stock": total_stock, "ros_wk_ytd": ros, "spot_week_cover": spot,
                "stocks_in_transit": in_transit, "forecasted_wk_cover": forecasted,
                "creator": user,
            }, user)

            # 周销量：Brand Item sheet Z(26)=W1 ... BY(77)=W52
            weekly_rows = []
            for w in range(1, 53):
                col = 25 + w  # Z=26 -> w=1 -> col 26
                qty = _num(cell(ws, r, col))
                if qty is not None:
                    weekly_rows.append((code, w, int(qty), user, user))
            if weekly_rows:
                with db.transaction() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"DELETE FROM {T_WEEKLY} WHERE item_code=%s", (code,))
                        cur.executemany(
                            f"INSERT INTO {T_WEEKLY} (item_code, week_seq, sales_qty, creator, modifier) "
                            f"VALUES (%s,%s,%s,%s,%s)", weekly_rows,
                        )
                weekly_count += len(weekly_rows)

            # 库存快照：六地
            loc_names = ["UAE_WH", "UAE_STORES", "QTR_WH", "QTR_STORES", "BAH_WH", "BAH_STORES"]
            snap_rows = [(code, loc_names[i], int(stock_vals[i]), user, user)
                         for i in range(6)]
            with db.transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"DELETE FROM {T_STOCK} WHERE item_code=%s", (code,))
                    cur.executemany(
                        f"INSERT INTO {T_STOCK} (item_code, location_type, stock_qty, creator, modifier) "
                        f"VALUES (%s,%s,%s,%s,%s)", snap_rows,
                    )
            stock_count += 6
            item_count += 1
        result["item_plan"] = item_count
        result["item_weekly_sales"] = weekly_count
        result["item_stock_snapshot"] = stock_count

    return result


# ---------------------------------------------------------------------------
# 8. 汇总看板 / 校验
# ---------------------------------------------------------------------------
def dashboard(fiscal_year: str = "FY2027") -> Dict[str, Any]:
    header = header_list(fiscal_year)
    h = header[0] if header else {}
    cats = category_list(fiscal_year)
    total_retail = sum(D(c.get("sales_retail")) for c in cats)
    total_buy = sum(D(c.get("fc_buy_plan")) for c in cats)
    top_brands = db.fetch_all(
        f"SELECT brand_name, sale_mix_pct, fc_sales_plan, fc_buy_plan, gp_pct "
        f"FROM {T_BRAND} WHERE fiscal_year=%s ORDER BY sale_mix_pct DESC LIMIT 10",
        (fiscal_year,),
    )
    replen = db.fetch_one(
        f"SELECT COUNT(*) AS total, SUM(CASE WHEN propose_the_qty>0 THEN 1 ELSE 0 END) AS to_order "
        f"FROM {T_ITEM}"
    ) or {"total": 0, "to_order": 0}
    return {
        "fiscal_year": fiscal_year,
        "otb_header": row_out(h),
        "category_count": len(cats),
        "total_sales_retail": float(total_retail),
        "total_buy_plan": float(total_buy),
        "top_brands": rows_out(top_brands),
        "items": {
            "total": replen.get("total") or 0,
            "to_order": replen.get("to_order") or 0,
        },
    }


def validate(fiscal_year: str = "FY2027") -> Dict[str, Any]:
    """数据自检：品类/全局 Mix 合计、成本率一致性、闭合校验"""
    checks = []
    cat = category_check(fiscal_year)
    checks.append({"item": "品类 Sale Mix 合计", **cat})
    mix = mix_list(fiscal_year)
    mix_total = sum(D(m.get("mix_pct")) for m in mix)
    checks.append({
        "item": "全局 Sales Mix 合计", "count": len(mix),
        "sale_mix_total": float(mix_total), "valid": abs(float(mix_total) - 1.0) <= 0.005,
    })
    headers = header_list(fiscal_year)
    if headers:
        result = compute_monthly(headers[0], mix)
        checks.append({"item": "OTB 预算闭合", **{"valid": result["summary"]["check_budget"]}})
        checks.append({"item": "资金闭合", **{"valid": result["summary"]["check_funds"]}})
    return {"fiscal_year": fiscal_year, "checks": checks}
