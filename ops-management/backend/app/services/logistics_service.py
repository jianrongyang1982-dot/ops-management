"""
物流验收跟踪服务

按「集装箱号 + 品牌」查询 WMS 验收/上架数据，聚合出可回写到
transit_containers 的五个时间字段：
  - acceptanceStartTime 开始验收时间  <- imchecksumitem.editdate 最小值（多条取最早）
  - acceptanceCompleteTime 完成验收时间 <- imchecksumitem.editdate 最大值（多条取最晚）
  - orderCloseTime 关单时间            <- imchecksum.checkdate（多条取最晚）
  - earliestShelfTime   最早上架时间  <- Min_Putaway_Date（多条取最早）
  - latestShelfTime     最晚上架时间  <- Max_Putaway_Date（多条取最晚）

说明：
  1. SQL 由两段 UNION ALL 组成：imimport（未验收，flag=0）与 imimportsum（已验收，FLAG>=1）；
     每段各带一组 (containerno, brandid) 参数，共 4 个 %s。
  2. 品牌 note（MMS/DZL/XB）存于 mdmbasedb.brand，resolve_wms_brandid 按 note 查询并保留 brandname 兜底。
  3. 五个时间字段全部回写；原 SQL 中 not exists(...) 后缺少 AND，已补 AND 1=1。
"""
import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.database import fetch_all, fetch_one, execute
from app.core import freightower_logger as flog

logger = logging.getLogger(__name__)


