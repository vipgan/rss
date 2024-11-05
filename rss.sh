#!/bin/bash

# 检查 rss.py 是否在运行
if pgrep -f "rss.py" > /dev/null; then
    echo "rss.py is running. Stopping it..."
    # 停止 rss.py 进程
    pkill -f "rss.py"
else
    echo "rss.py is not running."
fi
# 等待1秒
sleep 1
# 运行 RSS 脚本
source ~/rss/rss_venv/bin/activate
python3 ~/rss/rss.py &
deactivate
