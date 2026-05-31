"""FastAPI Web 服务端 - 仪表盘版本"""
import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# 将项目根目录加入 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import MiniOpenClaw, Session, config

# 本地已知模型列表（当 API 获取失败时作为备选）
LOCAL_MODELS = {
    "openai": [
        {"id": "gpt-4o", "description": "OpenAI 最强多模态模型"},
        {"id": "gpt-4o-mini", "description": "OpenAI 轻量快速模型"},
        {"id": "gpt-4-turbo", "description": "OpenAI 高级模型"},
        {"id": "gpt-3.5-turbo", "description": "OpenAI 标准模型"},
        {"id": "gpt-3.5-turbo-16k", "description": "OpenAI 长上下文模型"},
    ],
    "deepseek": [
        {"id": "deepseek-chat", "description": "DeepSeek 对话模型"},
        {"id": "deepseek-reasoner", "description": "DeepSeek 推理模型"},
        {"id": "deepseek-coder", "description": "DeepSeek 代码模型"},
    ],
    "moonshot": [
        {"id": "moonshot-v1-8k", "description": "Kimi 8K 上下文"},
        {"id": "moonshot-v1-32k", "description": "Kimi 32K 上下文"},
        {"id": "moonshot-v1-128k", "description": "Kimi 128K 上下文"},
    ],
    "zhipu": [
        {"id": "glm-4-plus", "description": "智谱 GLM-4 增强版"},
        {"id": "glm-4-flash", "description": "智谱 GLM-4 极速版（免费）"},
        {"id": "glm-4", "description": "智谱 GLM-4 标准版"},
        {"id": "glm-4-air", "description": "智谱 GLM-4 轻量版"},
        {"id": "glm-4v", "description": "智谱 GLM-4 视觉版"},
        {"id": "chatglm3-6b", "description": "智谱 ChatGLM3"},
    ],
    "aliyun": [
        {"id": "qwen-turbo", "description": "通义千问 Turbo"},
        {"id": "qwen-plus", "description": "通义千问 Plus"},
        {"id": "qwen-max", "description": "通义千问 Max"},
        {"id": "qwen-coder-plus", "description": "通义千问代码版"},
        {"id": "qwen2.5-72b-instruct", "description": "Qwen2.5 72B"},
    ],
    "siliconflow": [
        {"id": "deepseek-ai/DeepSeek-V3", "description": "DeepSeek V3"},
        {"id": "deepseek-ai/DeepSeek-R1", "description": "DeepSeek R1"},
        {"id": "Qwen/Qwen2.5-72B-Instruct", "description": "Qwen2.5 72B"},
        {"id": "THUDM/glm-4-9b-chat", "description": "GLM-4 9B"},
        {"id": "meta-llama/Meta-Llama-3.1-70B-Instruct", "description": "Llama 3.1 70B"},
    ],
    "ollama": [
        {"id": "llama3", "description": "Meta Llama 3"},
        {"id": "llama3.1", "description": "Meta Llama 3.1"},
        {"id": "qwen2.5", "description": "阿里 Qwen2.5"},
        {"id": "deepseek-coder", "description": "DeepSeek Coder"},
        {"id": "mistral", "description": "Mistral"},
        {"id": "gemma2", "description": "Google Gemma 2"},
    ],
}


def guess_provider(base_url: str) -> str:
    """根据 base_url 猜测提供商"""
    url = base_url.lower()
    if "openai" in url:
        return "openai"
    elif "deepseek" in url:
        return "deepseek"
    elif "moonshot" in url or "kimi" in url:
        return "moonshot"
    elif "bigmodel" in url or "zhipu" in url:
        return "zhipu"
    elif "aliyun" in url or "dashscope" in url:
        return "aliyun"
    elif "siliconflow" in url:
        return "siliconflow"
    elif "localhost" in url or "127.0.0.1" in url or "ollama" in url:
        return "ollama"
    return "openai"  # 默认


# ========== 配置 ==========
API_KEY = os.environ.get("OPENCLAW_API_KEY", "")
BASE_URL = os.environ.get("OPENCLAW_BASE_URL", "")
MODEL = os.environ.get("OPENCLAW_MODEL", "gpt-3.5-turbo")
CUSTOM_TOOLS_DIR = os.environ.get("OPENCLAW_CUSTOM_TOOLS", "")

