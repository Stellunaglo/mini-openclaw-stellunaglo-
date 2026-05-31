"""数据模型定义"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


@dataclass
class ToolCall:
    """工具调用指令"""
    tool: str
    args: Dict[str, Any]


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any
    error: Optional[str] = None


@dataclass
class Message:
    """对话消息"""
    role: str
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_results: Optional[List[ToolResult]] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ToolDefinition:
    """工具定义（用于注册和描述）"""
    name: str
    description: str
    parameters: Dict[str, Any]
    required: List[str]

    def to_openai_format(self) -> dict:
        """转换为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required
                }
            }
        }


@dataclass
class Session:
    """会话对象"""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    memory: Dict[str, str] = field(default_factory=dict)
    virtual_fs: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str):
        msg = Message(role=role, content=content)
        self.messages.append(msg)
        self.updated_at = datetime.now()
        return msg

    def get_recent_messages(self, n: int = 10) -> List[dict]:
        """获取最近 n 条消息，用于 LLM 上下文"""
        recent = self.messages[-n:] if len(self.messages) > n else self.messages
        return [{"role": m.role, "content": m.content} for m in recent]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "memory_keys": list(self.memory.keys()),
            "file_count": len(self.virtual_fs),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class ScheduledTask:
    """定时任务"""
    task_id: str
    name: str
    cron: str  # cron 表达式或简化格式
    description: str
    tool_name: str
    tool_args: Dict[str, Any]
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "cron": self.cron,
            "description": self.description,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "created_at": self.created_at.isoformat()
        }
