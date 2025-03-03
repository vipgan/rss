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
from telegram.error import BadRequest
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tmt.v20180321 import tmt_client, models

# 加载.env 文件
load_dotenv()

# 配置绝对路径
BASE_DIR = Path(__file__).resolve().parent
STATUS_FILE = BASE_DIR / "rss2.json"

# 配置日志
logging.basicConfig(
    filename=BASE_DIR / "rss2.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

RSS_FEEDS = [
  #  'https://feeds.bbci.co.uk/news/world/rss.xml', # bbc
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
  #  'https://36kr.com/feed-newsflash',
   # 'https://rss.owo.nz/10jqka/realtimenews',
  #  'https://rss.penggan.us.kg/rss/7b7190c84ada52e7a89e2901ea71ce41_chinese_simplified',
   # 'https://rss.penggan.us.kg/rss/7b0c2fb839915016a94424c9ebd6d7cb_chinese_simplified',
   # 'https://rss.penggan.us.kg/rss/57fac0d19e56587f9264b3a0485b46e3_chinese_simplified',
  #  'https://rss.penggan.us.kg/rss/4734eed5ffb55689bfe8ebc4f55e63bd_chinese_simplified',
]
 # 主题+预览
FOURTH_RSS_FEEDS = [
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCUNciDq-y6I6lEQPeoP-R5A', # 苏恒观察
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCXkOTZJ743JgVhJWmNV8F3Q', # 寒國人
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC2r2LPbOUssIa02EbOIm7NA', # 星球熱點
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCF-Q1Zwyn9681F7du8DMAWg', # 謝宗桓-老謝來了
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCOSmkVK2xsihzKXQgiXPS4w', # 历史哥
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCSYBgX9pWGiUAcBxjnj6JCQ', # 郭正亮頻道
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCNiJNzSkfumLB7bYtXcIEmg', # 真的很博通
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCG_gH6S-2ZUOtEw27uIS_QA', # 7Car小七車觀點
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCJ5rBA0z4WFGtUTS83sAb_A', # POP Radio聯播網
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCQeRaTukNYft1_6AZPACnog', # Asmongold TV 
    'https://rss.penggan.us.kg/rss/4734eed5ffb55689bfe8ebc4f55e63bd_chinese_simplified', # Asmongold TV 
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCN0eCImZY6_OiJbo8cy5bLw', # 屈機TV 
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCb3TZ4SD_Ys3j4z0-8o6auA', # BBC News 中文
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCiwt1aanVMoPYUt_CQYCPQg', # 全球大視野
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC000Jn3HGeQSwBuX_cLDK8Q', # 我是柳傑克
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCQFEBaHCJrHu2hzDA_69WQg', # 国漫说
# 影视
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC7Xeh7thVIgs_qfTlwC-dag', # Marc TV
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCqWNOHjgfL8ADEdXGznzwUw', # 悦耳音乐酱
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCCD14H7fJQl3UZNWhYMG3Mg', # 温城鲤
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCQO2T82PiHCYbqmCQ6QO6lw', # 月亮說
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCKyDmY3R_xGKz8IjvbijiHA', # 珊珊追剧社
    'https://www.youtube.com/feeds/videos.xml?channel_id=UClyVC2wh_2fQhU0hPdXA4rw', # 热门古风
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UC1ISajIKfRN359MMmtckUTg', # Taiwanese Pop Mix
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCQFyMGc6h30NMCd6HCk0ZPA', # 哔哩哔哩动画
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCQatgKoA7lylp_UzvsLCgcw', # 腾讯视频
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCUhpu5MJQ_bjPkXO00jyxsw', # 爱奇艺
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCHW6W9g2TJL2_Lf7GfoI5kg', # 电影放映厅
]

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv("RSS_TWO")
RSS_TWO = os.getenv("RSS_TWO")
YOUTUBE_RSS = os.getenv("YOUTUBE_RSS")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").split(",")
TENCENTCLOUD_SECRET_ID = os.getenv("TENCENTCLOUD_SECRET_ID")
TENCENTCLOUD_SECRET_KEY = os.getenv("TENCENTCLOUD_SECRET_KEY")

MAX_CONCURRENT_REQUESTS = 10
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def sanitize_markdown_v2(text):
    """
    转义 Telegram Markdown V2 中的特殊字符，并移除斜体等格式。
    只保留粗体，并安全地处理 URL。
    """
    # Markdown V2 需要转义的字符
    md_special_chars = r'_*[]()~`>#+-=|{}.!'
    pattern = f'([{re.escape(md_special_chars)}])'
    text = re.sub(pattern, r'\\\1', text)

    # 移除 HTML 标签
    text = re.sub(r'<[^>]*>', '', text)

    return text

def format_link_markdown_v2(text, url):
    """
    创建 Markdown V2 格式的安全链接。
    """
    # 对 URL 进行转义，确保它不包含 Markdown V2 特殊字符
    safe_url = sanitize_markdown_v2(url)
    safe_text = sanitize_markdown_v2(text)  # 确保链接文本也安全

    return f"[{safe_text}]({safe_url})"


async def send_single_message(bot, chat_id, text, disable_web_page_preview=False):
    try:
        MAX_MESSAGE_LENGTH = 4096
        if len(text.encode('utf-8')) > MAX_MESSAGE_LENGTH:
            for i in range(0, len(text), MAX_MESSAGE_LENGTH):
                await bot.send_message(
                    chat_id=chat_id,
                    text=text[i:i+MAX_MESSAGE_LENGTH],
                    parse_mode='MarkdownV2',  # 明确指定 MarkdownV2
                    disable_web_page_preview=disable_web_page_preview
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='MarkdownV2', # 明确指定 MarkdownV2
                disable_web_page_preview=disable_web_page_preview
            )
    except BadRequest as e:
        logging.error(f"Failed to send message (Markdown error): {e} - Text: {text[:200]}...") # 记录前200个字符
    except Exception as e:
        logging.error(f"Failed to send message: {e}")


async def fetch_feed(session, feed_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'}
    try:
        async with semaphore:
            async with session.get(feed_url, headers=headers, timeout=40) as response:
                response.raise_for_status()
                return parse(await response.read())
    except Exception as e:
        logging.error(f"Error fetching {feed_url}: {e}")
        return None

async def auto_translate_text(text):
    try:
        cred = credential.Credential(TENCENTCLOUD_SECRET_ID, TENCENTCLOUD_SECRET_KEY)
        clientProfile = ClientProfile(httpProfile=HttpProfile(endpoint="tmt.tencentcloudapi.com"))
        client = tmt_client.TmtClient(cred, "na-siliconvalley", clientProfile)

        req = models.TextTranslateRequest()
        req.SourceText = text
        req.Source = "auto"
        req.Target = "zh"
        req.ProjectId = 0

        return client.TextTranslate(req).TargetText
    except Exception as e:
        logging.error(f"Translation error: {e}")
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
        logging.error(f"Error saving status: {e}")

def get_entry_identifier(entry):
    """获取条目的唯一标识符"""
    if hasattr(entry, 'guid') and entry.guid:
        return entry.guid
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6]).isoformat()
    if hasattr(entry, 'pubDate_parsed') and entry.pubDate_parsed:
        return datetime(*entry.pubDate_parsed[:6]).isoformat()
    return f"{entry.get('title', '')}-{entry.get('link', '')}"

