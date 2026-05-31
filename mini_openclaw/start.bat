@echo off
chcp 65001 >nul
echo 🦞 Mini OpenClaw 启动器
echo ========================

if "%1"=="web" (
    echo 启动 Web 服务模式...
    python backend\cli.py --server --port %PORT%
) else if "%1"=="cli" (
    echo 启动 CLI 模式...
    python backend\cli.py
) else (
    echo 用法:
    echo   start.bat web    启动 Web 服务
    echo   start.bat cli    启动命令行界面
    echo.
    echo 或直接:
    echo   python backend\cli.py --server
    echo   python backend\cli.py
)