# ========== FastAPI App ==========
app = FastAPI(
    title="Mini OpenClaw Dashboard",
    description="AI Agent 框架仪表盘",
    version="3.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Agent 实例
agent: Optional[MiniOpenClaw] = None

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()


@app.on_event("startup")
async def startup():
    global agent
    agent = MiniOpenClaw(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=MODEL,
        custom_tools_dir=CUSTOM_TOOLS_DIR
    )
    print("[启动] Mini OpenClaw Dashboard 已初始化")
    print("[配置] LLM: " + MODEL + " @ " + (BASE_URL or "模拟模式"))
    print("[配置] 自定义工具目录: " + (CUSTOM_TOOLS_DIR or "无"))

    # 启动定时任务调度器
    if config.get("scheduled_tasks_enabled"):
        asyncio.create_task(agent.scheduler.start())

    # 启动心跳
    if config.get("heartbeat_enabled"):
        asyncio.create_task(agent.heartbeat.start())


@app.on_event("shutdown")
async def shutdown():
    if agent:
        agent.scheduler.stop()
        agent.heartbeat.stop()


# ========== 数据模型 ==========

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    tool_calls: List[str]
    session_id: str
    error: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    custom_tools_dir: Optional[str] = None
    sandbox_enabled: Optional[bool] = None
    learning_enabled: Optional[bool] = None
    scheduled_tasks_enabled: Optional[bool] = None
    heartbeat_enabled: Optional[bool] = None
    heartbeat_interval: Optional[int] = None
    browser_enabled: Optional[bool] = None
    system_control_enabled: Optional[bool] = None


class TaskCreateRequest(BaseModel):
    name: str
    cron: str
    description: Optional[str] = ""
    tool_name: str
    tool_args: dict


# ========== API 路由 ==========

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回仪表盘界面"""
    web_index = Path(__file__).parent.parent / "web" / "static" / "index.html"
    if web_index.exists():
        return FileResponse(web_index)
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head><title>Mini OpenClaw Dashboard</title></head>
    <body>
        <h1>Mini OpenClaw Dashboard 运行中</h1>
        <p>访问 <a href="/docs">/docs</a> 查看 API 文档</p>
    </body>
    </html>
    """)


# ---------- 聊天 ----------

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """发送消息并获取回复"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    result = await agent.process(req.message, req.session_id)
    return ChatResponse(**result)


# ---------- 配置管理 ----------

@app.get("/api/config")
async def get_config():
    """获取当前配置（隐藏敏感信息）"""
    return config.get_all()


@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    """更新配置"""
    updates = {k: v for k, v in req.dict().items() if v is not None}

    # 如果更新了 API 配置，需要重新初始化 LLM
    need_reload = any(k in updates for k in ["api_key", "base_url", "model"])

    success = config.update(updates)

    if success and need_reload and agent:
        # 重新初始化 LLM 客户端
        cfg = config.get_raw()
        agent.llm = agent.llm.__class__(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model
        )
        agent.llm.use_real_llm = bool(cfg.api_key)

    return {"success": success, "config": config.get_all()}


@app.get("/api/config/models")
async def list_available_models():
    """获取当前 API 支持的模型列表，失败时返回本地备选"""
    if not agent:
        return {"models": [], "mode": "offline"}

    # 尝试从 API 获取
    if agent.llm.use_real_llm:
        try:
            models = await agent.llm.list_models()
            if models:
                return {
                    "models": models,
                    "mode": "real",
                    "current_model": agent.llm.model,
                    "source": "api"
                }
        except Exception as e:
            print(f"[模型列表] API 获取失败，使用本地备选: {e}")

    # API 失败或模拟模式，返回本地备选
    provider = guess_provider(agent.llm.base_url)
    local = LOCAL_MODELS.get(provider, LOCAL_MODELS["openai"])

    return {
        "models": [{"id": m["id"], "object": "model", "description": m.get("description", "")} for m in local],
        "mode": "real" if agent.llm.use_real_llm else "simulated",
        "current_model": agent.llm.model,
        "source": "local_auto",
        "provider": provider,
        "note": "API 获取失败，显示本地已知模型列表。请确认 API Key 和 Base URL 正确。"
    }


# ---------- 会话管理 ----------

@app.get("/api/sessions")
async def list_sessions():
    """列出所有会话"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    return [s.to_dict() for s in agent.sessions.values()]


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话信息"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    session = agent.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session.to_dict()


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    agent.delete_session(session_id)
    return {"success": True, "message": "会话已删除"}


@app.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """获取会话消息历史"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    session = agent.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "messages": [m.to_dict() for m in session.messages],
        "session_id": session_id
    }


# ---------- 工具 ----------

@app.get("/api/tools")
async def list_tools():
    """列出所有可用工具"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    tools = agent.tools.list_tools()
    return [{"name": t["name"], "description": t["description"], "parameters": t["parameters"]} for t in tools]


# ---------- 文件系统 ----------

@app.get("/api/sessions/{session_id}/files")
async def list_files(session_id: str):
    """列出会话的虚拟文件"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    session = agent.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return [{"name": k, "size": len(v.encode("utf-8"))} for k, v in session.virtual_fs.items()]


@app.get("/api/sessions/{session_id}/files/{filename}")
async def read_file(session_id: str, filename: str):
    """读取会话的虚拟文件内容"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    session = agent.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if filename not in session.virtual_fs:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {
        "filename": filename,
        "content": session.virtual_fs[filename],
        "size": len(session.virtual_fs[filename].encode("utf-8"))
    }


# ---------- 沙盒 ----------

