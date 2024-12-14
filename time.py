import os
from datetime import datetime, timedelta
import pytz
import asyncio
from telegram import Bot
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 从环境变量中读取配置
TOKEN = os.getenv('TELEGRAM_API_KEY')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 设置上海时区
shanghai = pytz.timezone('Asia/Shanghai')

# 初始化 Bot
bot = Bot(token=TOKEN)

# 定义基准日期，例如 2024-12-06 作为起始提醒日期
BASE_DATE = datetime(2024, 12, 6, tzinfo=shanghai)

async def send_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        print(f"Failed to send message: {e}")

async def check_reminders():
    now = datetime.now(shanghai)  # 获取上海时间

    messages = []

    # Daily medicine reminder
    messages.append('时间到，记得吃药！')

    # Every 10 days pass renewal reminder
    days_since_base = (now - BASE_DATE).days
    if days_since_base % 10 == 0:  # 如果今天是基准日期之后的第10天、第20天等
        messages.append('提醒：续签通行证！')

    # 年份提醒，每个日期有一个独特的提醒消息
    annual_reminders = {
        (1, 1): "元旦",
        (5, 1): "从业资格证年审",
        (12, 1): "小汽车年检"
    }

    for (month, day), message in annual_reminders.items():
        if now.month == month and now.day == day:
            messages.append(message)

    # 每月1号提醒云闪付
    if now.day == 1:
        messages.append('提醒：云闪付')

    # 如果有消息需要发送，合并它们并发送
    if messages:
        await send_message('\n\n'.join(messages))

if __name__ == "__main__":
    asyncio.run(check_reminders())
