import asyncio
import aiohttp
import logging
import re
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from feedparser import parse
from telegram import Bot
from telegram.helpers import escape_markdown
from telegram.error import BadRequest
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tmt.v20180321 import tmt_client, models

# 加载.env 文件
load_dotenv()

# 配置绝对路径
BASE_DIR = Path(__file__).resolve().parent
STATUS_FILE = BASE_DIR / "rss.json"

# 配置日志
logging.basicConfig(
    filename=BASE_DIR / "rss.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

RSS_FEEDS = [
    'https://feeds.bbci.co.uk/news/world/rss.xml', # bbc
  #  'https://www3.nhk.or.jp/rss/news/cat6.xml',  # nhk
  #  'http://www3.nhk.or.jp/rss/news/cat5.xml',  # nhk金融
  #  'https://www.cnbc.com/id/100003114/device/rss/rss.html', # CNBC
  #  'https://feeds.a.dj.com/rss/RSSWorldNews.xml', # 华尔街日报
  #  'https://www.aljazeera.com/xml/rss/all.xml',# 半岛电视台
  #  'https://www3.nhk.or.jp/rss/news/cat5.xml',# NHK 商业
  #  'https://www.ft.com/?format=rss', # 金融时报
  #  'http://rss.cnn.com/rss/edition.rss', # cnn

]
#主题+内容+预览
THIRD_RSS_FEEDS = [
    'https://36kr.com/feed-newsflash',
  #  'https://rss.owo.nz/10jqka/realtimenews',
    'https://rss.penggan.us.kg/rss/7b7190c84ada52e7a89e2901ea71ce41_chinese_simplified',
    'https://rss.penggan.us.kg/rss/7b0c2fb839915016a94424c9ebd6d7cb_chinese_simplified',
    'https://rss.penggan.us.kg/rss/57fac0d19e56587f9264b3a0485b46e3_chinese_simplified',
  #  'https://rss.penggan.us.kg/rss/4734eed5ffb55689bfe8ebc4f55e63bd_chinese_simplified',
]
 # 主题+预览
FOURTH_RSS_FEEDS = [
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCvijahEyGtvMpmMHBu4FS2w', # 零度解说
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC96OvMh0Mb_3NmuE8Dpu7Gg', # 搞机零距离
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCQoagx4VHBw3HkAyzvKEEBA', # 科技共享
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCbCCUH8S3yhlm7__rhxR2QQ', # 不良林
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCMtXiCoKFrc2ovAGc1eywDg', # 一休
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCii04BCvYIdQvshrdNDAcww', # 悟空的日常
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCJMEiNh1HvpopPU3n9vJsMQ', # 理科男士
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCYjB6uufPeHSwuHs8wovLjg', # 中指通
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCSs4A6HYKmHA2MG_0z-F0xw', # 李永乐老师
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCZDgXi7VpKhBJxsPuZcBpgA', # 可恩KeEn
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCxukdnZiXnTFvjF5B5dvJ5w', # 甬哥侃侃侃ygkkk
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCUfT9BAofYBKUTiEVrgYGZw', # 科技分享
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UC51FT5EeNPiiQzatlA2RlRA', # 乌客wuke
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCDD8WJ7Il3zWBgEYBUtc9xQ', # jack stone
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCWurUlxgm7YJPPggDz9YJjw', # 一瓶奶油
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCvENMyIFurJi_SrnbnbyiZw', # 酷友社
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCmhbF9emhHa-oZPiBfcLFaQ', # WenWeekly
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UC3BNSKOaphlEoK4L7QTlpbA', # 中外观察
]

# Telegram配置
TELEGRAM_BOT_TOKEN = os.getenv("RSS_TWO")
RSS_TWO = os.getenv("RSS_TWO")
RSS_TOKEN = os.getenv("RSS_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").split(",")
TENCENTCLOUD_SECRET_ID = os.getenv("TENCENTCLOUD_SECRET_ID")
TENCENTCLOUD_SECRET_KEY = os.getenv("TENCENTCLOUD_SECRET_KEY")

MAX_CONCURRENT_REQUESTS = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def remove_html_tags(text):
    """彻底移除HTML标签"""
    return re.sub(r'<[^>]*>', '', text)

async def send_single_message(bot, chat_id, text, disable_web_page_preview=False):
    try:
        MAX_MESSAGE_LENGTH = 4096
        if len(text.encode('utf-8')) > MAX_MESSAGE_LENGTH:
            for i in range(0, len(text), MAX_MESSAGE_LENGTH):
                await bot.send_message(
                    chat_id=chat_id,
                    text=text[i:i+MAX_MESSAGE_LENGTH],
                    parse_mode='MarkdownV2',
                    disable_web_page_preview=disable_web_page_preview
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='MarkdownV2',
                disable_web_page_preview=disable_web_page_preview
            )
    except BadRequest as e:
        logging.error(f"消息发送失败(Markdown错误): {e} - 文本片段: {text[:200]}...")
    except Exception as e:
        logging.error(f"消息发送失败: {e}")

async def fetch_feed(session, feed_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'}
    try:
        async with semaphore:
            async with session.get(feed_url, headers=headers, timeout=40) as response:
                response.raise_for_status()
                return parse(await response.read())
    except Exception as e:
        logging.error(f"抓取失败 {feed_url}: {e}")
        return None

async def auto_translate_text(text):
    try:
        cred = credential.Credential(TENCENTCLOUD_SECRET_ID, TENCENTCLOUD_SECRET_KEY)
        clientProfile = ClientProfile(httpProfile=HttpProfile(endpoint="tmt.tencentcloudapi.com"))
        client = tmt_client.TmtClient(cred, "na-siliconvalley", clientProfile)

        req = models.TextTranslateRequest()
        req.SourceText = remove_html_tags(text)  # 翻译前先移除HTML
        req.Source = "auto"
        req.Target = "zh"
        req.ProjectId = 0

        return client.TextTranslate(req).TargetText
    except Exception as e:
        logging.error(f"翻译错误: {e}")
        return text

def load_status():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_status(status):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"状态保存失败: {e}")

def get_entry_identifier(entry):
    """获取条目唯一标识"""
    if hasattr(entry, 'guid') and entry.guid:
        return entry.guid
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6]).isoformat()
    if hasattr(entry, 'pubDate_parsed') and entry.pubDate_parsed:
        return datetime(*entry.pubDate_parsed[:6]).isoformat()
    return f"{entry.get('title', '')}-{entry.get('link', '')}"

