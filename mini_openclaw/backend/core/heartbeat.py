"""主动心跳模块 - 系统状态监控和主动报告"""
import asyncio
import json
import psutil
from datetime import datetime
from typing import Callable, Optional


class HeartbeatMonitor:
    """心跳监控器 - 定期收集系统状态并主动报告"""

    def __init__(self, interval: int = 60):
        self.interval = interval
        self._running = False
        self._callbacks: List[Callable] = []
        self._last_status: Optional[dict] = None

    def on_beat(self, callback: Callable):
        """注册心跳回调"""
        self._callbacks.append(callback)

    def get_status(self) -> dict:
        """获取当前系统状态"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            status = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                },
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
            }
            self._last_status = status
            return status
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }

    async def start(self):
        """启动心跳"""
        self._running = True
        while self._running:
            status = self.get_status()
            for callback in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(status)
                    else:
                        callback(status)
                except Exception as e:
                    print(f"[心跳] 回调执行失败: {e}")
            await asyncio.sleep(self.interval)

    def stop(self):
        """停止心跳"""
        self._running = False

    def get_last_status(self) -> Optional[dict]:
        """获取最后一次状态"""
        return self._last_status
