import os
import asyncio
from datetime import datetime, timedelta
import pytz
import requests
from dotenv import load_dotenv
from lunarcalendar import Converter, Solar, Lunar

# 加载 .env 文件
load_dotenv()

# 从环境变量中读取配置
TOKEN = os.getenv('TELEGRAM_API_KEY')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 设置上海时区
shanghai = pytz.timezone('Asia/Shanghai')

# 定义基准日期，例如 2024-12-06 作为起始提醒日期
BASE_DATE = datetime(2024, 12, 6, tzinfo=shanghai)

def send_telegram_message(text):
    try:
        url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
        data = {
            'chat_id': CHAT_ID,
            'text': text
        }
        response = requests.post(url, data=data)
        response.raise_for_status()  # 如果请求失败，抛出异常
        print("Message sent successfully")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message: {e}")

async def check_reminders():
    now = datetime.now(shanghai)  # 获取上海时间
    solar_today = Solar(now.year, now.month, now.day)

    messages = []

    # Daily medicine reminder
    messages.append('时间到，记得吃药！')

    # Every 10 days pass renewal reminder
    days_since_base = (now - BASE_DATE).days
    if days_since_base % 10 == 0:  # 如果今天是基准日期之后的第10天、第20天等
        messages.append('提醒加油：续签通行证！')

    # 年份提醒，每个日期有一个独特的提醒消息
    annual_reminders = {
        (3, 1): "小汽车打腊",
        (5, 1): "从业资格证年审",
        (10, 5): "结婚周年",
        (12, 1): "小车年检保险"
    }

    # 添加固定年份的提醒
    specific_year_reminders = {
        (2025, 4, 5): "提醒：换建行银行卡",
        (2026, 10, 5): "结婚20周年",
        (2027, 5, 1): "彭贝娜医保卡到期换卡",
        (2027, 5, 11): "彭付生换身份证",
        (2028, 6, 1): "招商银行卡到期",
        (2037, 3, 22): "提醒：我换身份证"
    }

    # 遍历年份提醒
    for (month, day), message in annual_reminders.items():
        if now.month == month and now.day == day:
            messages.append(message)

    # 遍历特定年份的提醒
    for (year, month, day), message in specific_year_reminders.items():
        if now.year == year and now.month == month and now.day == day:
            messages.append(message)

    # 每月1号提醒云闪付
    if now.day == 1:
        messages.append('提醒：云闪付，汽车拍照')

    # 农历生日提醒
    lunar_today = Converter.Solar2Lunar(solar_today)
    
    # 定义农历生日
    lunar_birthdays = {
        (2, 1): "杜根华生日快乐！",
        (2, 28): "彭佳文生日快乐！",
        (3, 11): "刘裕萍生日快乐！",
        (4, 12): "彭绍莲生日快乐！",
        (4, 20): "邬思生日快乐！",
        (4, 27): "彭博生日快乐！",
        (5, 5): "周子君生日快乐！",
        (5, 17): "杜俊豪生日快乐！",
        (8, 19): "奶奶生日快乐！",       
        (8, 17): "邬启元生日快乐！",
        (10, 9): "彭付生生日快乐！",
        (10, 18): "彭贝娜生日快乐",
        (11, 12): "彭辉生日快乐！",
        (11, 22): "彭干生日快乐！",
        (12, 29): "彭世庆生日快乐！"
    }

    # 检查今天是否是某个人的农历生日
    for (month, day), message in lunar_birthdays.items():
        if lunar_today.month == month and lunar_today.day == day:
            messages.append(message)

    # 如果有消息需要发送，合并它们并发送
    if messages:
        send_telegram_message('\n\n'.join(messages))

if __name__ == "__main__":
    asyncio.run(check_reminders())
