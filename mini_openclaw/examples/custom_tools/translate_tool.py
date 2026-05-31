"""自定义工具示例：翻译工具

将此文件放入自定义工具目录，Agent 启动时会自动加载。

使用方法：
    1. 环境变量: OPENCLAW_CUSTOM_TOOLS=/path/to/custom_tools
    2. 命令行: --custom-tools /path/to/custom_tools
    3. 启动后，Agent 会自动扫描该目录下的 .py 文件
"""

# 方式一：使用装饰器（推荐）
from backend.core.registry import tool

@tool(
    name="translate",
    description="将文本翻译成指定语言",
    parameters={
        "text": {"type": "string", "description": "要翻译的文本"},
        "target_lang": {"type": "string", "description": "目标语言，如 'en', 'zh', 'ja'", "default": "en"}
    },
    required=["text"]
)
def translate_tool(args: dict) -> dict:
    """翻译工具 - 使用免费的 MyMemory API"""
    text = args.get("text", "")
    target = args.get("target_lang", "en")

    if not text:
        return {"success": False, "error": "请提供要翻译的文本"}

    try:
        import requests
        url = "https://api.mymemory.translated.net/get"
        params = {
            "q": text,
            "langpair": f"auto|{target}"
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if data.get("responseStatus") == 200:
            return {
                "success": True,
                "original": text,
                "translated": data["responseData"]["translatedText"],
                "target_lang": target,
                "source": "mymemory"
            }
        else:
            return {"success": False, "error": f"翻译服务错误: {data.get('responseDetails', '未知错误')}"}
    except Exception as e:
        return {"success": False, "error": f"翻译失败: {str(e)}"}


# 方式二：使用 register_tools 函数
# 如果模块中有 register_tools 函数，会自动传入 registry 调用
# def register_tools(registry):
#     registry.register("translate2", "另一种翻译", {...}, translate_func)
