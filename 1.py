import requests
from bs4 import BeautifulSoup
import datetime
import asyncio
from telegram import Bot

# Telegram Bot 配置
TELEGRAM_API_TOKEN = '7422217982:AAGcyh0Do-RzggL8i61BksdVZModB6wfHzc'
CHAT_ID = '7071127210'

# 转义MarkdownV2中的特殊字符
def escape_markdown_v2(text):
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    return text

# 获取上证指数
def get_shanghai_index():
    url = 'https://finance.sina.com.cn/realstock/company/sh000001/nc.shtml'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 修改选择器，使用更具体的方式查找
    try:
        index_value = soup.find('div', {'class': 'price'}).text.strip()
    except AttributeError:
        index_value = "无法获取上证指数"
    
    return index_value

# 获取黄金价格
def get_gold_price():
    url = 'https://www.bullionvault.com/gold_price'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 找到黄金价格
    try:
        gold_price = soup.find('span', {'class': 'gold_price'}).text.strip()
    except AttributeError:
        gold_price = "无法获取黄金价格"
    
    return gold_price

# 异步发送消息到Telegram
async def send_to_telegram(message):
    bot = Bot(token=TELEGRAM_API_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='MarkdownV2')

# 主函数
async def main():
    # 获取数据
    shanghai_index = get_shanghai_index()
    gold_price = get_gold_price()
    
    # 格式化消息内容
    message = f"当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    message += f"上证指数: {shanghai_index}\n"
    message += f"黄金价格: {gold_price}\n"
    
    # 转义消息中的特殊字符
    message = escape_markdown_v2(message)
    
    # 发送消息
    await send_to_telegram(message)

if __name__ == '__main__':
    # 使用 asyncio 运行主函数
    asyncio.run(main())
