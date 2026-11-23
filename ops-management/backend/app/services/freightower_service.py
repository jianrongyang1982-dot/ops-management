"""
飞驼开放平台同步服务
1. 获取 Token 并缓存（过期前刷新）
2. 用提单号查询轨迹
3. 解析 eventCode -> 日期字段，回写数据库
4. 同一 bl 多品牌批量回写
"""
import json
import logging
import threading
import time
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.database import fetch_all, execute, pool
from app.core import freightower_logger as flog

logger = logging.getLogger(__name__)

# eventCode -> 表字段
EVENT_FIELD_MAP = {
    "STSP": "stspdate",   # 提空箱
    "LOBD": "loaddate",   # 装船
    "STCS": "stcsdate",   # 提柜
    "RCVE": "rcvedate",   # 还空箱
}


class TokenManager:
    """Token 缓存管理：线程安全，过期前60秒自动刷新"""

    def __init__(self):
        self._token: Optional[str] = None
        self._expire_at: float = 0.0
        self._lock = threading.Lock()

    def get_token(self, force: bool = False) -> str:
        with self._lock:
            now = time.time()
            if not force and self._token and now < self._expire_at - 60:
                return self._token
            token, expires_in = self._fetch_token()
            self._token = token
            self._expire_at = now + expires_in
            logger.info("飞驼 Token 已刷新，有效期 %s 秒", expires_in)
            return token

    def _fetch_token(self) -> Tuple[str, int]:
        payload = {
            "clientId": settings.FREIGHTOWER_CLIENT_ID,
            "secret": settings.FREIGHTOWER_SECRET,
        }
        t0 = time.time()
        try:
            resp = httpx.post(
                settings.FREIGHTOWER_TOKEN_URL, json=payload, timeout=20.0
            )
            data = resp.json()
        except Exception as e:
            flog.log_token(False, f"请求异常：{e}", int((time.time() - t0) * 1000))
            raise RuntimeError(f"请求飞驼 Token 失败：{e}")

        elapsed = int((time.time() - t0) * 1000)
        if data.get("statusCode") != 20000:
            flog.log_token(False, f"{data.get('message')} ({data.get('statusCode')})", elapsed)
            raise RuntimeError(f"飞驼 Token 获取失败：{data.get('message')} ({data.get('statusCode')})")

        token = (data.get("data") or {}).get("access_token")
        if not token:
            flog.log_token(False, "响应缺少 access_token", elapsed)
            raise RuntimeError("飞驼 Token 响应中缺少 access_token")
        flog.log_token(True, f"statusCode=20000 token={str(token)[:8]}...", elapsed)
        try:
            expires_in = int((data["data"].get("expires_in") or 7200))
        except (ValueError, TypeError):
            expires_in = 7200
        return token, expires_in


token_manager = TokenManager()


def _parse_date(value: Optional[str]) -> Optional[date]:
    """解析飞驼日期 YYYY/MM/DD HH:mm:ss -> date（不换算时区，取日期部分）"""
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19] if len(s) >= 19 else s, fmt).date()
        except ValueError:
            continue
    return None


def _do_query(payload: Dict[str, Any], mode: str = "unknown") -> Optional[Dict[str, Any]]:
    """执行一次轨迹查询，返回 data.result；业务错误或无数据返回 None"""
    token = token_manager.get_token()
    base_payload = {
        "billNo": "",
        "containerNo": "",
        "carrierCode": "",
        "portCode": "",
        "isExport": "",
        "businessNo": "",
        "billCategory": "",
        "polCode": "",
        "podCode": "",
    }
    base_payload.update(payload)
    headers = {"Authorization": f"Bearer {token}"}
    t0 = time.time()
    try:
        resp = httpx.post(
            settings.FREIGHTOWER_QUERY_URL, json=base_payload, headers=headers, timeout=30.0
        )
        data = resp.json()
    except Exception as e:
        flog.log_query(mode, base_payload, False, int((time.time() - t0) * 1000), error=str(e))
        raise RuntimeError(f"查询轨迹失败：{e}")

    elapsed = int((time.time() - t0) * 1000)
    status_code = data.get("statusCode")
    message = data.get("message") or ""

    if status_code != 20000:
        # 业务错误（如查无此单）视为未命中，由调用方决定是否换方式重试
        logger.warning("飞驼查询未命中：%s (%s)", message, status_code)
        flog.log_query(mode, base_payload, False, elapsed, status_code, message)
        return None

    result = ((data.get("data") or {}).get("result")) or {}
    if not result:
        flog.log_query(mode, base_payload, False, elapsed, status_code, "无 result 数据")
        return None

    flog.log_query(mode, base_payload, True, elapsed, status_code, message)
    return result


