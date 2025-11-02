#!/bin/bash

# Atomic Hedge Bot 启动脚本

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

echo "=========================================="
echo "  Atomic Hedge Bot"
echo "=========================================="
echo ""

# 检查.env文件
if [ ! -f "../.env" ] && [ ! -f ".env" ]; then
    echo "Warning: .env file not found"
    echo "Please create .env with required configuration"
    exit 1
fi

# 显示配置的交易所
if [ -f "../.env" ]; then
    ENV_FILE="../.env"
else
    ENV_FILE=".env"
fi

EXCHANGES=$(grep "^EXCHANGES=" "$ENV_FILE" | cut -d'=' -f2)
if [ -n "$EXCHANGES" ]; then
    echo "Configured exchanges: $EXCHANGES"
else
    echo "Configured exchanges: GRVT,Lighter (default)"
fi

echo ""
echo "Starting bot..."
echo ""

# 运行bot
python3 hedge_bot_atomic.py

# 退出状态
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "Bot exited with error code: $EXIT_CODE"
fi

exit $EXIT_CODE
