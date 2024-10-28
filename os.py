import os
import time
import psutil
from datetime import datetime, timedelta, timezone

# 上海时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

# 定义程序路径和调度规则
SCRIPTS = {
    "rss": {"path": "~/rss/rss.py", "time": ["30"]},         # 每小时的第30分钟运行
 #   "rss2": {"path": "~/rss/rss2.py", "interval_hours": 2},  # 每2小时运行一次
 #   "rss3": {"path": "~/rss/rss3.py", "time": ["08:00", "20:00"]},    # 每天00:00运行
    "mail": {"path": "~/rss/mail.py", "time": ["*/5"]}       # 每5分钟运行
}

# 上次运行时间记录
last_run = {key: datetime.min.replace(tzinfo=SHANGHAI_TZ) for key in SCRIPTS}

def expand_path(path):
    """将路径中的 ~ 扩展为用户目录"""
    return os.path.expanduser(path)

def is_running(script_name):
    """检查指定脚本是否在运行"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if script_name in " ".join(proc.info['cmdline']):
            return True
    return False

def run_script(script_path):
    """使用虚拟环境的 Python 解释器运行指定脚本"""
    script_path = expand_path(script_path)
    python_executable = expand_path("~/rss/rss_venv/bin/activate")  # 虚拟环境的 Python 解释器

    print(f"正在启动 {script_path}...")
    os.system(f"{python_executable} {script_path}")

def should_run_now(schedule, now):
    """判断是否应在当前时间运行"""
    if "interval_hours" in schedule:
        interval = schedule["interval_hours"]
        return (now - last_run[name]).total_seconds() >= interval * 3600

    for time_str in schedule.get("time", []):
        if time_str == "*/5" and now.minute % 5 == 0:
            return True
        elif ":" in time_str:
            scheduled_time = datetime.strptime(time_str, "%H:%M").time()
            if now.time() == scheduled_time:
                return True
        elif now.minute == int(time_str):
            return True
    return False

def monitor_scripts():
    """按调度规则管理脚本运行"""
    while True:
        now = datetime.now(SHANGHAI_TZ)

        for name, config in SCRIPTS.items():
            script_path = config["path"]

            if should_run_now(config, now):
                if not is_running(script_path):
                    run_script(script_path)
                    last_run[name] = now

        time.sleep(60)

if __name__ == "__main__":
    print("监控脚本启动...")
    monitor_scripts()
