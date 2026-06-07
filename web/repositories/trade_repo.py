"""
交易记录数据仓库
提供 trades 表的 CRUD 操作
"""
import logging
import sqlite3
from datetime import datetime
from typing import Optional

from web.database import get_connection

logger = logging.getLogger(__name__)


class TradeRepository:
    """交易记录仓库"""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    def create(
        self,
        date: str,
        stock_code: str,
        stock_name: str,
        action: str,
        price: float,
        quantity: int,
        reason: str = "",
        reflection: str = "",
        tags: str = "",
    ) -> Optional[int]:
        """
        创建交易记录

        Returns:
            新建记录 ID，失败返回 None
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO trades
                   (date, stock_code, stock_name, action, price, quantity, reason, reflection, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (date, stock_code, stock_name, action, price, quantity, reason, reflection, tags),
            )
            conn.commit()
            trade_id = cursor.lastrowid
            logger.info("创建交易记录: id=%d, %s %s %s", trade_id, date, action, stock_code)
            return trade_id
        except Exception as e:
            logger.error("创建交易记录失败: %s", e)
            return None
        finally:
            conn.close()

    def get_by_id(self, trade_id: int) -> Optional[dict]:
        """根据 ID 获取交易记录"""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def list_all(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        stock_code: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        查询交易记录列表

        Args:
            start_date: 起始日期
            end_date: 结束日期
            stock_code: 股票代码筛选
            limit: 每页数量
            offset: 偏移量

        Returns:
            交易记录列表
        """
        conn = self._conn()
        try:
            conditions = []
            params = []

            if start_date:
                conditions.append("date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("date <= ?")
                params.append(end_date)
            if stock_code:
                conditions.append("stock_code = ?")
                params.append(stock_code)

            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"SELECT * FROM trades{where} ORDER BY date DESC, id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def list_by_date(self, date: str) -> list[dict]:
        """根据日期查询交易记录"""
        return self.list_all(start_date=date, end_date=date)

    def update(self, trade_id: int, **kwargs) -> bool:
        """
        更新交易记录

        Args:
            trade_id: 交易 ID
            **kwargs: 要更新的字段

        Returns:
            是否更新成功
        """
        if not kwargs:
            return False

        allowed = {
            "date", "stock_code", "stock_name", "action",
            "price", "quantity", "reason", "reflection", "tags",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return False

        updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [trade_id]

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE trades SET {set_clause} WHERE id = ?", values)
            conn.commit()
            if cursor.rowcount > 0:
                logger.info("更新交易记录: id=%d", trade_id)
                return True
            return False
        except Exception as e:
            logger.error("更新交易记录失败: %s", e)
            return False
        finally:
            conn.close()

    def delete(self, trade_id: int) -> bool:
        """删除交易记录"""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
            conn.commit()
            if cursor.rowcount > 0:
                logger.info("删除交易记录: id=%d", trade_id)
                return True
            return False
        except Exception as e:
            logger.error("删除交易记录失败: %s", e)
            return False
        finally:
            conn.close()

    def count(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> int:
        """统计交易记录数量"""
        conn = self._conn()
        try:
            conditions = []
            params = []
            if start_date:
                conditions.append("date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("date <= ?")
                params.append(end_date)

            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM trades{where}", params)
            return cursor.fetchone()[0]
        finally:
            conn.close()
