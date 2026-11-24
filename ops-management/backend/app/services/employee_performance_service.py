"""
员工绩效服务：按 owner / 日期 / 作业人员 / 作业模式汇总工作量与绩效金额
数据源：iscewmsdb（WMS 连接）
"""
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from app.core import wms_database

logger = logging.getLogger(__name__)

BASE_SQL = """
SELECT Work_Mode, `Month`, Owner_ID, Operator, cateid, Cate_Name,
       Total_Operate_Qty, Total_Operate_Amcount,
       Total_Operate_Fee1, Total_Operate_Fee2, Total_Operate_Fee3
FROM (
  SELECT 1 AS Work_Mode,
         DATE_FORMAT(t1.operatedate, '%Y-%m') AS `Month`,
         T1.Owner_ID, Operator, t1.cateid, t1.Cate_Name,
         SUM(Pick_Qty) AS Total_Operate_Qty,
         SUM(Price * Pick_Qty) AS Total_Operate_Amcount,
         SUM(Price * Pick_Qty * NVL(price1, 0)) AS Total_Operate_Fee1,
         SUM(Price * Pick_Qty * NVL(price2, 0)) AS Total_Operate_Fee2,
         SUM(Price * Pick_Qty * NVL(price3, 0)) AS Total_Operate_Fee3
  FROM (
    SELECT CONCAT(T1.OwnerID, '', t1.ownerName) AS Owner_ID,
           DATE(t2.operatedate) AS operatedate,
           t1.sheetid AS Sheet_ID, t1.zoneno AS ZONE_NO,
           t6.cateid, CONCAT(t6.cateid, ' ', t6.catename) AS Cate_Name,
           t2.gdid AS Item_No, t2.gdname AS Item_Name, t2.skuunit AS Unit,
           t2.scellno AS Location, t2.PackingQty,
           t2.realqty AS Pick_Qty,
           CONCAT(t2.operator, ' ', t4.username) AS Operator,
           t3.adviceprice AS Price
    FROM iscewmsdb.omoutstock t1
    INNER JOIN iscewmsdb.omoutstocksitem t2
      ON t1.entid = t2.entid AND t1.sheetid = t2.sheetid
    LEFT JOIN v_goods t3 ON t2.gdid = t3.gdid AND t3.entid = '1'
    LEFT JOIN user.account t4 ON t2.operator = t4.usercode
    LEFT JOIN iscemdmdb.bmgoodsowner t5
      ON t2.ownerid = t5.ownerid AND t2.gdid = t5.gdid
    LEFT JOIN iscemdmdb.bmclassowner t6
      ON t5.ownerid = t6.ownerid AND SUBSTR(t5.groupno, 1, 3) = t6.cateid
    WHERE t1.sheettype IN ('9123000', '9123002', '9123003')
      AND T2.FLAG = 13 AND t2.realqty > 0
      {owner1} {inner_start1} {inner_end1}
  ) T1
  LEFT JOIN iscewmsdb.westlake_workprice t2
    ON t1.CateID = t2.cateid AND t2.workmode = '1'
  WHERE 1 = 1 {operator1}
  GROUP BY DATE_FORMAT(t1.operatedate, '%Y-%m'), T1.Owner_ID, Operator, t1.cateid

  UNION ALL

  SELECT 2 AS Work_Mode,
         DATE_FORMAT(t1.operatedate, '%Y-%m') AS `Month`,
         CONCAT(T1.Owner_ID, '', t1.owner_Name) AS Owner_ID,
         Operator, t1.cateid, t1.Cate_Name,
         SUM(Pick_Qty) AS Total_Operate_Qty,
         SUM(Price * Pick_Qty) AS Total_Operate_Amcount,
         SUM(Price * Pick_Qty * NVL(price1, 0)) AS Total_Operate_Fee1,
         SUM(Price * Pick_Qty * NVL(price1, 0)) AS Total_Operate_Fee2,
         SUM(Price * Pick_Qty * NVL(price3, 0)) AS Total_Operate_Fee3
  FROM (
    SELECT t1.ownerid AS Owner_ID, t1.ownername AS Owner_Name,
           DATE(t1.CheckDate) AS operatedate,
           t1.sheetid AS Sheet_ID,
           t6.cateid, CONCAT(t6.cateid, ' ', t6.catename) AS Cate_Name,
           t2.gdid AS Item_No, t2.gdname AS Item_Name, t2.skuunit AS Unit,
           t2.scanqty AS Pick_Qty,
           CONCAT(t1.editor, ' ', t4.username) AS Operator,
           t3.adviceprice AS Price
    FROM iscewmsdb.omscanpack t1
    INNER JOIN iscewmsdb.omscanpackitem t2
      ON t1.entid = t2.entid AND t1.sheetid = t2.sheetid
    LEFT JOIN v_goods t3 ON t2.gdid = t3.gdid AND t3.entid = '1'
    LEFT JOIN user.account t4 ON t1.editor = t4.usercode
    LEFT JOIN iscemdmdb.bmgoodsowner t5
      ON t2.ownerid = t5.ownerid AND t2.gdid = t5.gdid
    LEFT JOIN iscemdmdb.bmclassowner t6
      ON t5.ownerid = t6.ownerid AND SUBSTR(t5.groupno, 1, 3) = t6.cateid
    WHERE T1.FLAG = 100
      {owner2} {inner_start2} {inner_end2}
  ) T1
  LEFT JOIN iscewmsdb.westlake_workprice t2
    ON t1.CateID = t2.cateid AND t2.workmode = '2'
  WHERE 1 = 1 {operator2}
  GROUP BY DATE_FORMAT(t1.operatedate, '%Y-%m'), T1.Owner_ID, Operator, t1.cateid
) T1
WHERE 1 = 1 {workmode}
"""