def get_entry_timestamp(entry):
    """获取标准化时间戳"""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    if hasattr(entry, 'pubDate_parsed') and entry.pubDate_parsed:
        return datetime(*entry.pubDate_parsed[:6])
    return datetime.now()

async def process_feed(session, feed_url, status, bot, translate=True):
    feed_data = await fetch_feed(session, feed_url)
    if not feed_data or not feed_data.entries:
        return ""

    # 状态处理
    last_status = status.get(feed_url, {})
    last_identifier = last_status.get('identifier')
    last_timestamp = datetime.fromisoformat(last_status.get('timestamp')) if last_status.get('timestamp') else None

    # 按时间排序
    sorted_entries = sorted(feed_data.entries, 
                          key=lambda x: get_entry_timestamp(x), 
                          reverse=True)

    new_entries = []
    current_latest = None

    for entry in sorted_entries:
        entry_time = get_entry_timestamp(entry)
        identifier = get_entry_identifier(entry)

        if last_identifier and identifier == last_identifier:
            break
        if last_timestamp and entry_time <= last_timestamp:
            break

        new_entries.append(entry)
        if not current_latest or entry_time > get_entry_timestamp(current_latest):
            current_latest = entry

    if not new_entries:
        return ""

    # 更新状态
    if current_latest:
        status[feed_url] = {
            "identifier": get_entry_identifier(current_latest),
            "timestamp": get_entry_timestamp(current_latest).isoformat()
        }

    # 处理消息
    merged_message = ""
    source_name = feed_data.feed.get('title', feed_url)
    for entry in reversed(new_entries):
        # 原始内容处理
        raw_subject = remove_html_tags(entry.title or "无标题")
        raw_summary = remove_html_tags(getattr(entry, 'summary', "暂无简介"))
        raw_url = entry.link

        # 翻译处理
        if translate:
            translated_subject = await auto_translate_text(raw_subject)
            translated_summary = await auto_translate_text(raw_summary)
        else:
            translated_subject = raw_subject
            translated_summary = raw_summary

        # Markdown转义
        safe_subject = escape_markdown(translated_subject, version=2)
        safe_summary = escape_markdown(translated_summary, version=2)
        safe_source = escape_markdown(source_name, version=2)
        safe_url = escape_markdown(raw_url, version=2)

        # 构建消息
        message = f"*{safe_subject}*\n{safe_summary}\n[{safe_source}]({safe_url})"
        merged_message += message + "\n\n"

    return merged_message