# 用户提供的 SQL，参数：%s = containerno，%s = brandid
LOGISTICS_SQL = """
SELECT
    Owner_ID, Owner_Name, Receiving_Date, Container_No,
    brandid AS Brand_ID, brandname AS Brand_Name,
    importtype AS Logistics_Mode, Sheet_ID, PO_No, Receiving_SNo, Receiving_No,
    Receiving_Status, Putaway_Status,
    acceptanceStartTime, acceptanceCompleteTime, orderCloseTime,
    Vender_ID, Vender_Name, PO_Qty, Receive_Qty, Diff_Qty, Receive_Box,
    putway_qty AS Putaway_Qty, not_putway_qty AS Not_Putaway_Qty,
    not_putaway_box AS Not_Putaway_Box, Putway_Line, Not_Putway_Line,
    Max_Putaway_Date, Min_Putaway_Date,billdate as Bill_Date
FROM (

    SELECT
        ownerid AS Owner_ID, ownername AS Owner_Name,
        sheetdate AS Receiving_Date, brandid, brandname,
        containerno AS Container_No, sheetid AS Sheet_ID,
        pono AS PO_No, importtype,
        checksumno AS Receiving_SNo, checkno AS Receiving_No,
        Receiving_Status AS Receiving_Status,
        Putaway_Status AS Putaway_Status,
        venderid AS Vender_ID, vendername AS Vender_Name,
        po_qty AS PO_Qty, receive_qty AS Receive_Qty,
        difqty AS Diff_Qty, receive_box AS Receive_Box,
        putway_qty, not_putway_qty,
        Max_Putaway_date, Min_Putaway_date,
        Putway_Line, Not_Putway_Line, not_putaway_box,
        acceptanceStartTime, acceptanceCompleteTime, orderCloseTime,billdate
    FROM (

        select t1.ownerid,max(t1.ownername) as ownername,max(t1.sheetdate) as sheetdate,max(t3.brandid) as brandid,
        max(t3.brandname) as brandname, max(t1.containerno) as containerno ,t1.sheetid,
        max(t1.pono) as pono,max(t1.importtype) as importtype,
        null as  checksumno,null as  checkno, max(t1.str1) as str1, 0 as Receiving_Status, 0 as Putaway_Status,
        t1.venderid,max(t1.vendername) as vendername,sum(t2.orderqty) as po_qty,0 as receive_qty,sum(t2.orderqty) as difqty,
        0 as receive_box,0 as putway_qty,0 as not_putway_qty,null  as Max_Putaway_date,null as  Min_Putaway_date,0 as Putway_Line,0 as Not_Putway_Line,0 as not_putaway_box,
        null as acceptanceStartTime,null as acceptanceCompleteTime,null as orderCloseTime,t1.sheetdate as billdate

        from iscewmsdb.imimport t1  inner join iscewmsdb.imimportitem t2 on t1.entid=t2.entid and t1.SHOPID=t2.shopid and t1.sheetid=t2.sheetid
        INNER JOIN iscemdmdb.bmgoodsowner T5 ON T2.ownerid=T5.ownerid AND T2.GDID=T5.gdid
        INNER JOIN iscemdmdb.bmbrand T3 ON T5.brandid=T3.brandid
        where t1.flag=0 and not exists (select importno from iscewmsdb.imimportmerge t3
        inner join iscewmsdb.imchecksum t4 on t3.SHOPID=t4.SHOPID and t3.importsumno=t4.importsumno
        and t1.SHOPID=t3.shopid and t1.sheetid=t3.importno)
        AND 1=1
        AND t1.containerno =  %s
        AND T3.brandid = %s
        group by t1.containerno,t1.ownerid,t1.sheetid,t1.refsheetid


        union all

        SELECT
            t3.ownerid, t3.ownername, t3.sheetdate, t3.brandid, t3.brandname,
            t3.containerno, t3.sheetid, t3.pono, t3.importtype,
            t3.checksumno, t3.checkno, t3.str1,
            t3.flag AS Receiving_Status,
            CASE WHEN t3.importtype='ID' THEN 100
                 WHEN (NVL(t2.not_putway_qty, 0)=0 AND NVL(t2.putway_qty, 0)=0) THEN 0
                 WHEN NVL(t2.not_putway_qty, 0)>0 THEN 0
                 ELSE 100 END AS Putaway_Status,
            t3.venderid, t3.vendername,
            t3.po_qty, t3.receive_qty, t3.difqty, t3.receive_box,
            NVL(t2.putway_qty, 0) AS putway_qty,
            NVL(t2.not_putway_qty, 0) AS not_putway_qty,
            Max_Putaway_date, Min_Putaway_date, Putway_Line, Not_Putway_Line,
            not_putaway_box,
            acceptanceStartTime, acceptanceCompleteTime, orderCloseTime,billdate
        FROM (
            SELECT
                ownerid,
                MAX(ownername) AS ownername,
                max(brandid) AS brandid,
                max(brandname) AS brandname,
                MAX(sheetdate) AS sheetdate,
                max(acceptanceStartTime) AS acceptanceStartTime,
                max(acceptanceCompleteTime) AS acceptanceCompleteTime,
                max(orderCloseTime) AS orderCloseTime,
                max(billdate) as billdate,
                containerno,
                max(importtype) AS importtype,
                sheetid,
                max(pono) AS pono,
                checksumno,
                max(checkno) AS checkno,
                max(flag) AS flag,
                MAX(str1) AS str1,
                MAX(venderid) AS venderid,
                MAX(vendername) AS vendername,
                SUM(po_qty) AS po_qty,
                SUM(receive_qty) AS receive_qty,
                SUM(difqty) AS difqty,
                SUM(receive_box) AS receive_box
            FROM (
                SELECT
                    T1.ownerid, T1.ownername, t3.sheetdate,
                    t4.containerno, t1.sheetid,
                    t3.sheetid AS checksumno,
                    t3.flag, t4.pono, t4.checkno,
                    t1.str1, t1.importtype,
                    t1.venderid, t1.vendername,
                    t2.orderqty AS po_qty,
                    t2.checkqty AS receive_qty,
                    t2.orderqty - t2.checkqty AS difqty,
                    FLOOR(t2.checkqty / t2.packingqty) AS receive_box,
                    t6.brandid, t6.brandname,
                    t7.acceptanceStartTime, t7.acceptanceCompleteTime,
                    t3.checkdate AS orderCloseTime,t4.billdate
                FROM iscewmsdb.imimportsum t1
                INNER JOIN iscewmsdb.imimportsumitem t2
                    ON t1.entid = t2.entid AND t1.sheetid = t2.sheetid
                INNER JOIN iscewmsdb.imchecksum t3
                    ON t1.entid = t3.entid
                    AND t1.sheetid = t3.importsumno
                    AND t3.flag <> 99
                INNER JOIN iscemdmdb.bmgoodsowner T5
                    ON T2.ownerid = T5.ownerid AND T2.GDID = T5.gdid
                INNER JOIN iscemdmdb.bmbrand T6
                    ON T5.brandid = T6.brandid
                INNER JOIN (
                    SELECT entid, sheetid,
                           min(editdate) AS acceptanceStartTime,
                           max(editdate) AS acceptanceCompleteTime
                    FROM iscewmsdb.imchecksumitem
                    GROUP BY entid, sheetid
                ) t7 ON t3.entid = t7.entid AND t3.sheetid = t7.sheetid
                INNER JOIN (
                    SELECT
                        t2.entid, t1.shopid, t2.importsumno,
                        MAX(t1.containerno) AS containerno,
                        max(t1.pono) AS pono,
                        max(t2.checkno) AS checkno,
                        max(t1.sheetdate) as billdate
                    FROM iscewmsdb.imimport t1
                    INNER JOIN iscewmsdb.imimportmerge t2
                        ON t1.entid = t2.entid AND t1.sheetid = t2.importno
                    WHERE 1=1
                    GROUP BY t2.entid, t1.shopid, t2.importsumno
                ) t4
                    ON t1.entid = t4.entid
                    AND t1.shopid = t4.shopid
                    AND t1.sheetid = t4.importsumno
                WHERE T1.FLAG >= 1
            ) t1
            WHERE 1=1
              AND t1.containerno = %s
              AND brandid = %s
            GROUP BY ownerid, containerno, sheetid, checksumno
        ) t3
        LEFT JOIN (
            SELECT
                t1.importsumno,
                SUM(CASE WHEN t2.flag = 13 THEN t2.realqty ELSE 0 END) AS putway_qty,
                SUM(CASE WHEN t2.flag = 10 THEN t2.realqty ELSE 0 END) AS not_putway_qty,
                SUM(CASE WHEN t2.flag = 13 THEN 1 ELSE 0 END) AS Putway_Line,
                SUM(CASE WHEN t2.flag = 10 THEN 1 ELSE 0 END) AS Not_Putway_Line,
                SUM(CASE WHEN t2.flag = 10 THEN FLOOR(t2.realqty / t2.packingqty) ELSE 0 END) AS not_putaway_box,
                max(t2.operatedate) AS Max_Putaway_date,
                min(t2.operatedate) AS Min_Putaway_date
            FROM iscewmsdb.iminstock t1
            INNER JOIN iscewmsdb.iminstockitem t2
                ON t1.entid = t2.entid
                AND t1.shopid = t2.shopid
                AND t1.sheetid = t2.sheetid
            WHERE t2.flag IN (10, 13)
            GROUP BY t1.importsumno
        ) t2 ON t3.sheetid = t2.importsumno
        WHERE 1=1
    ) tmp
) result
ORDER BY Owner_ID, Receiving_Date, Sheet_ID
"""


