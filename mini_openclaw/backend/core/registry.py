"""工具注册表 - 支持自定义工具加载"""
import json
import os
import sys
import importlib.util
import inspect
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from .models import ToolDefinition


class ToolRegistry:
    """工具注册表 - 类似 OpenClaw 的插件系统"""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._custom_tool_paths: List[str] = []

    def register(self, name: str, description: str, parameters: Dict[str, Any],
                 execute: Callable, required: List[str] = None):
        """注册工具"""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required or list(parameters.keys())
            },
            "execute": execute
        }
        return self

    def get(self, name: str) -> Optional[Dict]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict]:
        return list(self._tools.values())

    def get_tool_definitions(self) -> List[dict]:
        """获取 OpenAI function calling 格式的工具定义列表"""
        defs = []
        for tool in self._tools.values():
            td = ToolDefinition(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"]["properties"],
                required=tool["parameters"]["required"]
            )
            defs.append(td.to_openai_format())
        return defs

    def get_descriptions(self) -> str:
        """生成给 LLM 的文本工具说明书（备用）"""
        desc = "你可以使用以下工具：\n\n"
        for tool in self._tools.values():
            desc += f"【{tool['name']}】{tool['description']}\n"
            params = tool["parameters"]["properties"]
            if params:
                desc += f"参数: {json.dumps(params, ensure_ascii=False)}\n"
            desc += "\n"
        desc += "\n当你需要调用工具时，请严格按以下 JSON 格式输出：\n"
        desc += '{"tool": "工具名", "args": {"参数名": "参数值"}}\n'
        desc += "如果不需要工具，直接回复用户即可。"
        return desc

    # ========== 自定义工具加载 ==========

    def load_custom_tools(self, directory: str):
        """从目录加载自定义 Python 工具模块"""
        path = Path(directory)
        if not path.exists():
            print(f"[注册表] 自定义工具目录不存在: {directory}")
            return

        self._custom_tool_paths.append(str(path.absolute()))

        for py_file in path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                self._load_module(py_file)
                print(f"[注册表] 已加载自定义工具模块: {py_file.name}")
            except Exception as e:
                print(f"[注册表] 加载失败 {py_file.name}: {e}")

    def _load_module(self, file_path: Path):
        """动态加载单个 Python 模块"""
        module_name = f"custom_tool_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # 查找模块中的 register 函数
        if hasattr(module, "register_tools"):
            module.register_tools(self)
        else:
            # 自动扫描所有函数
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("_"):
                    continue
                # 检查是否有工具装饰器标记
                if hasattr(obj, "_tool_meta"):
                    meta = obj._tool_meta
                    self.register(
                        name=meta["name"],
                        description=meta["description"],
                        parameters=meta["parameters"],
                        execute=obj,
                        required=meta.get("required", [])
                    )


def tool(name: str = None, description: str = "", parameters: Dict = None, required: List[str] = None):
    """工具装饰器 - 用于标记自定义工具函数

    用法示例:
        @tool(name="my_tool", description="描述", parameters={"arg": {"type": "string"}})
        def my_tool_func(args: dict) -> dict:
            return {"success": True, "result": args["arg"]}
    """
    def decorator(func):
        func_name = name or func.__name__
        func._tool_meta = {
            "name": func_name,
            "description": description or func.__doc__ or "",
            "parameters": parameters or {},
            "required": required or list((parameters or {}).keys())
        }
        return func
    return decorator
