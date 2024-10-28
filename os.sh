#!/bin/bash

# 要检测的脚本名称
SCRIPT_NAME="os.py"

# 检查脚本是否在运行
is_running=$(pgrep -f "$SCRIPT_NAME")

if [ -n "$is_running" ]; then
    echo "$SCRIPT_NAME 正在运行，跳过启动。"
else
    echo "$SCRIPT_NAME 未运行，正在启动..."
    
    # 激活虚拟环境
    source ~/rss/rss_venv/bin/activate
    
    # 启动脚本
    nohup python ~/rss/os.py &
    
    echo "$SCRIPT_NAME 已启动。"
fi