async def process_third_feed(session, feed_url, status, bot):
    feed_data = await fetch_feed(session, feed_url)
    if not feed_data or not feed_data.entries:
        return ""

    last_status = status.get(feed_url, {})
    last_identifier = last_status.get('identifier')
    last_timestamp = datetime.fromisoformat(last_status.get('timestamp')) if last_status.get('timestamp') else None

    sorted_entries = sorted(feed_data.entries,
                          key=lambda x: get_entry_timestamp(x),
                          reverse=True)

    new_entries = []
    current_latest = None

    for entry in sorted_entries:
        entry_time = get_entry_timestamp(entry)
        identifier = get_entry_identifier(entry)

        if last_identifier and identifier == last_identifier:
            break
        if last_timestamp and entry_time <= last_timestamp:
            break

        new_entries.append(entry)
        if not current_latest or entry_time > get_entry_timestamp(current_latest):
            current_latest = entry

    if not new_entries:
        return ""

    if current_latest:
        status[feed_url] = {
            "identifier": get_entry_identifier(current_latest),
            "timestamp": get_entry_timestamp(current_latest).isoformat()
        }

    merged_message = ""
    source_name = feed_data.feed.get('title', feed_url)
    for entry in reversed(new_entries):
        # 内容处理
        raw_subject = remove_html_tags(entry.title or "无标题")
        raw_summary = remove_html_tags(getattr(entry, 'summary', "暂无简介"))
        raw_url = entry.link

        # Markdown转义
        safe_subject = escape_markdown(raw_subject, version=2)
        safe_summary = escape_markdown(raw_summary, version=2)
        safe_source = escape_markdown(source_name, version=2)
        safe_url = escape_markdown(raw_url, version=2)

        # 消息构建
        message_content = f"*{safe_subject}*\n{safe_summary}\n[{safe_source}]({safe_url})"
        message_bytes = message_content.encode('utf-8')

        if len(message_bytes) <= 333:
            merged_message += message_content + "\n\n"
        else:
            title_link = f"*{safe_subject}*\n[{safe_source}]({safe_url})"
            merged_message += title_link + "\n\n"

    return merged_message

async def process_fourth_feed(session, feed_url, status, bot):
    feed_data = await fetch_feed(session, feed_url)
    if not feed_data or not feed_data.entries:
        return ""

    last_status = status.get(feed_url, {})
    last_identifier = last_status.get('identifier')
    last_timestamp = datetime.fromisoformat(last_status.get('timestamp')) if last_status.get('timestamp') else None

    sorted_entries = sorted(feed_data.entries,
                          key=lambda x: get_entry_timestamp(x),
                          reverse=True)

    new_entries = []
    current_latest = None

    for entry in sorted_entries:
        entry_time = get_entry_timestamp(entry)
        identifier = get_entry_identifier(entry)

        if last_identifier and identifier == last_identifier:
            break
        if last_timestamp and entry_time <= last_timestamp:
            break

        new_entries.append(entry)
        if not current_latest or entry_time > get_entry_timestamp(current_latest):
            current_latest = entry

    if not new_entries:
        return ""

    if current_latest:
        status[feed_url] = {
            "identifier": get_entry_identifier(current_latest),
            "timestamp": get_entry_timestamp(current_latest).isoformat()
        }

    merged_message = ""
    source_name = feed_data.feed.get('title', feed_url)
    for entry in reversed(new_entries):
        # 内容处理
        raw_subject = remove_html_tags(entry.title or "无标题")
        raw_url = entry.link

        # Markdown转义
        safe_subject = escape_markdown(raw_subject, version=2)
        safe_source = escape_markdown(source_name, version=2)
        safe_url = escape_markdown(raw_url, version=2)

        merged_message += f"*{safe_subject}*\n[{safe_source}]({safe_url})\n\n"

    return merged_message

async def main():
    async with aiohttp.ClientSession() as session:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        third_bot = Bot(token=RSS_TWO)
        fourth_bot = Bot(token=RSS_TOKEN)

        status = load_status()

        # 处理第一类源
        for url in RSS_FEEDS:
            if message := await process_feed(session, url, status, bot):
                await send_single_message(bot, TELEGRAM_CHAT_ID[0], message, True)

        # 处理第三类源
        for url in THIRD_RSS_FEEDS:
            if message := await process_third_feed(session, url, status, third_bot):
                await send_single_message(third_bot, TELEGRAM_CHAT_ID[0], message, True)

        # 处理第四类源
        for url in FOURTH_RSS_FEEDS:
            if message := await process_fourth_feed(session, url, status, fourth_bot):
                await send_single_message(fourth_bot, TELEGRAM_CHAT_ID[0], message)

        save_status(status)

if __name__ == "__main__":
    asyncio.run(main())