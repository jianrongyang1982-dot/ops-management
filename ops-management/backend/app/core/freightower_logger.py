"""
飞驼请求专用日志：写入 logs/freightower.log，按大小轮转。
记录 Token 获取、轨迹查询（请求参数/耗时/响应/回写）、错误，便于排查。
"""
import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

# 日志目录：与 docker-compose 挂载卷 ./logs:/app/backend/logs 对应
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "freightower.log")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("freightower")
logger.setLevel(logging.INFO)
logger.propagate = False  # 不冒泡到根 logger，避免控制台重复输出

if not logger.handlers:
    _handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)


def _safe_json(obj: Any, max_len: int = 2000) -> str:
    """序列化为 JSON 字符串，超长截断"""
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    return s if len(s) <= max_len else s[:max_len] + "...(truncated)"


def log_token(success: bool, detail: str = "", elapsed_ms: int = 0):
    """记录 Token 获取"""
    status = "OK" if success else "FAIL"
    logger.info(
        "TOKEN %s | elapsed=%dms | %s", status, elapsed_ms, detail
    )


def log_query(
    mode: str,
    params: Dict[str, Any],
    success: bool,
    elapsed_ms: int,
    status_code: Optional[int] = None,
    message: str = "",
    fields: Optional[Dict[str, Any]] = None,
    record_ids: Optional[list] = None,
    error: str = "",
):
    """记录一次轨迹查询：方式、参数、耗时、结果、回写字段"""
    status = "OK" if success else "FAIL"
    parts = [
        f"QUERY {status}",
        f"mode={mode}",
        f"params={_safe_json(params)}",
        f"elapsed={elapsed_ms}ms",
    ]
    if status_code is not None:
        parts.append(f"statusCode={status_code}")
    if message:
        parts.append(f"message={message}")
    if fields is not None:
        parts.append(f"fields={_safe_json(fields)}")
    if record_ids:
        parts.append(f"records={record_ids}")
    if error:
        parts.append(f"error={error}")
    log_line = " | ".join(parts)
    if success:
        logger.info(log_line)
    else:
        logger.warning(log_line)


def log_sync_summary(scanned: int, synced: int, failed: int, elapsed_ms: int):
    logger.info(
        "SYNC SUMMARY | scanned=%d synced=%d failed=%d elapsed=%dms",
        scanned, synced, failed, elapsed_ms,
    )


def read_log(lines: int = 200) -> str:
    """读取日志末尾 N 行（供接口查询）"""
    if not os.path.isfile(LOG_FILE):
        return ""
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return "".join(all_lines[-lines:])
