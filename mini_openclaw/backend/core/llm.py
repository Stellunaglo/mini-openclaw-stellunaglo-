"""LLM 客户端 - 支持真实 API、模拟模式和模型列表获取"""
import json
import os
import re
from typing import Dict, List, Any, Optional


class LLMClient:
    """LLM 客户端 - 支持多种 API 格式（OpenAI 兼容）"""

    def __init__(self, api_key: str = "", base_url: str = "", model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.model = model
        self.use_real_llm = bool(api_key)
        self._client = None
        self._init_client()

    def _init_client(self):
        """初始化 OpenAI 兼容客户端"""
        if not self.use_real_llm:
            return
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        except ImportError:
            print("[LLM] 未安装 openai 包，尝试使用 HTTP 请求")
            self._client = None

    async def list_models(self) -> List[dict]:
        """获取可用模型列表"""
        if not self.use_real_llm:
            return []
        try:
            if self._client:
                response = await self._client.models.list()
                return [{"id": m.id, "object": m.object} for m in response.data]
            else:
                return await self._list_models_http()
        except Exception as e:
            print(f"[LLM] 获取模型列表失败: {e}")
            return []

    async def _list_models_http(self) -> List[dict]:
        """使用 aiohttp 获取模型列表"""
        import aiohttp
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"API 错误 {resp.status}")
                return data.get("data", [])

    async def chat(self, messages: List[Dict[str, str]], tools: List[dict] = None,
                   tools_desc: str = "") -> dict:
        """调用 LLM，返回结构化结果

        返回格式:
            {
                "type": "text" | "tool_calls",
                "content": str,
                "tool_calls": [
                    {"id": str, "name": str, "arguments": dict}
                ]
            }
        """
        if self.use_real_llm:
            return await self._call_api(messages, tools)
        else:
            text = self._simulate_llm(messages[-1]["content"] if messages else "")
            return {"type": "text", "content": text, "tool_calls": []}

    async def _call_api(self, messages: List[Dict[str, str]], tools: List[dict]) -> dict:
        """调用真实 LLM API（OpenAI 兼容格式）"""
        system_msg = {"role": "system", "content": "你是一个 AI Agent，可以使用工具帮助用户解决问题。"}
        full_messages = [system_msg] + messages

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": 0.3,
            "max_tokens": 2000
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            if self._client:
                response = await self._client.chat.completions.create(**payload)
                msg = response.choices[0].message

                if msg.tool_calls:
                    return {
                        "type": "tool_calls",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "name": tc.function.name,
                                "arguments": json.loads(tc.function.arguments)
                            }
                            for tc in msg.tool_calls
                        ]
                    }
                return {"type": "text", "content": msg.content or "", "tool_calls": []}
            else:
                return await self._call_api_http(payload)
        except Exception as e:
            print(f"  [警告] API 调用失败: {e}，切换到模拟模式")
            text = self._simulate_llm(messages[-1]["content"] if messages else "")
            return {"type": "text", "content": text, "tool_calls": []}

    async def _call_api_http(self, payload: dict) -> dict:
        """使用 aiohttp 发送 HTTP 请求"""
        import aiohttp
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"API 错误 {resp.status}: {data}")

                msg = data["choices"][0]["message"]
                if msg.get("tool_calls"):
                    return {
                        "type": "tool_calls",
                        "content": msg.get("content", ""),
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "name": tc["function"]["name"],
                                "arguments": json.loads(tc["function"]["arguments"])
                            }
                            for tc in msg["tool_calls"]
                        ]
                    }
                return {"type": "text", "content": msg.get("content", ""), "tool_calls": []}

    def _simulate_llm(self, user_input: str) -> str:
        """模拟 LLM 决策 - 本地规则匹配（降级方案）"""
        inp = user_input.lower()
        q = chr(39)
        d = chr(34)

        if re.search(r"删除|删掉", inp):
            m = re.search(r'[' + d + q + r']?([\w\-\.]+\.\w+)[' + d + q + r']?', user_input)
            filename = m.group(1) if m else None
            return json.dumps({"tool": "fs_delete", "args": {"filename": filename}})

        if re.search(r"创建|新建|写|保存.*文件", inp):
            m = re.search(r'[' + d + q + r']?([\w\-\.]+\.\w+)[' + d + q + r']?', user_input)
            filename = m.group(1) if m else "untitled.txt"
            m2 = re.search(r"内容[是为:：][\s]*[" + d + q + r"]?(.+?)[" + d + q + r"]?$", user_input)
            content = m2.group(1) if m2 else "Hello World"
            return json.dumps({"tool": "fs_write", "args": {"filename": filename, "content": content}})

        if re.search(r"读取|打开|查看.*文件", inp):
            m = re.search(r'[' + d + q + r']?([\w\-\.]+\.\w+)[' + d + q + r']?', user_input)
            filename = m.group(1) if m else None
            return json.dumps({"tool": "fs_read", "args": {"filename": filename}})

        if re.search(r"列出|查看.*目录|文件.*列表", inp):
            return json.dumps({"tool": "fs_list", "args": {"path": "/"}})

        if re.search(r"搜索|查找|查一下|搜一下", inp):
            query = re.sub(r".*?搜索|.*?查找|.*?查一下|.*?搜一下", "", user_input).strip()
            query = re.sub(r"^[一下点些个的\s]+", "", query).strip()
            return json.dumps({"tool": "web_search", "args": {"query": query or user_input}})

        if re.search(r"计算|等于|多少", inp) or re.search(r"\d+[\+\-\*/]\d+", inp):
            m = re.search(r"[\d\s\+\-\*/()\.]+", user_input)
            expr = m.group(0) if m else user_input
            return json.dumps({"tool": "calculator", "args": {"expression": expr}})

        if re.search(r"时间|几点|日期|今天|现在", inp):
            return json.dumps({"tool": "datetime", "args": {}})

        if re.search(r"我叫什么|我是谁|我的名字|记住.*什么", inp):
            return json.dumps({"tool": "memory_read", "args": {"key": "user_name"}})

        if re.search(r"记住|我叫", inp):
            m = re.search(r"我叫\s*(\S+)", user_input)
            if m:
                return json.dumps({"tool": "memory_store", "args": {"key": "user_name", "value": m.group(1)}})
            info = re.sub(r".*记住", "", user_input).strip()
            return json.dumps({"tool": "memory_store", "args": {"key": "user_info", "value": info}})

        if re.search(r"天气|气温|下雨", inp):
            m = re.search(r"(.+?)的?天气", user_input)
            city = m.group(1) if m else "北京"
            return json.dumps({"tool": "weather", "args": {"city": city}})

        if re.search(r"帮助|help|功能|能做什么", inp):
            return json.dumps({"tool": "help", "args": {}})

        if re.search(r"系统信息|系统状态", inp):
            return json.dumps({"tool": "system_info", "args": {}})

        if re.search(r"打开浏览器|访问网站|浏览网页", inp):
            m = re.search(r"(https?://\S+|\w+\.\w+\.\w+)", user_input)
            url = m.group(1) if m else "https://www.baidu.com"
            return json.dumps({"tool": "browser_open", "args": {"url": url}})

        if re.search(r"执行命令|运行程序|打开应用", inp):
            m = re.search(r"运行\s+(.+)", user_input)
            cmd = m.group(1) if m else "echo hello"
            return json.dumps({"tool": "system_exec", "args": {"command": cmd}})

        return (f'我理解你的需求是："{user_input}"。目前我没有找到合适的工具来处理这个请求，'
                f'但我可以陪你聊天！\n\n你可以尝试以下功能：\n'
                f'• 创建/读取/列出/删除文件\n• 搜索信息\n• 数学计算\n'
                f'• 查询时间/天气\n• 记忆存储\n• 浏览器操作\n• 系统命令')