def resolve_wms_brandid(brand: Optional[str]) -> Optional[str]:
    """把系统品牌编码（如 MMS/XB）解析为 WMS brandid"""
    if not brand:
        return None
    code = str(brand).strip()
    try:
        row = fetch_one(
            "SELECT brandid FROM mdmbasedb.brand "
            "WHERE note=%s AND dbsplitcode=1 LIMIT 1",
            (code,),
        )
        if row and row.get("brandid") is not None:
            return str(row["brandid"])
        # 兜底1：brand 字段本身存的就是 brandid（历史数据如 1001）
        if code.isdigit():
            row = fetch_one(
                "SELECT brandid FROM mdmbasedb.brand "
                "WHERE brandid=%s AND dbsplitcode=1 LIMIT 1",
                (code,),
            )
            if row and row.get("brandid") is not None:
                return str(row["brandid"])
        # 兜底2：品牌名精确匹配
        row = fetch_one(
            "SELECT brandid FROM iscemdmdb.bmbrand "
            "WHERE brandname=%s AND dbsplitcode=1 LIMIT 1",
            (code,),
        )
        if row and row.get("brandid") is not None:
            return str(row["brandid"])
    except Exception as e:
        logger.warning("解析品牌 %s 的 WMS brandid 失败：%s", code, e)
    return None


