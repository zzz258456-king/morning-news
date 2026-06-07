"""
资金流向数据仓库
提供 fund_flow_snapshots 表的操作
"""
import logging
import sqlite3
from typing import Optional

from web.database import get_connection

logger = logging.getLogger(__name__)


class FundFlowRepository:
    """资金流向仓库"""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    def save_snapshot(
        self,
        date: str,
        sector_name: str,
        sector_type: str = "industry",
        main_net_inflow: float = 0,
        retail_net_inflow: float = 0,
        super_large_inflow: float = 0,
        large_inflow: float = 0,
        medium_inflow: float = 0,
        small_inflow: float = 0,
        rank: int = 0,
    ) -> Optional[int]:
        """保存单条资金流向快照"""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO fund_flow_snapshots
                   (date, sector_name, sector_type, main_net_inflow, retail_net_inflow,
                    super_large_inflow, large_inflow, medium_inflow, small_inflow, rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (date, sector_name, sector_type, main_net_inflow, retail_net_inflow,
                 super_large_inflow, large_inflow, medium_inflow, small_inflow, rank),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error("保存资金流向失败: %s", e)
            return None
        finally:
            conn.close()

    def save_batch(self, date: str, items: list[dict]) -> int:
        """
        批量保存资金流向数据

        Args:
            date: 日期
            items: 数据列表，每项包含 sector_name, main_net_inflow 等字段

        Returns:
            成功保存的条数
        """
        # 先删除该日期已有数据
        self.delete_by_date(date)

        conn = self._conn()
        count = 0
        try:
            cursor = conn.cursor()
            for i, item in enumerate(items):
                try:
                    cursor.execute(
                        """INSERT INTO fund_flow_snapshots
                           (date, sector_name, sector_type, main_net_inflow, retail_net_inflow,
                            super_large_inflow, large_inflow, medium_inflow, small_inflow, rank)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            date,
                            item.get("sector_name", ""),
                            item.get("sector_type", "industry"),
                            item.get("main_net_inflow", 0),
                            item.get("retail_net_inflow", 0),
                            item.get("super_large_inflow", 0),
                            item.get("large_inflow", 0),
                            item.get("medium_inflow", 0),
                            item.get("small_inflow", 0),
                            item.get("rank", i + 1),
                        ),
                    )
                    count += 1
                except Exception as e:
                    logger.warning("保存资金流向条目失败: %s", e)
            conn.commit()
            logger.info("批量保存资金流向: date=%s, %d 条", date, count)
        finally:
            conn.close()
        return count

    def query(
        self,
        date: str,
        sector_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        查询指定日期的资金流向数据

        Args:
            date: 日期
            sector_type: 板块类型筛选
            limit: 最大返回数

        Returns:
            资金流向列表
        """
        conn = self._conn()
        try:
            conditions = ["date = ?"]
            params: list = [date]

            if sector_type:
                conditions.append("sector_type = ?")
                params.append(sector_type)

            where = " WHERE " + " AND ".join(conditions)
            query = f"SELECT * FROM fund_flow_snapshots{where} ORDER BY rank ASC LIMIT ?"
            params.append(limit)

            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def exists_for_date(self, date: str) -> bool:
        """检查指定日期是否已有资金流向数据"""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM fund_flow_snapshots WHERE date = ?", (date,)
            )
            return cursor.fetchone()[0] > 0
        finally:
            conn.close()

    def delete_by_date(self, date: str) -> int:
        """删除指定日期的所有资金流向数据"""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM fund_flow_snapshots WHERE date = ?", (date,))
            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info("删除资金流向数据: date=%s, %d 条", date, deleted)
            return deleted
        except Exception as e:
            logger.error("删除资金流向数据失败: %s", e)
            return 0
        finally:
            conn.close()
