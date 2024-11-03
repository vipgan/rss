git clone https://github.com/penggan00/rss.git  
chmod +x ~/rss/rss.sh  
chmod +x ~/rss/rss2.sh  
chmod +x ~/rss/setup.sh  
chmod +x ~/rss/mail.sh  
# 安装
~/rss/setup.sh  


crontab -e
# 无链接
rss.py
# 24小时youtube
rss2.py

# 创建虚拟环境
python3 -m venv rss_venv
# 激活虚拟环境
source rss_venv/bin/activate
pip install --upgrade pip
python3 -m pip install -r requirements.txt

# 退出虚拟环境
deactivate