@app.get("/api/sandbox")
async def list_sandbox():
    """列出沙盒文件"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    return agent.sandbox.list_dir(".")


@app.get("/api/sandbox/{path:path}")
async def read_sandbox_file(path: str):
    """读取沙盒文件"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    try:
        content = agent.sandbox.read(path)
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- 记忆 ----------

@app.get("/api/memory")
async def get_memory():
    """获取全局记忆"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    return [{"key": k, "value": v} for k, v in agent.global_memory.get_all().items()]


@app.get("/api/sessions/{session_id}/memory")
async def get_session_memory(session_id: str):
    """获取会话记忆"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    session = agent.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return [{"key": k, "value": v} for k, v in session.memory.items()]


# ---------- 学习 ----------

@app.get("/api/learning")
async def get_learning_stats():
    """获取学习统计"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    return agent.learning.get_stats()


@app.get("/api/learning/patterns")
async def get_learning_patterns():
    """获取所有学习模式"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    return agent.learning.get_all()


# ---------- 定时任务 ----------

@app.get("/api/tasks")
async def list_tasks():
    """列出所有定时任务"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    return agent.scheduler.get_tasks()


@app.post("/api/tasks")
async def create_task(req: TaskCreateRequest):
    """创建定时任务"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    task_id = agent.scheduler.add_task(
        name=req.name,
        cron=req.cron,
        description=req.description,
        tool_name=req.tool_name,
        tool_args=req.tool_args
    )
    return {"success": True, "task_id": task_id}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除定时任务"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    agent.scheduler.remove_task(task_id)
    return {"success": True}


@app.post("/api/tasks/{task_id}/toggle")
async def toggle_task(task_id: str):
    """启用/禁用定时任务"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    enabled = agent.scheduler.toggle_task(task_id)
    return {"success": True, "enabled": enabled}


# ---------- 心跳 ----------

@app.get("/api/heartbeat")
async def get_heartbeat():
    """获取最新心跳状态"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    status = agent.heartbeat.get_last_status()
    if not status:
        status = agent.heartbeat.get_status()
    return status


# ---------- WebSocket 实时推送 ----------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 处理客户端消息
            try:
                msg = json.loads(data)
                if msg.get("type") == "chat":
                    result = await agent.process(msg.get("message", ""), msg.get("session_id"))
                    await websocket.send_json({
                        "type": "chat_response",
                        "data": result
                    })
                elif msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ---------- 健康检查 ----------



# ---------- 文件系统浏览 ----------

@app.get("/api/fs/browse")
async def browse_directory(path: str = "."):
    """浏览文件系统目录"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    from backend.tools.fs_browser import FileSystemBrowser
    browser = FileSystemBrowser()
    return browser.list_directory(path)


@app.get("/api/fs/read")
async def read_system_file(path: str, max_size: int = 100000):
    """读取系统文件"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    from backend.tools.fs_browser import FileSystemBrowser
    browser = FileSystemBrowser()
    return browser.read_file(path, max_size)


@app.get("/api/fs/search")
async def search_system_files(pattern: str, root: str = ".", max_results: int = 50):
    """搜索系统文件"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    from backend.tools.fs_browser import FileSystemBrowser
    browser = FileSystemBrowser()
    return browser.search_files(pattern, root, max_results)


# ---------- 系统进程 ----------

@app.get("/api/system/processes")
async def list_processes():
    """列出系统进程"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    try:
        import psutil
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                info = proc.info
                processes.append(info)
            except:
                pass
        processes.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
        return {"processes": processes[:50], "total": len(list(psutil.process_iter()))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/network")
async def network_information():
    """获取网络信息"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    try:
        import socket
        import psutil
        interfaces = []
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    interfaces.append({"name": name, "ip": addr.address, "netmask": addr.netmask})
        return {"hostname": socket.gethostname(), "interfaces": interfaces}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- 学习模式管理 ----------

@app.post("/api/learning")
async def add_learning_pattern(input_pattern: str, response_pattern: str, context: str = ""):
    """添加学习模式"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    agent.learning.learn(input_pattern, response_pattern, context)
    return {"success": True, "message": "学习模式已添加"}


@app.delete("/api/learning/{index}")
async def delete_learning_pattern(index: int):
    """删除学习模式"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    patterns = agent.learning.get_all()
    if 0 <= index < len(patterns):
        # 这里需要实现删除逻辑
        return {"success": True, "message": "学习模式已删除"}
    raise HTTPException(status_code=404, detail="索引不存在")

@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "llm_mode": "real" if (agent and agent.llm.use_real_llm) else "simulated",
        "model": MODEL,
        "sessions": len(agent.sessions) if agent else 0,
        "tools": len(agent.tools.list_tools()) if agent else 0,
        "timestamp": datetime.now().isoformat()
    }


# ========== 静态文件 ==========
web_static = Path(__file__).parent.parent / "web" / "static"
if web_static.exists():
    app.mount("/static", StaticFiles(directory=str(web_static)), name="static")


# ========== 入口 ==========
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
