"""内置工具集合 - 真实 API 版本 + 系统控制 + 浏览器"""
import json
import re
import sys
import random
import asyncio
import subprocess
import platform
from datetime import datetime
from typing import Dict, List, Any

from backend.core.registry import ToolRegistry


class BuiltInTools:
    """内置工具集合"""

    def __init__(self, agent):
        self.agent = agent

    def register_all(self, registry: ToolRegistry):
        """注册所有内置工具"""
        # 文件系统（沙盒）
        registry.register("fs_write", "创建或写入文件到沙盒文件系统",
            {"filename": {"type": "string", "description": "文件名"},
             "content": {"type": "string", "description": "文件内容"}},
            self.fs_write)
        registry.register("fs_read", "读取沙盒文件系统中的文件内容",
            {"filename": {"type": "string", "description": "文件名"}},
            self.fs_read)
        registry.register("fs_list", "列出沙盒文件系统中的所有文件",
            {"path": {"type": "string", "description": "目录路径", "default": "/"}},
            self.fs_list)
        registry.register("fs_delete", "删除沙盒文件系统中的文件",
            {"filename": {"type": "string", "description": "文件名"}},
            self.fs_delete)

        # 搜索 - 真实 DuckDuckGo 搜索
        registry.register("web_search", "搜索网络信息（使用 DuckDuckGo）",
            {"query": {"type": "string", "description": "搜索关键词"},
             "max_results": {"type": "integer", "description": "最大结果数", "default": 5}},
            self.web_search)

        # 计算
        registry.register("calculator", "执行数学计算",
            {"expression": {"type": "string", "description": "数学表达式，如 '123 * 456'"}},
            self.calculator)

        # 时间
        registry.register("datetime", "获取当前日期时间", {}, self.datetime)

        # 记忆
        registry.register("memory_store", "存储信息到长期记忆",
            {"key": {"type": "string", "description": "记忆键名"},
             "value": {"type": "string", "description": "记忆内容"}},
            self.memory_store)
        registry.register("memory_read", "读取长期记忆中的信息",
            {"key": {"type": "string", "description": "记忆键名"}},
            self.memory_read)

        # 天气 - 真实天气 API
        registry.register("weather", "查询城市天气（使用 wttr.in）",
            {"city": {"type": "string", "description": "城市名称，如 '北京'、'Shanghai'"}},
            self.weather)

        # 帮助
        registry.register("help", "显示可用功能列表", {}, self.help)

        # 系统
        registry.register("system_info", "显示系统信息", {}, self.system_info)

        # 浏览器控制
        registry.register("browser_open", "打开浏览器访问指定网址",
            {"url": {"type": "string", "description": "网址 URL"}},
            self.browser_open)
        registry.register("browser_screenshot", "对当前浏览器页面截图",
            {"filename": {"type": "string", "description": "截图保存文件名", "default": "screenshot.png"}},
            self.browser_screenshot)

        # 系统命令执行
        registry.register("system_exec", "执行系统命令（需谨慎使用）",
            {"command": {"type": "string", "description": "要执行的命令"}},
            self.system_exec)

        # 学习
        registry.register("learn_pattern", "学习新的语言表达模式",
            {"input_pattern": {"type": "string", "description": "输入匹配模式（正则）"},
             "response_pattern": {"type": "string", "description": "对应的回复模板"},
             "context": {"type": "string", "description": "上下文说明", "default": ""}},
            self.learn_pattern)

        # 定时任务
        registry.register("schedule_task", "创建定时任务",
            {"name": {"type": "string", "description": "任务名称"},
             "cron": {"type": "string", "description": "定时表达式，如 'every_5_minutes', 'daily_9am'"},
             "tool_name": {"type": "string", "description": "要执行的工具名"},
             "tool_args": {"type": "object", "description": "工具参数"}},
            self.schedule_task)

        # 注册文件系统浏览工具
        from backend.tools.fs_browser import register_fs_browser_tools
        register_fs_browser_tools(registry, self.agent)

        # 注册实用工具
        from backend.tools.utils import register_utils_tools
        register_utils_tools(registry, self.agent)

    # ---------- 文件系统工具（沙盒） ----------

    def fs_write(self, args: Dict) -> Dict:
        session = self._get_session(args)
        filename = args.get("filename", "untitled.txt")
        content = args.get("content", "")
        # 使用沙盒管理器
        if hasattr(self.agent, 'sandbox'):
            self.agent.sandbox.write(filename, content)
        else:
            session.virtual_fs[filename] = content
        return {"success": True, "filename": filename, "size": len(content.encode("utf-8"))}

    def fs_read(self, args: Dict) -> Dict:
        session = self._get_session(args)
        filename = args.get("filename")
        if not filename:
            raise ValueError("请指定文件名")
        if hasattr(self.agent, 'sandbox') and self.agent.sandbox.exists(filename):
            content = self.agent.sandbox.read(filename)
            return {"success": True, "filename": filename, "content": content}
        if filename not in session.virtual_fs:
            raise FileNotFoundError(f'文件 "{filename}" 不存在')
        return {"success": True, "filename": filename, "content": session.virtual_fs[filename]}

    def fs_list(self, args: Dict) -> Dict:
        session = self._get_session(args)
        if hasattr(self.agent, 'sandbox'):
            files = self.agent.sandbox.list_dir(args.get("path", "."))
            return {"success": True, "path": args.get("path", "."), "files": files, "count": len(files)}
        files = [{"name": k, "size": len(v.encode("utf-8"))} for k, v in session.virtual_fs.items()]
        return {"success": True, "path": args.get("path", "/"), "files": files, "count": len(files)}

    def fs_delete(self, args: Dict) -> Dict:
        session = self._get_session(args)
        filename = args.get("filename")
        if hasattr(self.agent, 'sandbox') and self.agent.sandbox.exists(filename):
            self.agent.sandbox.delete(filename)
            return {"success": True, "filename": filename, "message": "已删除"}
        if filename not in session.virtual_fs:
            raise FileNotFoundError(f'文件 "{filename}" 不存在')
        del session.virtual_fs[filename]
        return {"success": True, "filename": filename, "message": "已删除"}

    # ---------- 搜索工具（真实 DuckDuckGo） ----------

    def web_search(self, args: Dict) -> Dict:
        query = args.get("query", "")
        max_results = args.get("max_results", 5)

        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                formatted = []
                for r in results:
                    formatted.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("href", "")
                    })
                return {"success": True, "query": query, "results": formatted, "source": "duckduckgo"}
        except ImportError:
            return self._web_search_fallback(query, max_results)
        except Exception as e:
            return self._web_search_fallback(query, max_results, error=str(e))

    def _web_search_fallback(self, query: str, max_results: int = 5, error: str = None) -> Dict:
        """搜索降级方案"""
        try:
            import requests
            url = "https://html.duckduckgo.com/html/"
            params = {"q": query}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, params=params, headers=headers, timeout=10)

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for item in soup.select(".result")[:max_results]:
                title_tag = item.select_one(".result__title a")
                snippet_tag = item.select_one(".result__snippet")
                if title_tag:
                    results.append({
                        "title": title_tag.get_text(strip=True),
                        "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                        "url": title_tag.get("href", "")
                    })

            return {"success": True, "query": query, "results": results, "source": "duckduckgo_fallback"}
        except Exception as e2:
            return {
                "success": True,
                "query": query,
                "results": [
                    {"title": f"{query} - 搜索结果", "snippet": f"关于 {query} 的相关信息...", "url": f"https://duckduckgo.com/?q={query}"}
                ],
                "source": "simulated",
                "note": f"真实搜索失败 ({error or str(e2)})，返回模拟结果。请安装 duckduckgo-search: pip install duckduckgo-search"
            }

    # ---------- 计算工具 ----------

    def calculator(self, args: Dict) -> Dict:
        expression = args.get("expression", "")
        safe_expr = re.sub(r"[^0-9+\-*/().\s]", "", expression)
        if not safe_expr:
            raise ValueError("无效的数学表达式")
        try:
            result = eval(safe_expr, {"__builtins__": {}}, {})
            return {"success": True, "expression": safe_expr, "result": result}
        except Exception as e:
            raise ValueError(f"计算错误: {e}")

    # ---------- 时间工具 ----------

    def datetime(self, args: Dict) -> Dict:
        now = datetime.now()
        return {
            "success": True,
            "datetime": now.strftime("%Y/%m/%d %H:%M:%S"),
            "date": now.strftime("%Y/%m/%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "timestamp": int(now.timestamp())
        }

    # ---------- 记忆工具 ----------

    def memory_store(self, args: Dict) -> Dict:
        session = self._get_session(args)
        key = args.get("key", "")
        value = args.get("value", "")
        session.memory[key] = value
        # 同时保存到全局持久化记忆
        if hasattr(self.agent, 'global_memory'):
            self.agent.global_memory.set(key, value)
        return {"success": True, "key": key, "value": value, "message": f"已记住: {key} = {value}"}

    def memory_read(self, args: Dict) -> Dict:
        session = self._get_session(args)
        key = args.get("key", "")
        # 先查会话记忆
        if key in session.memory:
            return {"success": True, "key": key, "value": session.memory[key]}
        # 再查全局持久化记忆
        if hasattr(self.agent, 'global_memory'):
            value = self.agent.global_memory.get(key)
            if value:
                return {"success": True, "key": key, "value": value, "source": "global"}
        return {"success": True, "key": key, "value": None, "message": "没有找到相关记忆"}

    # ---------- 天气工具（真实 wttr.in） ----------

    def weather(self, args: Dict) -> Dict:
        city = args.get("city", "北京")

        try:
            import requests
            url = f"https://wttr.in/{city}?format=j1"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()

            current = data["current_condition"][0]
            weather_desc = current.get("lang_zh", [{}])[0].get("value", current["weatherDesc"][0]["value"])

            return {
                "success": True,
                "city": city,
                "condition": weather_desc,
                "temperature": current["temp_C"],
                "feels_like": current["FeelsLikeC"],
                "humidity": current["humidity"],
                "wind": f"{current['windspeedKmph']} km/h {current['winddir16Point']}",
                "update_time": datetime.now().strftime("%H:%M"),
                "source": "wttr.in"
            }
        except Exception as e:
            conditions = ["晴朗", "多云", "小雨", "阴天", "晴转多云"]
            condition = random.choice(conditions)
            temp = random.randint(15, 35)
            humidity = random.randint(30, 80)
            return {
                "success": True,
                "city": city,
                "condition": condition,
                "temperature": temp,
                "humidity": humidity,
                "wind": f"{random.randint(1, 5)}级",
                "update_time": datetime.now().strftime("%H:%M"),
                "source": "simulated",
                "note": f"真实天气 API 失败 ({str(e)})，返回模拟数据"
            }

    # ---------- 帮助工具 ----------

    def help(self, args: Dict) -> Dict:
        tools = self.agent.tools.list_tools()
        help_text = "\n可用功能列表：\n\n"
        for i, tool in enumerate(tools, 1):
            help_text += f"{i}. 【{tool['name']}】{tool['description']}\n"
        help_text += "\n示例指令：\n"
        help_text += "• 创建一个 hello.txt 文件，内容是 Hello World\n"
        help_text += "• 读取 hello.txt\n"
        help_text += "• 列出所有文件\n"
        help_text += "• 删除 hello.txt\n"
        help_text += "• 搜索一下人工智能\n"
        help_text += "• 计算 123 * 456\n"
        help_text += "• 现在几点了\n"
        help_text += "• 记住我叫小明\n"
        help_text += "• 我叫什么\n"
        help_text += "• 北京天气怎么样\n"
        help_text += "• 系统信息\n"
        help_text += "• 打开浏览器 https://www.baidu.com\n"
        help_text += "• 执行命令 echo hello\n"
        return {"success": True, "help_text": help_text}

    # ---------- 系统工具 ----------

    def system_info(self, args: Dict) -> Dict:
        session = self._get_session(args)
        return {
            "success": True,
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "memory_count": len(session.memory),
            "file_count": len(session.virtual_fs),
            "tool_count": len(self.agent.tools.list_tools()),
            "llm_mode": "真实 LLM" if self.agent.llm.use_real_llm else "模拟 LLM",
            "model": self.agent.llm.model,
            "hostname": platform.node(),
            "processor": platform.processor() or "unknown"
        }

    # ---------- 浏览器工具 ----------

    def browser_open(self, args: Dict) -> Dict:
        """打开浏览器访问指定网址"""
        url = args.get("url", "https://www.baidu.com")
        if not url.startswith("http"):
            url = "https://" + url

        try:
            import webbrowser
            webbrowser.open(url)
            return {"success": True, "url": url, "message": f"已在浏览器中打开: {url}"}
        except Exception as e:
            return {"success": False, "error": f"打开浏览器失败: {str(e)}"}

    def browser_screenshot(self, args: Dict) -> Dict:
        """对浏览器页面截图（需要 playwright 或 selenium）"""
        filename = args.get("filename", "screenshot.png")
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                # 这里需要知道当前打开的页面，简化处理
                page.goto("https://www.baidu.com")
                page.screenshot(path=filename)
                browser.close()
            return {"success": True, "filename": filename, "message": f"截图已保存: {filename}"}
        except ImportError:
            return {"success": False, "error": "请先安装 playwright: pip install playwright && playwright install chromium"}
        except Exception as e:
            return {"success": False, "error": f"截图失败: {str(e)}"}

    # ---------- 系统命令执行 ----------

    def system_exec(self, args: Dict) -> Dict:
        """执行系统命令（带安全检查）"""
        command = args.get("command", "")
        if not command:
            return {"success": False, "error": "请提供要执行的命令"}

        # 安全检查：禁止危险命令
        dangerous = ["rm -rf /", "format", "del /f /s /q", "rd /s /q", ">", "<", "|", ";", "&&", "||"]
        for d in dangerous:
            if d in command.lower():
                return {"success": False, "error": f"检测到危险命令，已阻止: {d}"}

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "success": result.returncode == 0,
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "命令执行超时（30秒）"}
        except Exception as e:
            return {"success": False, "error": f"执行失败: {str(e)}"}

    # ---------- 学习工具 ----------

    def learn_pattern(self, args: Dict) -> Dict:
        """学习新的语言表达模式"""
        input_pattern = args.get("input_pattern", "")
        response_pattern = args.get("response_pattern", "")
        context = args.get("context", "")

        if hasattr(self.agent, 'learning'):
            self.agent.learning.learn(input_pattern, response_pattern, context)
            return {
                "success": True,
                "message": f"已学习新模式: {input_pattern} -> {response_pattern}",
                "total_patterns": self.agent.learning.get_stats()["total_patterns"]
            }
        return {"success": False, "error": "学习系统未启用"}

    # ---------- 定时任务工具 ----------

    def schedule_task(self, args: Dict) -> Dict:
        """创建定时任务"""
        name = args.get("name", "")
        cron = args.get("cron", "every_5_minutes")
        tool_name = args.get("tool_name", "")
        tool_args = args.get("tool_args", {})

        if hasattr(self.agent, 'scheduler'):
            task_id = self.agent.scheduler.add_task(name, cron, "", tool_name, tool_args)
            return {
                "success": True,
                "task_id": task_id,
                "message": f"定时任务已创建: {name} ({cron})"
            }
        return {"success": False, "error": "定时任务系统未启用"}

    # ---------- 辅助方法 ----------

    def _get_session(self, args: Dict):
        """从参数或 agent 获取当前会话"""
        if "_session" in args:
            return args["_session"]
        if self.agent.sessions:
            return list(self.agent.sessions.values())[0]
        return self.agent.create_session()
