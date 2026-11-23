"""
数据库访问层 - 基于 pymysql 的轻量连接池
"""
import queue
import logging
from contextlib import contextmanager
from typing import Any, List, Optional, Dict

import pymysql
import pymysql.cursors

from app.core.config import settings

logger = logging.getLogger(__name__)


class MySQLPool:
    """简单可靠的 MySQL/OceanBase 连接池"""

    def __init__(self, size: int = 10):
        self._max = size
        self._pool: queue.Queue = queue.Queue(maxsize=size)
        self._created = 0
        for _ in range(min(size, 4)):
            self._pool.put(self._new_conn())

    def _new_conn(self):
        conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            charset=settings.DB_CHARSET,
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=15,
            read_timeout=30,
            write_timeout=30,
        )
        self._created += 1
        return conn

    def get_conn(self):
        try:
            conn = self._pool.get_nowait()
        except queue.Empty:
            if self._created < self._max + 20:
                conn = self._new_conn()
            else:
                conn = self._pool.get(timeout=30)
        # 检测断线重连
        try:
            conn.ping(reconnect=True)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            conn = self._new_conn()
        return conn

    def put_conn(self, conn):
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            try:
                conn.close()
            except Exception:
                pass

    @contextmanager
    def connection(self):
        conn = self.get_conn()
        try:
            yield conn
        finally:
            self.put_conn(conn)

    @contextmanager
    def transaction(self):
        """事务上下文：异常自动回滚"""
        conn = self.get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.put_conn(conn)

    def fetch_all(self, sql: str, params: tuple | dict = ()) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    def fetch_one(self, sql: str, params: tuple | dict = ()) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()

    def execute(self, sql: str, params: tuple | dict = ()) -> int:
        with self.transaction() as conn:
            with conn.cursor() as cur:
                return cur.execute(sql, params)

    def executemany(self, sql: str, seq_params: List[tuple]) -> int:
        with self.transaction() as conn:
            with conn.cursor() as cur:
                return cur.executemany(sql, seq_params)


pool = MySQLPool(size=settings.DB_POOL_SIZE)


def fetch_all(sql: str, params: tuple | dict = ()) -> List[Dict[str, Any]]:
    return pool.fetch_all(sql, params)


def fetch_one(sql: str, params: tuple | dict = ()) -> Optional[Dict[str, Any]]:
    return pool.fetch_one(sql, params)


def execute(sql: str, params: tuple | dict = ()) -> int:
    return pool.execute(sql, params)
