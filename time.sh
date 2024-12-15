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
nohup python3 ~/rss/time.py > /dev/null 2>&1 &
# 这里的 deactivate 可能不会被执行，因为 nohup 让 time.py 在后台运行
# deactivate
