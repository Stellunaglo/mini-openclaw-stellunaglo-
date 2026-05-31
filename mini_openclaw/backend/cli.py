"""命令行交互界面"""
import os
import sys
import asyncio
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import MiniOpenClaw, config


class CLIInterface:
    def __init__(self, agent: MiniOpenClaw):
        self.agent = agent
        self.running = False
        self.current_session_id = None

    def print_banner(self):
        print("""
+----------------------------------------------------------+
|                                                          |
|   Mini OpenClaw Dashboard - AI Agent 框架               |
|                                                          |
|   支持: 文件操作 | 搜索 | 计算 | 时间 | 天气 | 记忆      |
|         浏览器 | 系统命令 | 学习 | 定时任务 | 心跳       |
|                                                          |
+----------------------------------------------------------+
        """)

    def print_help(self):
        print("""
使用说明：
============================================================
直接输入自然语言指令，例如：
  - 创建一个 hello.txt 文件，内容是 Hello World
  - 读取 hello.txt
  - 列出所有文件
  - 删除 hello.txt
  - 搜索一下人工智能
  - 计算 123 * 456
  - 现在几点了
  - 记住我叫小明
  - 我叫什么
  - 北京天气怎么样
  - 系统信息
  - 打开浏览器 https://www.baidu.com
  - 执行命令 echo hello
  - 学习模式: 当我问"你好"时回复"你好呀"

特殊命令：
  /help     - 显示此帮助
  /tools    - 显示已注册工具
  /files    - 显示虚拟文件系统
  /memory   - 显示记忆内容
  /clear    - 清空对话历史
  /new      - 新建会话
  /sessions - 列出所有会话
  /config   - 显示当前配置
  /quit     - 退出程序

配置方式：
  1. Web 仪表盘: http://localhost:8000 -> 配置页面
  2. 环境变量: OPENCLAW_API_KEY=xxx
  3. 命令行: --api-key xxx
============================================================
        """)

    async def run(self):
        self.print_banner()
        self.print_help()
        self.running = True

        session = self.agent.create_session()
        self.current_session_id = session.session_id
        print("[会话] 已创建新会话: " + session.session_id[:8] + "...")

        while self.running:
            try:
                prompt = "\n你 (" + self.current_session_id[:8] + ") > "
                user_input = input(prompt).strip()
                if not user_input:
                    continue
                if user_input.startswith("/"):
                    await self._handle_command(user_input)
                    continue

                result = await self.agent.process(user_input, self.current_session_id)
                if result.get("error"):
                    print("\n错误: " + result['error'])
                else:
                    print("\nAgent > " + result['reply'])
                self.current_session_id = result.get("session_id", self.current_session_id)

            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except Exception as e:
                print("\n错误: " + str(e))

    async def _handle_command(self, cmd: str):
        parts = cmd.lower().split()
        command = parts[0]

        if command == "/help":
            self.print_help()
        elif command == "/tools":
            tools = self.agent.tools.list_tools()
            print("\n已注册工具：")
            for t in tools:
                print("  - " + t['name'] + ": " + t['description'])
        elif command == "/files":
            session = self.agent.get_session(self.current_session_id)
            if not session or not session.virtual_fs:
                print("\n虚拟文件系统为空")
            else:
                print("\n虚拟文件系统：")
                for name, content in session.virtual_fs.items():
                    print("  - " + name + " (" + str(len(content.encode('utf-8'))) + " bytes)")
        elif command == "/memory":
            session = self.agent.get_session(self.current_session_id)
            if not session or not session.memory:
                print("\n会话记忆为空")
            else:
                print("\n会话记忆：")
                for k, v in session.memory.items():
                    print("  - " + k + ": " + v)
            print("\n全局记忆：")
            global_mem = self.agent.global_memory.get_all()
            if not global_mem:
                print("  (空)")
            else:
                for k, v in global_mem.items():
                    print("  - " + k + ": " + v)
        elif command == "/clear":
            session = self.agent.get_session(self.current_session_id)
            if session:
                session.messages.clear()
            print("\n对话历史已清空")
        elif command == "/new":
            session = self.agent.create_session()
            self.current_session_id = session.session_id
            print("\n已创建新会话: " + session.session_id[:8] + "...")
        elif command == "/sessions":
            print("\n会话列表：")
            for sid, s in self.agent.sessions.items():
                marker = " <- 当前" if sid == self.current_session_id else ""
                print("  - " + sid[:8] + "... (" + str(s.message_count) + " 条消息)" + marker)
        elif command == "/config":
            print("\n当前配置：")
            for k, v in config.get_all().items():
                print("  - " + k + ": " + str(v))
        elif command in ["/quit", "/exit", "/q"]:
            print("\n再见！")
            self.running = False
        else:
            print("\n未知命令: " + cmd + "，输入 /help 查看帮助")


def main():
    parser = argparse.ArgumentParser(description="Mini OpenClaw Dashboard")
    parser.add_argument("--api-key", "-k", default="", help="LLM API Key")
    parser.add_argument("--base-url", "-u", default="", help="API 基础地址")
    parser.add_argument("--model", "-m", default="", help="模型名称")
    parser.add_argument("--custom-tools", "-t", default="", help="自定义工具目录")
    parser.add_argument("--server", "-s", action="store_true", help="启动 Web 服务")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Web 服务端口")

    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENCLAW_API_KEY", "")
    base_url = args.base_url or os.environ.get("OPENCLAW_BASE_URL", "")
    model = args.model or os.environ.get("OPENCLAW_MODEL", "")
    custom_tools = args.custom_tools or os.environ.get("OPENCLAW_CUSTOM_TOOLS", "")

    if args.server:
        os.environ["OPENCLAW_API_KEY"] = api_key
        os.environ["OPENCLAW_BASE_URL"] = base_url
        os.environ["OPENCLAW_MODEL"] = model
        os.environ["OPENCLAW_CUSTOM_TOOLS"] = custom_tools
        import uvicorn
        from backend.api_server import app
        print("启动 Dashboard: http://0.0.0.0:" + str(args.port))
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        agent = MiniOpenClaw(
            api_key=api_key,
            base_url=base_url,
            model=model,
            custom_tools_dir=custom_tools
        )
        cli = CLIInterface(agent)
        try:
            asyncio.run(cli.run())
        except KeyboardInterrupt:
            print("\n\n再见！")


if __name__ == "__main__":
    main()
