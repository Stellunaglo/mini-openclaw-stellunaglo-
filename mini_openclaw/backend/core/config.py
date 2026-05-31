"""配置管理 - 支持持久化配置和Web端修改"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field

CONFIG_DIR = Path(__file__).parent.parent.parent / "data" / "config"
CONFIG_FILE = CONFIG_DIR / "settings.json"


@dataclass
class AppConfig:
    """应用配置"""
    # LLM 配置
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.3
    max_tokens: int = 2000

    # 系统配置
    custom_tools_dir: str = ""
    sandbox_enabled: bool = True
    sandbox_root: str = "data/sandbox"
    auto_save_interval: int = 300  # 秒

    # 学习配置
    learning_enabled: bool = True
    learning_file: str = "data/memory/language_learning.json"

    # 定时任务配置
    scheduled_tasks_enabled: bool = True
    tasks_file: str = "data/config/scheduled_tasks.json"

    # 心跳配置
    heartbeat_enabled: bool = True
    heartbeat_interval: int = 60  # 秒

    # 浏览器配置
    browser_enabled: bool = False
    browser_headless: bool = True

    # 系统控制配置
    system_control_enabled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        # 只加载已知字段
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class ConfigManager:
    """配置管理器"""

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._config = AppConfig()
        self._load()

    def _load(self):
        """从文件加载配置"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._config = AppConfig.from_dict(data)
            except Exception as e:
                print(f"[配置] 加载失败，使用默认配置: {e}")

    def save(self):
        """保存配置到文件"""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[配置] 保存失败: {e}")
            return False

    def get(self, key: str, default=None):
        """获取配置项"""
        return getattr(self._config, key, default)

    def set(self, key: str, value: Any) -> bool:
        """设置配置项"""
        if hasattr(self._config, key):
            setattr(self._config, key, value)
            return self.save()
        return False

    def update(self, updates: Dict[str, Any]) -> bool:
        """批量更新配置"""
        for key, value in updates.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        return self.save()

    def get_all(self) -> dict:
        """获取所有配置（隐藏敏感信息）"""
        data = self._config.to_dict()
        # 隐藏 API Key
        if data.get("api_key"):
            data["api_key"] = data["api_key"][:6] + "****" + data["api_key"][-4:]
        return data

    def get_raw(self) -> AppConfig:
        """获取原始配置对象"""
        return self._config

    def is_real_llm(self) -> bool:
        """是否配置了真实 LLM"""
        return bool(self._config.api_key and self._config.base_url)


# 全局配置实例
config = ConfigManager()
