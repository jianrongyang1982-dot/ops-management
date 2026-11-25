"""
BIDB 数据库访问层 - OTB 采买与商品补货功能

复用现有 OceanBase 连接池（settings 中的 roc 账号），表以 bidb.表名 全限定访问，
与 iscewmsdb / iscemdmdb 的多库访问方式保持一致。
"""
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import pool


def fetch_all(sql: str, params: tuple | dict = ()) -> List[Dict[str, Any]]:
    return pool.fetch_all(sql, params)


def fetch_one(sql: str, params: tuple | dict = ()) -> Optional[Dict[str, Any]]:
    return pool.fetch_one(sql, params)


def execute(sql: str, params: tuple | dict = ()) -> int:
    return pool.execute(sql, params)


def executemany(sql: str, seq_params: List[tuple]) -> int:
    return pool.executemany(sql, seq_params)


@contextmanager
def transaction():
    """批量写入场景：一个事务内执行多条 SQL，异常自动回滚"""
    with pool.transaction() as conn:
        yield conn


def build_where(filters: Dict[str, Any], exact_fields=(), like_fields=()) -> Tuple[str, tuple]:
    """根据过滤条件构造 WHERE 子句（供各 service 复用）"""
    clauses: List[str] = []
    params: List[Any] = []
    for f in exact_fields:
        v = filters.get(f)
        if v not in (None, ""):
            clauses.append(f"{f} = %s")
            params.append(v)
    for f in like_fields:
        v = filters.get(f)
        if v not in (None, ""):
            clauses.append(f"{f} LIKE %s")
            params.append("%" + str(v).strip() + "%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, tuple(params)
