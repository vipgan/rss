#!/bin/bash

# 检查 rss2.py 是否在运行
if pgrep -f "rss2.py" > /dev/null; then
    echo "rss2.py is running. Stopping it..."
    # 停止 rss2.py 进程
    pkill -f "rss2.py"
else
    echo "rss2.py is not running."
fi
# 等待1秒
sleep 1
# 运行 RSS2 脚本
source ~/rss/rss_venv/bin/activate
nohup python3 ~/rss/rss2.py > /dev/null 2>&1 &
# deactivate