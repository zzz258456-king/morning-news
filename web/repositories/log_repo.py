"""
日志数据仓库
提供 daily_logs 表的操作
"""
import json
import logging
import sqlite3
from typing import Any, Optional

from web.database import get_connection

logger = logging.getLogger(__name__)


class LogRepository:
    """日志仓库"""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    def add(
        self,
        date: str,
        log_type: str,
        status: str = "info",
        summary: str = "",
        detail: Optional[dict] = None,
    ) -> Optional[int]:
        """
        添加日志记录

        Args:
            date: 日期
            log_type: 日志类型 (morning, risk, trade, system 等)
            status: 状态 (info, success, warning, error)
            summary: 摘要
            detail: 详情字典

        Returns:
            新建记录 ID
        """
        detail_json = json.dumps(detail or {}, ensure_ascii=False)
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO daily_logs (date, log_type, status, summary, detail)
                   VALUES (?, ?, ?, ?, ?)""",
                (date, log_type, status, summary, detail_json),
            )
            conn.commit()
            log_id = cursor.lastrowid
            logger.debug("添加日志: id=%d, type=%s, date=%s", log_id, log_type, date)
            return log_id
        except Exception as e:
            logger.error("添加日志失败: %s", e)
            return None
        finally:
            conn.close()

    def get_by_id(self, log_id: int) -> Optional[dict]:
        """根据 ID 获取日志"""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM daily_logs WHERE id = ?", (log_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # 解析 detail JSON
                try:
                    result["detail"] = json.loads(result.get("detail", "{}"))
                except (json.JSONDecodeError, TypeError):
                    result["detail"] = {}
                return result
            return None
        finally:
            conn.close()

    def list_by_date(self, date: str) -> list[dict]:
        """查询指定日期的所有日志"""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM daily_logs WHERE date = ? ORDER BY id ASC", (date,)
            )
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                try:
                    result["detail"] = json.loads(result.get("detail", "{}"))
                except (json.JSONDecodeError, TypeError):
                    result["detail"] = {}
                results.append(result)
            return results
        finally:
            conn.close()

    def list_by_type(self, log_type: str, limit: int = 50) -> list[dict]:
        """查询指定类型的日志"""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM daily_logs WHERE log_type = ? ORDER BY date DESC, id DESC LIMIT ?",
                (log_type, limit),
            )
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                try:
                    result["detail"] = json.loads(result.get("detail", "{}"))
                except (json.JSONDecodeError, TypeError):
                    result["detail"] = {}
                results.append(result)
            return results
        finally:
            conn.close()

    def has_morning_for_date(self, date: str) -> bool:
        """检查指定日期是否有晨报日志"""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM daily_logs WHERE date = ? AND log_type = 'morning'",
                (date,),
            )
            return cursor.fetchone()[0] > 0
        finally:
            conn.close()

    def list_dates_with_logs(self, year: int, month: int) -> list[str]:
        """查询指定年月中有日志的日期列表"""
        conn = self._conn()
        try:
            prefix = f"{year:04d}-{month:02d}"
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT date FROM daily_logs WHERE date LIKE ? ORDER BY date",
                (f"{prefix}%",),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
