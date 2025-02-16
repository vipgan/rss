import asyncio
import aiohttp
import logging
import re
import os
import json
import time
from dotenv import load_dotenv
from feedparser import parse
from telegram import Bot
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tmt.v20180321 import tmt_client, models

# 加载.env 文件
load_dotenv()

# 主题+翻意内容+预览
RSS_FEEDS = [
 #   'https://feeds.bbci.co.uk/news/world/rss.xml', # bbc
  #  'https://www3.nhk.or.jp/rss/news/cat6.xml',  # nhk
  #  'http://www3.nhk.or.jp/rss/news/cat5.xml',  # nhk金融
  #  'https://www.cnbc.com/id/100003114/device/rss/rss.html', # CNBC
  #  'https://feeds.a.dj.com/rss/RSSWorldNews.xml', # 华尔街日报
  #  'https://www.aljazeera.com/xml/rss/all.xml',# 半岛电视台
  #  'https://www3.nhk.or.jp/rss/news/cat5.xml',# NHK 商业
  #  'https://www.ft.com/?format=rss', # 金融时报
  #  'http://rss.cnn.com/rss/edition.rss', # cnn

]
#主题+内容
THIRD_RSS_FEEDS = [ 
 #   'https://36kr.com/feed-newsflash',
 #   'https://rsshub.app/10jqka/realtimenews',

]
 # 主题+预览
FOURTH_RSS_FEEDS = [
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCvijahEyGtvMpmMHBu4FS2w', # 零度解说
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UC96OvMh0Mb_3NmuE8Dpu7Gg', # 搞机零距离
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCQoagx4VHBw3HkAyzvKEEBA', # 科技共享
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCbCCUH8S3yhlm7__rhxR2QQ', # 不良林
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCMtXiCoKFrc2ovAGc1eywDg', # 一休 
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCii04BCvYIdQvshrdNDAcww', # 悟空的日常 
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCJMEiNh1HvpopPU3n9vJsMQ', # 理科男士 
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCYjB6uufPeHSwuHs8wovLjg', # 中指通 
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCSs4A6HYKmHA2MG_0z-F0xw', # 李永乐老师 
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCZDgXi7VpKhBJxsPuZcBpgA', # 可恩KeEn  
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCxukdnZiXnTFvjF5B5dvJ5w', # 甬哥侃侃侃ygkkk  
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCUfT9BAofYBKUTiEVrgYGZw', # 科技分享  
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UC51FT5EeNPiiQzatlA2RlRA', # 乌客wuke  
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCDD8WJ7Il3zWBgEYBUtc9xQ', # jack stone  
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCWurUlxgm7YJPPggDz9YJjw', # 一瓶奶油
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCvENMyIFurJi_SrnbnbyiZw', # 酷友社
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCmhbF9emhHa-oZPiBfcLFaQ', # WenWeekly
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UC3BNSKOaphlEoK4L7QTlpbA', # 中外观察
]

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv("RSS_TWO")      #bbc
RSS_TWO = os.getenv("RSS_TWO")    #36
RSS_TOKEN = os.getenv("RSS_TOKEN")  #好烟10086
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").split(",")

# 本地文件存储配置
SENT_ENTRIES_FILE = "rss.json"
SENT_ENTRIES_FILE_THIRD = "rss2.json"
SENT_ENTRIES_FILE_FOURTH = "rss3.json"

TENCENTCLOUD_SECRET_ID = os.getenv("TENCENTCLOUD_SECRET_ID")
TENCENTCLOUD_SECRET_KEY = os.getenv("TENCENTCLOUD_SECRET_KEY")

MAX_ENTRIES_TO_KEEP = 5000
TELEGRAM_DELAY = 0.5  # 发送消息后的延迟时间（秒）
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 1  # 初始重试延迟（秒）

def sanitize_markdown(text):
    # 首先去除 HTML 标签
    text = re.sub(r'<[^>]*>', '', text)
    # 然后去除 Telegram 不支持的 Markdown 符号
    # 这里添加了更多的转义
    text = re.sub(r'([*_`\[\]\(\)\~>#+\-=|{}.!])', r'\\\1', text)
    return text