def query_tracking(bill_no: str) -> Optional[Dict[str, Any]]:
    """方式一：按提单号查询轨迹"""
    return _do_query({"billNo": bill_no, "carrierCode": "auto"}, mode="billNo")


def query_by_container(container_no: str, carrier_code: str, port_code: str) -> Optional[Dict[str, Any]]:
    """方式二：按柜号 + 船公司代码 + 起运港查询（billNo 方式失败时的兜底）"""
    return _do_query({
        "billNo": "",
        "containerNo": container_no,
        "carrierCode": carrier_code,
        "portCode": port_code,
        "isExport": "E",
    }, mode="containerNo")


def parse_tracking(result: Dict[str, Any], container_no: Optional[str] = None) -> Dict[str, Any]:
    """
    解析轨迹结果为可回写字段字典
    - 从 containers[].status[] 按 eventCode 取 eventTime
    - plandate（预计到达）取 delivery.eta，eta 为空时回退取 delivery.sta
    - acdate（实际到达）取 delivery.ata
    - voyage 取 firstVessel.voyage
    - currentStatus 存 result.currentStatus 的 JSON 字符串
    - statusEsti 存 containers[].status[].isEsti 映射（Y=计划，N=实际）
    - containers 多条时按 container_no 匹配，匹配不到取第一条
    """
    fields: Dict[str, Any] = {}

    containers = result.get("containers") or []
    target = None
    if container_no:
        for c in containers:
            if str(c.get("containerNo", "")).strip().upper() == str(container_no).strip().upper():
                target = c
                break
    if target is None and containers:
        target = containers[0]

    esti_map: Dict[str, str] = {}
    if target:
        for st in target.get("status") or []:
            code = st.get("eventCode")
            # isEsti: Y=计划（未实际发生），N=实际
            if code and st.get("isEsti") is not None:
                esti_map[code] = str(st.get("isEsti")).upper()
            if code in EVENT_FIELD_MAP:
                d = _parse_date(st.get("eventTime"))
                if d:
                    fields[EVENT_FIELD_MAP[code]] = d
    # 供前端链路条上色：plan 节点固定为计划，actual 节点固定为实际
    esti_map["PLAN"] = "Y"
    esti_map["ACTUAL"] = "N"
    fields["statusEsti"] = json.dumps(esti_map, ensure_ascii=False, separators=(",", ":"))

    # 当前状态（整段 JSON 字符串），如 currentStatus.currentStatusCode / descriptionCn / eventTime
    current_status = result.get("currentStatus")
    if current_status:
        fields["currentStatus"] = json.dumps(current_status, ensure_ascii=False, separators=(",", ":"))
        # 当前状态为还空箱(RCVE)时，标记任务完成 flag=100
        if str(current_status.get("eventCode") or "").strip().upper() == "RCVE":
            fields["flag"] = 100

    # 预计到达(plandate)：delivery.eta，为空回退 delivery.sta
    # 实际到达(acdate)：delivery.ata
    delivery = result.get("delivery") or {}
    d_eta = _parse_date(delivery.get("eta"))
    d_sta = _parse_date(delivery.get("sta"))
    d_ata = _parse_date(delivery.get("ata"))
    d_plan = d_eta or d_sta
    if d_plan:
        fields["plandate"] = d_plan
    # 实际到达取 ata；ata 为空时显式写 None 清空旧值（避免历史 sta 残留被误判为已到达）
    fields["acdate"] = d_ata

    voyage = (result.get("firstVessel") or {}).get("voyage")
    if not voyage:
        routes = result.get("routes") or []
        if routes:
            voyage = (routes[0].get("modeDetails") or {}).get("voyage")
    if voyage:
        fields["voyage"] = str(voyage)

    # 飞驼详情链接：优先短链 iframeShortUrl，其次 iframeUrl
    url = result.get("iframeShortUrl") or result.get("iframeUrl")
    if url:
        fields["url"] = str(url)[:500]

    return fields