def _status100(value: Any) -> bool:
    """WMS 状态字段是否为 100（兼容数字/字符串）"""
    if value is None or value == "":
        return False
    try:
        return int(value) == 100
    except (ValueError, TypeError):
        return False


def _parse_dt(value: Any) -> Optional[datetime]:
    """统一转换为 datetime，空值返回 None"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    s = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _min_dt(values: List[Optional[datetime]]) -> Optional[datetime]:
    parsed = [v for v in values if v is not None]
    return min(parsed) if parsed else None


def _max_dt(values: List[Optional[datetime]]) -> Optional[datetime]:
    parsed = [v for v in values if v is not None]
    return max(parsed) if parsed else None


def query_logistics(container_no: str, brand: Optional[str] = None) -> Dict[str, Any]:
    """
    查询 WMS 物流数据并聚合为可回写字段。
    返回 {found, brandid, rows, fields, raw_rows, message}
    """
    container_no = (container_no or "").strip()
    if not container_no:
        return {"found": False, "message": "集装箱号为空，无法查询物流数据", "rows": 0, "fields": {}}

    brandid = resolve_wms_brandid(brand)
    if not brandid:
        return {
            "found": False,
            "brandid": None,
            "rows": 0,
            "fields": {},
            "message": f"品牌 {brand or ''} 未匹配到 WMS brandid（按 mdmbasedb.brand.note 查询）",
        }

    t0 = time.time()
    try:
        rows = fetch_all(LOGISTICS_SQL, (container_no, brandid, container_no, brandid))
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        flog.logger.warning(
            "LOGISTICS QUERY FAIL | container=%s brandid=%s elapsed=%dms error=%s",
            container_no, brandid, elapsed, e,
        )
        raise RuntimeError(f"查询物流数据失败：{e}")

    elapsed = int((time.time() - t0) * 1000)
    flog.logger.info(
        "LOGISTICS QUERY | container=%s brandid=%s rows=%d elapsed=%dms",
        container_no, brandid, len(rows), elapsed,
    )

    if not rows:
        return {
            "found": False,
            "brandid": brandid,
            "rows": 0,
            "fields": {},
            "raw_rows": [],
            "message": "WMS 未查询到该柜号的物流数据",
        }

    fields: Dict[str, Any] = {}
    # 多张验收单时：开始取最早，完成/关单取最晚；上架最早/最晚同理
    start = _min_dt([_parse_dt(r.get("acceptanceStartTime")) for r in rows])
    if start is None:
        start = _min_dt([_parse_dt(r.get("Receiving_Date")) for r in rows])
    complete = _max_dt([_parse_dt(r.get("acceptanceCompleteTime")) for r in rows])
    close = _max_dt([_parse_dt(r.get("orderCloseTime")) for r in rows])
    shelf_min = _min_dt([_parse_dt(r.get("Min_Putaway_Date")) for r in rows])
    shelf_max = _max_dt([_parse_dt(r.get("Max_Putaway_Date")) for r in rows])
    if start:
        fields["acceptanceStartTime"] = start
    if complete:
        fields["acceptanceCompleteTime"] = complete
    if close:
        fields["orderCloseTime"] = close
    if shelf_min:
        fields["earliestShelfTime"] = shelf_min
    if shelf_max:
        fields["latestShelfTime"] = shelf_max
    # 下单日期（Bill_Date / 单据日期）：多张单据取最早
    bill = _min_dt([_parse_dt(r.get("Bill_Date")) for r in rows])
    if bill:
        fields["billdate"] = bill
    # WMS 状态：任一返回行 Receiving_Status/Putaway_Status 为 100 则对应标志=100，否则 0
    fields["receiveflag"] = 100 if any(_status100(r.get("Receiving_Status")) for r in rows) else 0
    fields["PutawayFlag"] = 100 if any(_status100(r.get("Putaway_Status")) for r in rows) else 0

    return {
        "found": bool(fields),
        "brandid": brandid,
        "rows": len(rows),
        "fields": fields,
        "raw_rows": rows[:20],
        "message": "查询成功" if fields else "查询到记录但无有效时间字段",
    }


def writeback(id: int, fields: Dict[str, Any]) -> int:
    """回写三个物流时间字段（自动跳过表中不存在的列）"""
    from app.services.container_service import has_col

    fields = {k: v for k, v in fields.items() if v is not None and has_col(k)}
    if not fields or not id:
        return 0
    sets = ", ".join(f"{k}=%s" for k in fields.keys())
    sql = f"UPDATE transit_containers SET {sets} WHERE id=%s"
    return execute(sql, tuple(fields.values()) + (id,))


def sync_single_row(id: int) -> Dict[str, Any]:
    """单行物流跟踪：查询 WSM -> 聚合 -> 回写 -> 返回结果"""
    from app.services.container_service import get_container

    row = get_container(id)
    if not row:
        return {"success": False, "id": id, "message": "记录不存在"}

    container_no = (row.get("container_no") or "").strip()
    brand = row.get("brand")
    if not container_no:
        return {"success": False, "id": id, "message": "该记录没有集装箱号，无法查询物流数据"}

    try:
        result = query_logistics(container_no, brand)
    except Exception as e:
        return {"success": False, "id": id, "message": str(e)}

    fields = result.get("fields") or {}
    n = writeback(id, fields) if fields else 0
    flog.logger.info(
        "LOGISTICS WRITEBACK | id=%s container=%s brand=%s rows=%s records=%s fields=%s",
        id, container_no, brand, result.get("rows", 0), n,
        flog._safe_json({k: str(v) for k, v in fields.items()}),
    )

    if not result.get("found"):
        return {
            "success": False,
            "id": id,
            "brandid": result.get("brandid"),
            "rows": result.get("rows", 0),
            "message": result.get("message", "未查询到物流数据"),
        }

    return {
        "success": True,
        "id": id,
        "container_no": container_no,
        "brand": brand,
        "brandid": result.get("brandid"),
        "rows": result.get("rows", 0),
        "synced": n,
        "fields": {k: str(v) for k, v in fields.items()},
        "message": "物流跟踪成功",
    }


def sync_all_for_product() -> Dict[str, Any]:
    """定时物流同步：只处理商品(cargotype=0)且未完成(flag<>100)的记录"""
    from app.services.container_service import get_all_for_logistics_sync

    rows = get_all_for_logistics_sync()
    scanned = len(rows)
    synced = 0
    failed = 0
    t0 = time.time()
    for row in rows:
        try:
            res = sync_single_row(row["id"])
            if res.get("success"):
                synced += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.exception("物流同步 id=%s 失败：%s", row["id"], e)
    elapsed = int((time.time() - t0) * 1000)
    flog.logger.info(
        "LOGISTICS SYNC SUMMARY | scanned=%s synced=%s failed=%s elapsed=%dms",
        scanned, synced, failed, elapsed,
    )
    return {
        "success": True,
        "scanned": scanned,
        "synced": synced,
        "failed": failed,
    }
