#!/bin/bash

# 检查 time.py 是否在运行
if pgrep -f "time.py" > /dev/null; then
    echo "time.py is running. Stopping it..."
    # 停止 time.py 进程
    pkill -f "time.py"
else
    echo "time.py is not running."
fi
# 等待1秒
sleep 1
# 运行 TIME 脚本
source ~/rss/rss_venv/bin/activate
nohup python3 ~/rss/time.py
deactivate