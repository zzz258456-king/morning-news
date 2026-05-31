"""
任务调度器 - 定时执行爬虫任务
"""
import time
import logging
import threading
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

import schedule

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """定时任务数据类"""
    name: str
    func: Callable
    interval: str  # 例如 "1h", "30m", "daily@10:00"
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    enabled: bool = True
    run_count: int = 0
    result: Any = None


class TaskScheduler:
    """
    任务调度器
    支持按分钟/小时/每天定时执行任务
    """

    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_task(self, name: str, func: Callable, interval: str) -> ScheduledTask:
        """
        添加定时任务
        interval 格式:
            "10s"  - 每10秒
            "5m"   - 每5分钟
            "1h"   - 每小时
            "daily@09:30" - 每天9:30
        """
        task = ScheduledTask(name=name, func=func, interval=interval)
        self._schedule_job(task)
        self.tasks[name] = task
        logger.info(f"添加定时任务: {name} ({interval})")
        return task

    def _schedule_job(self, task: ScheduledTask):
        """将任务注册到 schedule 库"""
        interval = task.interval

        if interval.endswith("s"):
            seconds = int(interval[:-1])
            job = schedule.every(seconds).seconds
        elif interval.endswith("m"):
            minutes = int(interval[:-1])
            job = schedule.every(minutes).minutes
        elif interval.endswith("h"):
            hours = int(interval[:-1])
            job = schedule.every(hours).hours
        elif interval.startswith("daily@"):
            time_str = interval.split("@")[1]
            job = schedule.every().day.at(time_str)
        else:
            raise ValueError(f"不支持的间隔格式: {interval}")

        job.do(self._run_task, task)

    def _run_task(self, task: ScheduledTask):
        """执行任务并记录状态"""
        logger.info(f"执行任务: {task.name}")
        task.last_run = datetime.now().isoformat()
        try:
            task.result = task.func()
            task.run_count += 1
            logger.info(f"任务完成: {task.name} (第{task.run_count}次)")
        except Exception as e:
            logger.error(f"任务失败: {task.name} -> {e}")
            task.result = str(e)
        return task.result

    def remove_task(self, name: str):
        """移除定时任务"""
        if name in self.tasks:
            del self.tasks[name]
            schedule.clear(name)
            logger.info(f"移除任务: {name}")

    def start(self):
        """在后台线程中启动调度器"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SchedulerThread")
        self._thread.start()
        logger.info("调度器已启动")

    def _run_loop(self):
        """调度器主循环"""
        while self._running:
            schedule.run_pending()
            time.sleep(1)

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("调度器已停止")

    def get_status(self) -> dict:
        """获取所有任务状态"""
        return {
            name: {
                "name": t.name,
                "interval": t.interval,
                "enabled": t.enabled,
                "last_run": t.last_run,
                "run_count": t.run_count,
            }
            for name, t in self.tasks.items()
        }

    def run_all_now(self):
        """立即运行所有任务"""
        for task in self.tasks.values():
            self._run_task(task)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
