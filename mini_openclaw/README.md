# 🦞 Mini OpenClaw Dashboard

一个功能完整的 AI Agent 仪表盘框架，支持持久化记忆、沙盒隔离、系统控制、浏览器操作、语言表达学习、定时任务和主动心跳监控。

## 核心特性

| 特性 | 说明 |
|------|------|
| **真实 LLM API** | 支持 OpenAI 兼容 API，可获取模型列表 |
| **持久化记忆** | 会话和全局记忆自动保存到文件 |
| **沙盒文件隔离** | 文件操作限制在沙盒目录内，防止越界 |
| **系统控制** | 执行系统命令（带安全检查） |
| **浏览器控制** | 打开浏览器、页面截图 |
| **语言表达学习** | 自动学习用户表达模式，提升回复质量 |
| **定时任务** | 支持 cron 表达式，自动执行工具 |
| **主动心跳** | 实时监控系统状态（CPU/内存/磁盘） |
| **Web 仪表盘** | 现代化管理界面，支持配置实时修改 |
| **自定义工具** | Python 装饰器快速扩展 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 Web 仪表盘
python backend/cli.py --server --port 8000

# 3. 打开浏览器访问 http://localhost:8000
```

## 项目结构

```
mini_openclaw/
├── backend/
│   ├── core/
│   │   ├── models.py          # 数据模型
│   │   ├── registry.py        # 工具注册表 + @tool 装饰器
│   │   ├── llm.py             # LLM 客户端（支持模型列表）
│   │   ├── agent.py           # 核心 Agent（多会话/持久化/学习）
│   │   ├── config.py          # 配置管理（Web可修改）
│   │   ├── persistence.py     # 持久化（会话/记忆/学习/沙盒）
│   │   ├── scheduler.py       # 定时任务调度器
│   │   └── heartbeat.py       # 主动心跳监控
│   ├── tools/
│   │   └── builtin.py         # 内置工具（系统/浏览器/学习/定时任务）
│   ├── api_server.py          # FastAPI Web 服务 + WebSocket
│   └── cli.py                 # CLI 入口
├── web/
│   └── static/
│       └── index.html         # 仪表盘界面
├── examples/
│   └── custom_tools/          # 自定义工具示例
├── data/                      # 数据目录（自动创建）
│   ├── sessions/              # 会话持久化
│   ├── memory/                # 全局记忆 + 学习数据
│   ├── config/                # 配置文件 + 定时任务
│   └── sandbox/               # 沙盒文件系统
└── requirements.txt
```

## 仪表盘页面

| 页面 | 功能 |
|------|------|
| **仪表盘** | 系统状态概览、实时资源监控、定时任务列表 |
| **对话** | 多会话聊天界面 |
| **会话** | 会话管理（查看/删除） |
| **工具** | 已注册工具列表 |
| **沙盒** | 沙盒文件系统浏览 |
| **定时任务** | 创建/启用/禁用/删除定时任务 |
| **配置** | LLM配置（支持获取模型列表）、系统开关、功能启用 |

## 配置方式

### 1. Web 仪表盘配置（推荐）

访问 `http://localhost:8000` -> 配置页面
- 输入 API Key 和 Base URL
- 点击"获取可用模型"自动拉取模型列表
- 实时切换功能开关

### 2. 环境变量

```bash
export OPENCLAW_API_KEY="your-key"
export OPENCLAW_BASE_URL="https://api.openai.com/v1"
export OPENCLAW_MODEL="gpt-3.5-turbo"
```

### 3. 命令行参数

```bash
python backend/cli.py -k your-key -u https://api.openai.com/v1
```

## 新增工具

| 工具名 | 描述 |
|--------|------|
| `browser_open` | 打开浏览器访问指定网址 |
| `browser_screenshot` | 浏览器页面截图 |
| `system_exec` | 执行系统命令（带安全检查） |
| `learn_pattern` | 学习语言表达模式 |
| `schedule_task` | 创建定时任务 |

## 定时任务表达式

| 表达式 | 说明 |
|--------|------|
| `every_minute` | 每分钟 |
| `every_5_minutes` | 每5分钟 |
| `every_hour` | 每小时 |
| `daily` | 每天 |
| `daily_9am` | 每天上午9点 |
| `0 */6 * * *` | 标准 cron 表达式（每6小时） |

## 自定义工具

```python
from backend.core.registry import tool

@tool(name="my_tool", description="我的工具", parameters={"arg": {"type": "string"}})
def my_tool_func(args: dict) -> dict:
    return {"success": True, "result": args["arg"]}
```

将文件放入自定义工具目录，自动加载。
