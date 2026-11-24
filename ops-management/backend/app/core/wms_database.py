"""
WMS 数据库访问层 - 用于 iscewmsdb 绩效系数表
"""
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import pymysql
import pymysql.cursors

from app.core.config import settings


def connect():
    conn = pymysql.connect(
        host=settings.WMS_DB_HOST,
        port=settings.WMS_DB_PORT,
        user=settings.WMS_DB_USER,
        password=settings.WMS_DB_PASSWORD,
        database=settings.WMS_DB_NAME,
        charset=settings.WMS_DB_CHARSET,
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=15,
        read_timeout=30,
        write_timeout=30,
    )
    # OceanBase 会话默认 autocommit=1，显式关闭以保证整批操作可回滚
    with conn.cursor() as cur:
        cur.execute("SET autocommit = 0")
    return conn


@contextmanager
def connection():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    conn = connect()
    try:
        conn.begin()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _execute(cur, sql: str, params):
    # pymysql 在传入空元组时仍会做 % 格式化，SQL 中的 DATE_FORMAT('%Y-%m') 会被误解析
    if params:
        return cur.execute(sql, params)
    return cur.execute(sql)


def fetch_all(sql: str, params: tuple | dict = ()) -> List[Dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            _execute(cur, sql, params)
            return list(cur.fetchall())


def fetch_one(sql: str, params: tuple | dict = ()) -> Optional[Dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            _execute(cur, sql, params)
            return cur.fetchone()


def execute(sql: str, params: tuple | dict = ()) -> int:
    with transaction() as conn:
        with conn.cursor() as cur:
            return _execute(cur, sql, params)
