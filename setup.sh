#!/bin/bash

# 进入 rss 目录
cd ~/rss || exit

# 创建虚拟环境
python3 -m venv rss_venv

# 激活虚拟环境
source rss_venv/bin/activate

# 安装 requirements.txt 中的库
pip install -r ~/rss/requirements.txt
pip install --upgrade pip

# 设置定时任务
# 检查是否已存在对应的 crontab 任务
(crontab -l | grep -q '~/rss/mail.py') || (crontab -l; echo "*/5 * * * * ~/rss/mail.sh ") | crontab -
(crontab -l | grep -q '~/rss/rss.py') || (crontab -l; echo "30 * * * * ~/rss/rss.sh") | crontab -

echo "设置完成！"

# 打开 .env 文件以便输入
nano ~/rss/.env