def _build_sql(filters: Dict[str, Any]) -> Tuple[str, tuple]:
    owner = str(filters.get("ownerid") or "").strip()
    start = str(filters.get("start_date") or "").strip()
    end = str(filters.get("end_date") or "").strip()
    operator = str(filters.get("operator") or "").strip()
    workmode = str(filters.get("workmode") or "").strip()

    owner_clause = "AND t2.ownerid = %s" if owner else ""
    # 日期条件下推到明细表，避免先 join 出全部明细再在最外层过滤
    inner_start1 = "AND t2.operatedate >= %s" if start else ""
    inner_end1 = "AND t2.operatedate < DATE_ADD(%s, INTERVAL 1 DAY)" if end else ""
    inner_start2 = "AND t1.CheckDate >= %s" if start else ""
    inner_end2 = "AND t1.CheckDate < DATE_ADD(%s, INTERVAL 1 DAY)" if end else ""
    operator_clause = "AND T1.Operator LIKE %s" if operator else ""
    workmode_clause = "AND T1.Work_Mode = %s" if workmode else ""

    sql = BASE_SQL.format(
        owner1=owner_clause,
        inner_start1=inner_start1,
        inner_end1=inner_end1,
        operator1=operator_clause,
        owner2=owner_clause,
        inner_start2=inner_start2,
        inner_end2=inner_end2,
        operator2=operator_clause,
        workmode=workmode_clause,
    )

    params: List[Any] = []
    # SQL 占位符顺序按出现位置：
    # 分支1: owner1, start1, end1, operator1
    # 分支2: owner2, start2, end2, operator2
    # 最外层: workmode
    pattern = "%" + operator + "%" if operator else ""
    for _ in range(2):
        if owner:
            params.append(owner)
        if start:
            params.append(start)
        if end:
            params.append(end)
        if operator:
            params.append(pattern)
    if workmode:
        params.append(workmode)
    return sql, tuple(params)


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _row_out(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "work_mode": str(row.get("Work_Mode") or ""),
        "month": row.get("Month"),
        "owner_id": row.get("Owner_ID"),
        "operator": row.get("Operator"),
        "cateid": row.get("cateid"),
        "cate_name": row.get("Cate_Name"),
        "total_operate_qty": _num(row.get("Total_Operate_Qty")),
        "total_operate_amcount": _num(row.get("Total_Operate_Amcount")),
        "total_operate_fee1": _num(row.get("Total_Operate_Fee1")),
        "total_operate_fee2": _num(row.get("Total_Operate_Fee2")),
        "total_operate_fee3": _num(row.get("Total_Operate_Fee3")),
    }


def _escape_percent_for_params(sql: str) -> str:
    """pymysql 传参时会做 % 格式化，DATE_FORMAT 的 %Y/%m 需要转义"""
    return sql.replace("'%Y-%m'", "'%%Y-%%m'")


def _render_sql(sql: str, params: tuple) -> str:
    """把占位符替换成可见参数值，仅用于日志，不用于执行"""
    if not params:
        return sql.replace("%%", "%")
    parts = sql.split("%s")
    if len(parts) - 1 != len(params):
        return sql.replace("%%", "%") + f"  -- PARAMS={params!r}"
    rendered = parts[0]
    for value, tail in zip(params, parts[1:]):
        if value is None:
            literal = "NULL"
        elif isinstance(value, (int, float, Decimal)):
            literal = str(value)
        else:
            literal = "'" + str(value).replace("'", "''") + "'"
        rendered += literal + tail
    return rendered.replace("%%", "%")


def _run_with_log(label: str, sql: str, params: tuple, fetcher):
    started = time.perf_counter()
    try:
        return fetcher(sql, params)
    finally:
        elapsed = time.perf_counter() - started
        logger.info(
            "[员工绩效SQL][%s] 耗时=%.3fs 参数=%s\n%s",
            label, elapsed, params, _render_sql(sql, params),
        )


def query(filters: Dict[str, Any], page: int, page_size: int) -> Tuple[int, List[Dict[str, Any]]]:
    sql, params = _build_sql(filters)

    count_sql = f"SELECT COUNT(*) AS n FROM ({sql}) T_COUNT"
    count_exec = _escape_percent_for_params(count_sql) if params else count_sql
    total = _run_with_log(
        "COUNT", count_exec, params,
        lambda s, p: wms_database.fetch_one(s, p)["n"],
    )

    page_sql = (
        f"SELECT * FROM ({sql}) T_PAGE "
        "ORDER BY `Month` DESC, cateid, Operator "
        "LIMIT %s OFFSET %s"
    )
    page_params = params + (page_size, (page - 1) * page_size)
    rows = _run_with_log(
        "PAGE", _escape_percent_for_params(page_sql), page_params,
        wms_database.fetch_all,
    )
    return total, [_row_out(r) for r in rows]