def get_entry_timestamp(entry):
    """获取条目的标准化时间戳"""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    if hasattr(entry, 'pubDate_parsed') and entry.pubDate_parsed:
        return datetime(*entry.pubDate_parsed[:6])
    return datetime.now()

async def process_feed(session, feed_url, status, bot, translate=True):
    feed_data = await fetch_feed(session, feed_url)
    if not feed_data or not feed_data.entries:
        return ""

    # 获取上次处理状态
    last_status = status.get(feed_url, {})
    last_identifier = last_status.get('identifier')
    last_timestamp = datetime.fromisoformat(last_status.get('timestamp')) if last_status.get('timestamp') else None

    # 按时间倒序排序
    sorted_entries = sorted(feed_data.entries, 
                          key=lambda x: get_entry_timestamp(x), 
                          reverse=True)

    new_entries = []
    current_latest = None

    for entry in sorted_entries:
        entry_time = get_entry_timestamp(entry)
        identifier = get_entry_identifier(entry)

        # 遇到已处理的条目则停止
        if last_identifier and identifier == last_identifier:
            break
        if last_timestamp and entry_time <= last_timestamp:
            break

        new_entries.append(entry)
        # 记录当前最新的条目
        if not current_latest or entry_time > get_entry_timestamp(current_latest):
            current_latest = entry

    # 如果没有新条目
    if not new_entries:
        return ""

    # 更新处理状态
    if current_latest:
        status[feed_url] = {
            "identifier": get_entry_identifier(current_latest),
            "timestamp": get_entry_timestamp(current_latest).isoformat()
        }

    # 按实际发布时间顺序处理（旧→新）
    merged_message = ""
    source_name = feed_data.feed.get('title', feed_url)
    for entry in reversed(new_entries):
        subject = entry.title or "*无标题*"
        url = entry.link
        summary = getattr(entry, 'summary', "暂无简介")  # 注意这里没有sanitize_markdown

        if translate:
            translated_subject = await auto_translate_text(subject)
            translated_summary = await auto_translate_text(summary)
        else:
            translated_subject = subject
            translated_summary = summary

        safe_subject = sanitize_markdown_v2(translated_subject)  # 转义主题
        safe_summary = sanitize_markdown_v2(translated_summary)  # 转义摘要

        # 构建 Markdown V2 消息
        formatted_link = format_link_markdown_v2(source_name, url)
        message = f"*{safe_subject}*\n{safe_summary}\n{formatted_link}"  # 粗体主题，安全链接

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
        subject = entry.title or "*无标题*"
        url = entry.link
        summary = getattr(entry, 'summary', "暂无简介")

        # Markdown V2 格式化
        safe_subject = sanitize_markdown_v2(subject)
        safe_summary = sanitize_markdown_v2(summary)
        formatted_link = format_link_markdown_v2(source_name, url)

        message_content = f"*{safe_subject}*\n{safe_summary}\n{formatted_link}" # 粗体主题, 安全链接
        message_bytes = message_content.encode('utf-8')

        if len(message_bytes) <= 333:
            merged_message += message_content + "\n\n"
        else:
            title_and_link = f"*{safe_subject}*\n{formatted_link}"# 粗体主题, 安全链接
            merged_message += title_and_link + "\n\n"

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
        subject = entry.title or "*无标题*"
        url = entry.link

        # Markdown V2 格式化
        safe_subject = sanitize_markdown_v2(subject)
        formatted_link = format_link_markdown_v2(source_name, url)


        merged_message += f"*{safe_subject}*\n{formatted_link}\n\n" # 粗体主题，安全链接

    return merged_message

async def main():
    async with aiohttp.ClientSession() as session:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        third_bot = Bot(token=RSS_TWO)
        fourth_bot = Bot(token=YOUTUBE_RSS)

        # 加载处理状态
        status = load_status()

        # 处理三类源
        for url in RSS_FEEDS:
            message = await process_feed(session, url, status, bot)
            if message:
                await send_single_message(bot, TELEGRAM_CHAT_ID[0], message, True)

        for url in THIRD_RSS_FEEDS:
            message = await process_third_feed(session, url, status, third_bot)
            if message:
                await send_single_message(third_bot, TELEGRAM_CHAT_ID[0], message, True)

        for url in FOURTH_RSS_FEEDS:
            message = await process_fourth_feed(session, url, status, fourth_bot)
            if message:
                await send_single_message(fourth_bot, TELEGRAM_CHAT_ID[0], message)

        # 保存最新状态
        save_status(status)

if __name__ == "__main__":
    asyncio.run(main())