def writeback(ids: List[int], fields: Dict[str, Any]) -> int:
    """回写日期字段到数据库（批量 ID），自动跳过表中不存在的字段"""
    from app.services.container_service import has_col
    fields = {k: v for k, v in fields.items() if has_col(k)}
    if not fields or not ids:
        return 0
    sets = ", ".join(f"{k}=%s" for k in fields.keys())
    values = list(fields.values())
    placeholders = ", ".join(["%s"] * len(ids))
    sql = f"UPDATE transit_containers SET {sets} WHERE id IN ({placeholders})"
    with pool.transaction() as conn:
        with conn.cursor() as cur:
            return cur.execute(sql, tuple(values) + tuple(ids))


def sync_one_bl(bl: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """同步单个提单号，批量回写所有品牌记录"""
    result = query_tracking(bl)
    if not result:
        return {"bl": bl, "status": "no_data", "synced": 0}

    # 优先用第一条记录的柜号匹配 containers
    container_no = rows[0].get("container_no") if rows else None
    fields = parse_tracking(result, container_no)
    if not fields:
        return {"bl": bl, "status": "no_fields", "synced": 0}

    ids = [r["id"] for r in rows]
    n = writeback(ids, fields)
    return {"bl": bl, "status": "ok", "synced": n, "fields": {k: str(v) for k, v in fields.items()}}


def sync_all() -> Dict[str, Any]:
    """全量同步未关单数据：同一 bl 只调一次接口"""
    from app.services.container_service import get_all_for_sync

    rows = get_all_for_sync()
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        bl = r.get("bl")
        if bl:
            grouped.setdefault(bl, []).append(r)

    scanned = len(rows)
    synced = 0
    failed = 0
    details = []
    t0 = time.time()

    for bl, bl_rows in grouped.items():
        try:
            res = sync_one_bl(bl, bl_rows)
            details.append(res)
            synced += res.get("synced", 0)
        except Exception as e:
            failed += 1
            details.append({"bl": bl, "status": "error", "error": str(e)})
            logger.exception("同步提单 %s 失败", bl)

    flog.log_sync_summary(scanned, synced, failed, int((time.time() - t0) * 1000))
    return {
        "success": True,
        "message": "同步完成",
        "scanned": scanned,
        "synced": synced,
        "skipped": 0,
        "failed": failed,
        "details": details,
    }


def sync_single_row(id: int) -> Dict[str, Any]:
    """
    单条记录手动调用飞驼：
    1) 先按 billNo（表的 bl）查询
    2) 失败/无数据则按 containerNo + carrierCode(ship_co) + portCode(pol) + isExport=E 重试
    3) 命中后回写 url 及六个日期字段，并返回回写结果
    """
    from app.services.container_service import get_container

    row = get_container(id)
    if not row:
        return {"success": False, "message": "记录不存在", "id": id}

    # 已完成(flag=100)不再调用飞驼，需先点“重置”把状态改回 0
    if row.get("flag") is not None and int(row["flag"]) == 100:
        return {"success": False, "id": id, "message": "该记录已完成(flag=100)，请先重置后再调用"}

    bl = (row.get("bl") or "").strip()
    container_no = (row.get("container_no") or "").strip()
    carrier_code = (row.get("ship_co") or "").strip() or "auto"
    port_code = (row.get("pol") or "").strip()

    result = None
    mode = None
    # 方式一：提单号
    if bl:
        try:
            result = query_tracking(bl)
            if result:
                mode = "billNo"
        except Exception as e:
            logger.warning("记录 %s billNo(%s) 查询异常：%s", id, bl, e)

    # 方式二：柜号 + 船公司 + 起运港
    if not result and container_no:
        try:
            result = query_by_container(container_no, carrier_code, port_code)
            if result:
                mode = "containerNo"
        except Exception as e:
            logger.warning("记录 %s containerNo(%s) 查询异常：%s", id, container_no, e)

    if not result:
        return {
            "success": False,
            "id": id,
            "mode": mode,
            "message": "两种方式均未查询到轨迹数据",
        }

    fields = parse_tracking(result, container_no)
    n = writeback([id], fields) if fields else 0
    flog.logger.info(
        "WRITEBACK | id=%s mode=%s records=%s fields=%s",
        id, mode, n, flog._safe_json({k: str(v) for k, v in fields.items()}),
    )
    return {
        "success": True,
        "id": id,
        "mode": mode,
        "message": "同步成功",
        "synced": n,
        "fields": {k: str(v) for k, v in fields.items()},
        "statusCategory": result.get("statusCategory"),
        "description": result.get("statusDescription"),
    }
