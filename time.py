import os
from dotenv import load_dotenv
from telegram import Bot
import asyncio

async def send_medicine_reminder():
    # 加载 .env 文件中的环境变量
    load_dotenv()
    bot_token = os.getenv("TELEGRAM_API_KEY")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    # 检查环境变量是否正确加载
    if not bot_token or not chat_id:
        print("环境变量未正确加载，请检查 .env 文件")
        return

    # 创建 Telegram Bot 实例
    bot = Bot(token=bot_token)

    # 消息内容
    message = "提醒：请记得9点吃药！💊"

    # 发送消息
    try:
        print("正在发送消息...")
        await bot.send_message(chat_id=chat_id, text=message)
        print("消息已成功发送！")
    except Exception as e:
        print(f"发送消息时出现错误: {e}")

if __name__ == "__main__":
    asyncio.run(send_medicine_reminder())
