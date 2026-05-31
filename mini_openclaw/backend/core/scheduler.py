"""定时任务模块 - 支持简化格式和基础 cron 表达式"""
import json
import asyncio
import uuid
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable

TASKS_FILE = Path(__file__).parent.parent.parent / "data" / "config" / "scheduled_tasks.json"


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self):
        self._tasks: Dict[str, dict] = {}
        self._running = False
        self._callbacks: Dict[str, Callable] = {}
        self._load()

    def _load(self):
        """加载任务"""
        if TASKS_FILE.exists():
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    self._tasks = json.load(f)
            except Exception:
                self._tasks = {}

    def save(self):
        """保存任务"""
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._tasks, f, ensure_ascii=False, indent=2)

    def add_task(self, name: str, cron: str, description: str,
                 tool_name: str, tool_args: dict, enabled: bool = True) -> str:
        """添加定时任务"""
        task_id = str(uuid.uuid4())[:8]
        self._tasks[task_id] = {
            "task_id": task_id,
            "name": name,
            "cron": cron,
            "description": description,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "enabled": enabled,
            "last_run": None,
            "next_run": None,
            "run_count": 0,
            "created_at": datetime.now().isoformat()
        }
        self._update_next_run(task_id)
        self.save()
        return task_id

    def remove_task(self, task_id: str):
        """删除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self.save()

    def toggle_task(self, task_id: str) -> bool:
        """启用/禁用任务"""
        if task_id in self._tasks:
            self._tasks[task_id]["enabled"] = not self._tasks[task_id]["enabled"]
            self.save()
            return self._tasks[task_id]["enabled"]
        return False

    def get_tasks(self) -> List[dict]:
        """获取所有任务"""
        return list(self._tasks.values())

    def register_callback(self, task_id: str, callback: Callable):
        """注册任务回调"""
        self._callbacks[task_id] = callback

    def _update_next_run(self, task_id: str):
        """更新下次执行时间"""
        task = self._tasks[task_id]
        if not task["enabled"]:
            task["next_run"] = None
            return
        next_time = self._parse_cron(task["cron"])
        task["next_run"] = next_time.isoformat() if next_time else None

    def _parse_cron(self, cron: str) -> Optional[datetime]:
        """解析 cron 表达式 - 支持简化格式和标准 cron"""
        now = datetime.now()

        # 简化格式
        simple_map = {
            "every_minute": lambda: now + timedelta(minutes=1),
            "every_5_minutes": lambda: now + timedelta(minutes=5),
            "every_10_minutes": lambda: now + timedelta(minutes=10),
            "every_30_minutes": lambda: now + timedelta(minutes=30),
            "every_hour": lambda: now + timedelta(hours=1),
            "every_2_hours": lambda: now + timedelta(hours=2),
            "every_6_hours": lambda: now + timedelta(hours=6),
            "every_12_hours": lambda: now + timedelta(hours=12),
            "daily": lambda: (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
            "weekly": lambda: (now + timedelta(weeks=1)).replace(hour=0, minute=0, second=0, microsecond=0),
            "monthly": lambda: (now + timedelta(days=30)).replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        }

        if cron in simple_map:
            return simple_map[cron]()

        # daily_9am, daily_2pm 格式
        daily_match = re.match(r"daily_(\d+)(am|pm)?", cron, re.IGNORECASE)
        if daily_match:
            hour = int(daily_match.group(1))
            period = daily_match.group(2)
            if period and period.lower() == "pm" and hour != 12:
                hour += 12
            next_day = now + timedelta(days=1)
            return next_day.replace(hour=hour, minute=0, second=0, microsecond=0)

        # 标准 cron: "分 时 日 月 周"
        # 基础支持: "*/5 * * * *" (每5分钟), "0 * * * *" (每小时)
        parts = cron.split()
        if len(parts) == 5:
            minute, hour, day, month, weekday = parts

            # */n 格式（每n分钟/小时）
            if minute.startswith("*/") and hour == "*":
                n = int(minute[2:])
                return now + timedelta(minutes=n)

            # 0 * * * * (每小时)
            if minute == "0" and hour == "*":
                return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

            # 0 0 * * * (每天)
            if minute == "0" and hour == "0":
                return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

            # 具体时间点: "30 9 * * *" (每天9:30)
            if minute.isdigit() and hour.isdigit():
                target = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                return target

        # 默认: 5分钟后
        return now + timedelta(minutes=5)

    async def start(self):
        """启动调度器"""
        self._running = True
        while self._running:
            now = datetime.now()
            for task_id, task in list(self._tasks.items()):
                if not task.get("enabled") or not task.get("next_run"):
                    continue
                try:
                    next_run = datetime.fromisoformat(task["next_run"])
                    if now >= next_run:
                        if task_id in self._callbacks:
                            try:
                                await self._callbacks[task_id](task)
                            except Exception as e:
                                print(f"[定时任务] 执行失败 {task_id}: {e}")
                        task["last_run"] = now.isoformat()
                        task["run_count"] = task.get("run_count", 0) + 1
                        self._update_next_run(task_id)
                        self.save()
                except Exception:
                    continue
            await asyncio.sleep(30)

    def stop(self):
        """停止调度器"""
        self._running = False
