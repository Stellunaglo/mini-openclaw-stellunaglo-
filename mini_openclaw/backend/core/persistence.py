"""持久化模块 - 会话、记忆、学习的持久化存储"""
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
MEMORY_FILE = DATA_DIR / "memory" / "global_memory.json"
LEARNING_FILE = DATA_DIR / "memory" / "language_learning.json"

# 确保目录存在
for d in [SESSIONS_DIR, DATA_DIR / "memory", DATA_DIR / "config", DATA_DIR / "sandbox"]:
    d.mkdir(parents=True, exist_ok=True)


class SessionPersistence:
    """会话持久化"""

    @staticmethod
    def save(session_id: str, data: dict):
        """保存会话到文件"""
        filepath = SESSIONS_DIR / f"{session_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(session_id: str) -> Optional[dict]:
        """从文件加载会话"""
        filepath = SESSIONS_DIR / f"{session_id}.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    @staticmethod
    def list_all() -> List[str]:
        """列出所有会话ID"""
        return [f.stem for f in SESSIONS_DIR.glob("*.json")]

    @staticmethod
    def delete(session_id: str):
        """删除会话文件"""
        filepath = SESSIONS_DIR / f"{session_id}.json"
        if filepath.exists():
            filepath.unlink()


class MemoryPersistence:
    """全局记忆持久化"""

    def __init__(self):
        self._memory: Dict[str, str] = {}
        self._load()

    def _load(self):
        """加载全局记忆"""
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    self._memory = json.load(f)
            except Exception:
                self._memory = {}

    def save(self):
        """保存全局记忆"""
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._memory, f, ensure_ascii=False, indent=2)

    def get(self, key: str) -> Optional[str]:
        return self._memory.get(key)

    def set(self, key: str, value: str):
        self._memory[key] = value
        self.save()

    def delete(self, key: str):
        if key in self._memory:
            del self._memory[key]
            self.save()

    def get_all(self) -> Dict[str, str]:
        return dict(self._memory)


class LanguageLearning:
    """语言表达学习系统"""

    def __init__(self):
        self._patterns: List[dict] = []
        self._load()

    def _load(self):
        """加载学习数据"""
        if LEARNING_FILE.exists():
            try:
                with open(LEARNING_FILE, "r", encoding="utf-8") as f:
                    self._patterns = json.load(f)
            except Exception:
                self._patterns = []

    def save(self):
        """保存学习数据"""
        with open(LEARNING_FILE, "w", encoding="utf-8") as f:
            json.dump(self._patterns, f, ensure_ascii=False, indent=2)

    def learn(self, input_pattern: str, response_pattern: str, context: str = ""):
        """学习新的表达模式"""
        self._patterns.append({
            "input": input_pattern,
            "response": response_pattern,
            "context": context,
            "learned_at": datetime.now().isoformat(),
            "usage_count": 0
        })
        self.save()

    def find_match(self, user_input: str) -> Optional[str]:
        """查找匹配的学习模式"""
        import re
        for p in self._patterns:
            try:
                if re.search(p["input"], user_input, re.IGNORECASE):
                    p["usage_count"] += 1
                    return p["response"]
            except re.error:
                continue
        return None

    def get_stats(self) -> dict:
        """获取学习统计"""
        total = len(self._patterns)
        total_usage = sum(p["usage_count"] for p in self._patterns)
        return {
            "total_patterns": total,
            "total_usage": total_usage,
            "recent": self._patterns[-10:] if total > 0 else []
        }

    def get_all(self) -> List[dict]:
        return list(self._patterns)


class SandboxManager:
    """沙盒文件隔离管理"""

    def __init__(self, root_dir: str = "data/sandbox"):
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        """解析路径，确保在沙盒内"""
        target = (self.root / path).resolve()
        # 安全检查：确保目标路径在沙盒根目录内
        try:
            target.relative_to(self.root)
            return target
        except ValueError:
            raise PermissionError(f"路径越界: {path}")

    def write(self, path: str, content: str):
        """沙盒内写入文件"""
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

    def read(self, path: str) -> str:
        """沙盒内读取文件"""
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        with open(target, "r", encoding="utf-8") as f:
            return f.read()

    def list_dir(self, path: str = ".") -> List[dict]:
        """列出沙盒目录内容"""
        target = self._resolve(path)
        if not target.is_dir():
            return []
        result = []
        for item in target.iterdir():
            rel = str(item.relative_to(self.root))
            result.append({
                "name": item.name,
                "path": rel,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0
            })
        return result

    def delete(self, path: str):
        """删除沙盒内文件或目录"""
        target = self._resolve(path)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()
