#!/bin/bash
# Mini OpenClaw 启动脚本

cd "$(dirname "$0")"

echo "🦞 Mini OpenClaw 启动器"
echo "========================"

# 检查参数
if [ "$1" = "web" ]; then
    echo "启动 Web 服务模式..."
    python backend/cli.py --server --port ${PORT:-8000}
elif [ "$1" = "cli" ]; then
    echo "启动 CLI 模式..."
    python backend/cli.py
else
    echo "用法:"
    echo "  ./start.sh web    # 启动 Web 服务"
    echo "  ./start.sh cli    # 启动命令行界面"
    echo ""
    echo "或直接:"
    echo "  python backend/cli.py --server"
    echo "  python backend/cli.py"
fi
