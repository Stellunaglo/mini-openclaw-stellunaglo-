"""Mini OpenClaw 核心 Agent 类"""
import json
import re
import asyncio
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from backend.core.models import Session, Message
from backend.core.registry import ToolRegistry
from backend.core.llm import LLMClient
from backend.core.config import config
from backend.core.persistence import SessionPersistence, MemoryPersistence, LanguageLearning, SandboxManager
from backend.core.scheduler import TaskScheduler
from backend.core.heartbeat import HeartbeatMonitor


class MiniOpenClaw:
    """Mini OpenClaw 核心类 - 支持多会话、持久化、沙盒、学习、定时任务"""

    def __init__(self, api_key: str = "", base_url: str = "", model: str = "",
                 custom_tools_dir: str = ""):
        # 使用配置管理器
        cfg = config.get_raw()
        self.api_key = api_key or cfg.api_key
        self.base_url = base_url or cfg.base_url
        self.model = model or cfg.model
        self.custom_tools_dir = custom_tools_dir or cfg.custom_tools_dir

        self.tools = ToolRegistry()
        self.llm = LLMClient(self.api_key, self.base_url, self.model)
        self.sessions: Dict[str, Session] = {}
        self.global_memory = MemoryPersistence()
        self.learning = LanguageLearning()
        self.sandbox = SandboxManager(cfg.sandbox_root)
        self.scheduler = TaskScheduler()
        self.heartbeat = HeartbeatMonitor(cfg.heartbeat_interval)

        # 加载持久化会话
        self._load_sessions()

        self.builtin = None
        self._setup_default_tools()

        # 加载自定义工具
        if self.custom_tools_dir:
            self.tools.load_custom_tools(self.custom_tools_dir)

        # 注册定时任务回调
        self._setup_scheduler_callbacks()

        # 注册心跳回调
        if cfg.heartbeat_enabled:
            self._setup_heartbeat()

    def _setup_default_tools(self):
        """注册默认内置工具"""
        from backend.tools.builtin import BuiltInTools
        self.builtin = BuiltInTools(self)
        self.builtin.register_all(self.tools)

    def _load_sessions(self):
        """从文件加载持久化会话"""
        session_ids = SessionPersistence.list_all()
        for sid in session_ids:
            data = SessionPersistence.load(sid)
            if data:
                session = Session(session_id=sid)
                session.memory = data.get("memory", {})
                session.virtual_fs = data.get("virtual_fs", {})
                self.sessions[sid] = session

    def _save_session(self, session: Session):
        """保存会话到文件"""
        data = {
            "session_id": session.session_id,
            "memory": session.memory,
            "virtual_fs": session.virtual_fs,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat()
        }
        SessionPersistence.save(session.session_id, data)

    def _setup_scheduler_callbacks(self):
        """设置定时任务回调"""
        async def task_callback(task):
            tool_name = task["tool_name"]
            tool_args = task["tool_args"]
            print(f"[定时任务] 执行: {task['name']} -> {tool_name}")
            # 使用第一个会话执行
            if self.sessions:
                session = list(self.sessions.values())[0]
                result = await self._execute_tool(tool_name, tool_args, session)
                print(f"[定时任务] 结果: {result}")

        for task_id in self.scheduler._tasks:
            self.scheduler.register_callback(task_id, task_callback)

    def _setup_heartbeat(self):
        """设置心跳监控"""
        async def heartbeat_callback(status):
            # 可以在这里添加主动报告逻辑
            pass
        self.heartbeat.on_beat(heartbeat_callback)

    def create_session(self, session_id: str = None) -> Session:
        """创建新会话"""
        sid = session_id or str(uuid.uuid4())
        session = Session(session_id=sid)
        self.sessions[sid] = session
        self._save_session(session)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            SessionPersistence.delete(session_id)

    async def process(self, user_input: str, session_id: str = None) -> dict:
        """处理用户输入的主流程"""
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)

        try:
            # 1. 先检查学习模式匹配
            if config.get("learning_enabled"):
                learned_response = self.learning.find_match(user_input)
                if learned_response:
                    session.add_message("user", user_input)
                    session.add_message("assistant", learned_response)
                    self._save_session(session)
                    return {
                        "reply": learned_response + "\n\n[来自学习模式]",
                        "tool_calls": [],
                        "session_id": session.session_id,
                        "error": None
                    }

            # 2. 构建对话上下文
            messages = session.get_recent_messages(10)
            messages.append({"role": "user", "content": user_input})

            # 3. LLM 决策
            tool_defs = self.tools.get_tool_definitions()
            response = await self.llm.chat(messages, tools=tool_defs if tool_defs else None)

            # 4. 处理响应
            if response["type"] == "tool_calls" and response["tool_calls"]:
                return await self._handle_tool_calls(
                    session, user_input, response["tool_calls"]
                )
            else:
                return await self._handle_text_response(
                    session, user_input, response["content"]
                )

        except Exception as e:
            session.add_message("assistant", f"处理出错: {str(e)}")
            self._save_session(session)
            return {
                "reply": f"处理出错: {str(e)}",
                "tool_calls": [],
                "session_id": session.session_id,
                "error": str(e)
            }

    async def _handle_tool_calls(self, session: Session, user_input: str,
                                  tool_calls: List[dict]) -> dict:
        """处理 LLM 的工具调用请求"""
        results = []
        executed = []

        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["arguments"]
            tool_id = tc.get("id", "call_" + tool_name)

            print(f"调用工具: {tool_name}")
            print(f"   参数: {json.dumps(tool_args, ensure_ascii=False)}")

            result = await self._execute_tool(tool_name, tool_args, session)
            results.append({
                "tool_call_id": tool_id,
                "name": tool_name,
                "result": result
            })
            executed.append(tool_name)
            print(f"工具返回: {json.dumps(result, ensure_ascii=False)[:200]}")

        reply = self._generate_reply(results)

        session.add_message("user", user_input)
        session.add_message("assistant", reply)
        self._save_session(session)

        return {
            "reply": reply,
            "tool_calls": executed,
            "session_id": session.session_id,
            "error": None
        }

    async def _handle_text_response(self, session: Session, user_input: str,
                                     content: str) -> dict:
        """处理纯文本响应（兼容模拟模式的 JSON 工具调用）"""
        decision = self._parse_legacy_response(content)

        if decision.get("type") == "tool_call":
            tool_name = decision["tool"]
            tool_args = decision["args"]

            print(f"调用工具: {tool_name}")
            print(f"   参数: {json.dumps(tool_args, ensure_ascii=False)}")

            result = await self._execute_tool(tool_name, tool_args, session)
            print(f"工具返回: {json.dumps(result, ensure_ascii=False)[:200]}")

            reply = self._generate_reply([{
                "tool_call_id": "legacy",
                "name": tool_name,
                "result": result
            }])

            session.add_message("user", user_input)
            session.add_message("assistant", reply)
            self._save_session(session)

            return {
                "reply": reply,
                "tool_calls": [tool_name],
                "session_id": session.session_id,
                "error": None
            }
        else:
            reply = content
            session.add_message("user", user_input)
            session.add_message("assistant", reply)
            self._save_session(session)

            return {
                "reply": reply,
                "tool_calls": [],
                "session_id": session.session_id,
                "error": None
            }

    def _parse_legacy_response(self, response: str) -> Dict:
        """解析旧版模拟 LLM 的 JSON 工具调用"""
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict) and "tool" in parsed and self.tools.get(parsed["tool"]):
                return {"type": "tool_call", **parsed}
        except json.JSONDecodeError:
            pass

        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict) and "tool" in parsed and self.tools.get(parsed["tool"]):
                    return {"type": "tool_call", **parsed}
        except (json.JSONDecodeError, KeyError):
            pass

        return {"type": "text", "content": response}

    async def _execute_tool(self, tool_name: str, args: Dict, session: Session) -> Dict:
        """执行工具"""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f'工具 "{tool_name}" 未找到'}

        try:
            args_with_session = dict(args)
            args_with_session["_session"] = session
            result = tool["execute"](args_with_session)

            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _generate_reply(self, results: List[dict]) -> str:
        """基于工具结果生成自然语言回复"""
        lines = []
        for r in results:
            tool_name = r["name"]
            result = r["result"]
            reply = self._format_single_result(tool_name, result)
            lines.append(reply)
        return "\n\n".join(lines)

    def _format_single_result(self, tool_name: str, result: Dict) -> str:
        """格式化单个工具结果为自然语言"""
        if not result.get("success", True):
            return f"工具 {tool_name} 执行失败: {result.get('error', '未知错误')}"

        if tool_name == "fs_write":
            return f"文件创建成功！\n文件名: {result.get('filename')}\n大小: {result.get('size')} 字节"

        elif tool_name == "fs_read":
            content = result.get('content', '')
            return f'文件 "{result.get("filename")}" 的内容：\n\n```\n{content}\n```'

        elif tool_name == "fs_list":
            files = result.get('files', [])
            if not files:
                return "当前目录为空"
            lines = [f"当前目录文件列表（共 {result.get('count', 0)} 个）：\n"]
            for f in files:
                lines.append(f"  - {f['name']} ({f['size']} bytes)")
            return "\n".join(lines)

        elif tool_name == "fs_delete":
            return f'文件 "{result.get("filename")}" 已删除'

        elif tool_name == "web_search":
            results = result.get('results', [])
            query = result.get('query', '')
            lines = [f'"{query}" 的搜索结果：\n']
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   {r['snippet']}")
                lines.append(f"   {r.get('url', '')}\n")
            return "\n".join(lines)

        elif tool_name == "calculator":
            return f"计算结果：\n{result.get('expression')} = {result.get('result')}"

        elif tool_name == "datetime":
            return (f"当前时间：{result.get('datetime')}\n"
                    f"日期：{result.get('date')}\n"
                    f"时间：{result.get('time')}\n"
                    f"星期：{result.get('weekday')}")

        elif tool_name == "memory_store":
            return f"{result.get('message')}"

        elif tool_name == "memory_read":
            value = result.get('value')
            if value:
                return f"我记得：{result.get('key')} = {value}"
            return f"{result.get('message')}"

        elif tool_name == "weather":
            return (f"{result.get('city')} 天气：\n"
                    f"   天气状况：{result.get('condition')}\n"
                    f"   温度：{result.get('temperature')}°C\n"
                    f"   湿度：{result.get('humidity')}%\n"
                    f"   风力：{result.get('wind')}\n"
                    f"   更新时间：{result.get('update_time')}")

        elif tool_name == "help":
            return result.get('help_text', '')

        elif tool_name == "system_info":
            lines = ["系统信息：\n"]
            lines.append(f"   平台: {result.get('platform')}")
            lines.append(f"   Python: {result.get('python_version')}")
            lines.append(f"   记忆数: {result.get('memory_count')}")
            lines.append(f"   文件数: {result.get('file_count')}")
            lines.append(f"   工具数: {result.get('tool_count')}")
            lines.append(f"   LLM模式: {result.get('llm_mode')} ({result.get('model')})")
            return "\n".join(lines)

        elif tool_name == "browser_open":
            return result.get('message', f"已打开: {result.get('url', '')}")

        elif tool_name == "browser_screenshot":
            return result.get('message', f"截图: {result.get('filename', '')}")

        elif tool_name == "system_exec":
            output = result.get('stdout', '') or result.get('stderr', '')
            return f"命令执行结果：\n```\n{output}\n```"

        elif tool_name == "learn_pattern":
            return result.get('message', '学习完成')

        elif tool_name == "schedule_task":
            return result.get('message', '定时任务已创建')

        else:
            return f"工具 {tool_name} 执行完成：\n{json.dumps(result, ensure_ascii=False, indent=2)}"
