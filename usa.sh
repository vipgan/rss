#!/bin/bash

# 检查 usa.py 是否在运行
if pgrep -f "usa.py" > /dev/null; then
    echo "usa.py is running. Stopping it..."
    # 停止 usa.py 进程
    pkill -f "usa.py"
else
    echo "usa.py is not running."
fi
# 等待1秒
sleep 1
# 运行 USA 脚本
source ~/rss/rss_venv/bin/activate
nohup python3 ~/rss/usa.py > /dev/null 2>&1 &
# deactivate