async def send_single_message(bot, chat_id, text, disable_web_page_preview=True, retry_count=0):
    try:
        # Telegram 最大消息字节数限制：4096字节
        MAX_MESSAGE_LENGTH = 4096
        # 计算消息的字节数
        if len(text.encode('utf-8')) > MAX_MESSAGE_LENGTH:
            # 如果超长，拆分为多个消息
            for i in range(0, len(text), MAX_MESSAGE_LENGTH):
                await bot.send_message(
                    chat_id=chat_id, 
                    text=text[i:i+MAX_MESSAGE_LENGTH], 
                    parse_mode='Markdown', 
                    disable_web_page_preview=disable_web_page_preview
                )
                await asyncio.sleep(TELEGRAM_DELAY) # 添加延迟
        else:
            # 如果没有超长，直接发送
            await bot.send_message(
                chat_id=chat_id, 
                text=text, 
                parse_mode='Markdown', 
                disable_web_page_preview=disable_web_page_preview
            )
            await asyncio.sleep(TELEGRAM_DELAY) # 添加延迟
    except Exception as e:
        logging.error(f"Failed to send message (attempt {retry_count+1}): {e}, message: {text}")
        if retry_count < MAX_RETRIES:
            delay = RETRY_DELAY * (2 ** retry_count)
            logging.info(f"Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
            return await send_single_message(bot, chat_id, text, disable_web_page_preview, retry_count + 1)
        else:
             logging.error(f"Max retries exceeded for message: {text}")

async def fetch_feed(session, feed_url, retry_count=0):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
    }
    try:
        async with session.get(feed_url, headers=headers, timeout=60) as response: # 增加超时时间
            response.raise_for_status()
            content = await response.read()
            return parse(content)
    except aiohttp.ClientError as e:
        logging.error(f"Error fetching {feed_url} (attempt {retry_count+1}): {e}")
        if retry_count < MAX_RETRIES:
            delay = RETRY_DELAY * (2 ** retry_count)
            logging.info(f"Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
            return await fetch_feed(session, feed_url, retry_count + 1)
        else:
             logging.error(f"Max retries exceeded for feed: {feed_url}")
             return None
    except Exception as e:
        logging.error(f"Error fetching {feed_url} (attempt {retry_count+1}): {e}")
        return None

async def auto_translate_text(text):
    try:
        cred = credential.Credential(TENCENTCLOUD_SECRET_ID, TENCENTCLOUD_SECRET_KEY)
        httpProfile = HttpProfile(endpoint="tmt.tencentcloudapi.com")
        clientProfile = ClientProfile(httpProfile=httpProfile)
        client = tmt_client.TmtClient(cred, "na-siliconvalley", clientProfile)

        req = models.TextTranslateRequest()
        req.SourceText = text
        req.Source = "auto"
        req.Target = "zh"
        req.ProjectId = 0

        resp = client.TextTranslate(req)
        return resp.TargetText
    except Exception as e:
        logging.error(f"Translation error for text '{text}': {e}")
        return text
# 主题+翻意内容+预览
async def process_feed(session, feed_url, sent_entries, bot, file_path, translate=True):
    feed_data = await fetch_feed(session, feed_url)
    if feed_data is None:
        return []

    source_name = feed_data.feed.get('title', feed_url)  # 动态获取源名称
    new_entries = []

    for entry in feed_data.entries:
        subject = entry.title or "*无标题*"
        url = entry.link
        summary = getattr(entry, 'summary', "暂无简介")
        message_id = f"{subject}_{url}"

        if (url, subject, message_id) not in sent_entries:
            if translate:
                translated_subject = await auto_translate_text(subject)
                translated_summary = await auto_translate_text(summary)
            else:
                translated_subject = subject
                translated_summary = summary

            cleaned_subject = sanitize_markdown(translated_subject)
            cleaned_summary = sanitize_markdown(translated_summary)
            message = f"*{cleaned_subject}*\n{cleaned_summary}\n[{source_name}]({url})"

            if len(message.encode('utf-8')) > 4096:
                logging.warning(f"Message too long, skipping: {message}")
                continue

            try:
                await send_single_message(bot, TELEGRAM_CHAT_ID[0], message)
            except Exception as e:
                logging.error(f"Error sending message for subject '{cleaned_subject}': {e}")

            new_entries.append((url, subject, message_id))
            sent_entries.add((url, subject, message_id))
            await save_sent_entries(sent_entries, file_path)


    return new_entries
# 主题+内容 超过333字节不发送
async def process_third_feed(session, feed_url, sent_entries, bot, file_path):
    feed_data = await fetch_feed(session, feed_url)
    if feed_data is None:
        return []

    source_name = feed_data.feed.get('title', feed_url)  # 动态获取源名称
    merged_message = ""

    for entry in feed_data.entries:
        subject = entry.title or "*无标题*"
        url = entry.link
        summary = getattr(entry, 'summary', "暂无简介")
        summary = sanitize_markdown(summary)
        message_id = f"{subject}_{url}"

        if (url, subject, message_id) not in sent_entries:
            cleaned_subject = sanitize_markdown(subject)

            # 检查主题和内容的字节长度
            total_length = len(cleaned_subject.encode('utf-8')) + len(summary.encode('utf-8'))
            if total_length > 333:
                # 超过 333 字节的内容直接跳过，不发送
                continue
            else:
                # 如果字节长度不超过 333 字节，则合并发送
                merged_message += f"*{cleaned_subject}*\n{summary}\n[{source_name}]({url})\n\n"
                sent_entries.add((url, subject, message_id))
                await save_sent_entries(sent_entries, file_path)

    if merged_message:
        # 发送合并后的消息
        try:
            await send_single_message(bot, TELEGRAM_CHAT_ID[0], merged_message, disable_web_page_preview=True)
        except Exception as e:
            logging.error(f"Error sending merged message: {e}")


    return []

# 主题+预览
async def process_fourth_feed(session, feed_url, sent_entries, bot, file_path):
    feed_data = await fetch_feed(session, feed_url)
    if feed_data is None:
        return []

    source_name = feed_data.feed.get('title', feed_url)  # 动态获取源名称
    merged_message = ""

    for entry in feed_data.entries:
        subject = entry.title or "*无标题*"
        url = entry.link
        message_id = f"{subject}_{url}"

        if (url, subject, message_id) not in sent_entries:
            cleaned_subject = sanitize_markdown(subject)
            merged_message += f"{source_name}\n*{cleaned_subject}*\n{url}\n\n"

            sent_entries.add((url, subject, message_id))
            await save_sent_entries(sent_entries, file_path)

    if merged_message:
        try:
            await send_single_message(bot, TELEGRAM_CHAT_ID[0], merged_message, disable_web_page_preview=False)
        except Exception as e:
            logging.error(f"Error sending merged message: {e}")


    return []

# 加载本地保存的已发送条目
def load_sent_entries(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 将加载的数据转换为集合，并限制大小
                return set(tuple(item) for item in data[-MAX_ENTRIES_TO_KEEP:])
        except Exception as e:
            logging.error(f"Error loading sent entries from {file_path}: {e}")
            return set()
    return set()

# 保存已发送条目到本地文件
async def save_sent_entries(sent_entries, file_path):
    try:
        # 限制保存的条目数量
        entries_to_save = list(sent_entries)[-MAX_ENTRIES_TO_KEEP:]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(entries_to_save, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving sent entries to {file_path}: {e}")

async def main():
    sent_entries = load_sent_entries(SENT_ENTRIES_FILE)
    sent_entries_third = load_sent_entries(SENT_ENTRIES_FILE_THIRD)
    sent_entries_fourth = load_sent_entries(SENT_ENTRIES_FILE_FOURTH)

    connector = aiohttp.TCPConnector(limit=200)  # 增加连接池大小
    async with aiohttp.ClientSession(connector=connector) as session:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        third_bot = Bot(token=RSS_TWO)
        fourth_bot = Bot(token=RSS_TOKEN)

        tasks = [
            process_feed(session, feed_url, sent_entries, bot, SENT_ENTRIES_FILE, translate=True)
            for feed_url in RSS_FEEDS
        ] + [
            process_third_feed(session, feed_url, sent_entries_third, third_bot, SENT_ENTRIES_FILE_THIRD)
            for feed_url in THIRD_RSS_FEEDS
        ] + [
             process_fourth_feed(session, feed_url, sent_entries_fourth, fourth_bot, SENT_ENTRIES_FILE_FOURTH)
            for feed_url in FOURTH_RSS_FEEDS
        ]

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    asyncio.run(main())
