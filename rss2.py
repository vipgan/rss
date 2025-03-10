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

# 加载.env文件
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
# 翻译主题和内容
RSS_FEEDS = [
  #  'https://feeds.bbci.co.uk/news/world/rss.xml', # bbc
    'https://www3.nhk.or.jp/rss/news/cat6.xml',  # nhk
  #  'https://www.cnbc.com/id/100003114/device/rss/rss.html', # CNBC
  #  'https://feeds.a.dj.com/rss/RSSWorldNews.xml', # 华尔街日报
  #  'https://www.aljazeera.com/xml/rss/all.xml',# 半岛电视台
  #  'https://www3.nhk.or.jp/rss/news/cat5.xml',# NHK 商业
  #  'https://www.ft.com/?format=rss', # 金融时报
  #  'http://rss.cnn.com/rss/edition.rss', # cnn
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw', # cnn
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCQeRaTukNYft1_6AZPACnog', # Asmongold TV
]
#主题+内容
THIRD_RSS_FEEDS = [
  #  'https://36kr.com/feed-newsflash',
  #  'https://rss.owo.nz/10jqka/realtimenews',
]
 # 主题+预览
FOURTH_RSS_FEEDS = [
    'https://blog.090227.xyz/atom.xml',
    'https://www.freedidi.com/feed',
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCUNciDq-y6I6lEQPeoP-R5A', # 苏恒观察
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCXkOTZJ743JgVhJWmNV8F3Q', # 寒國人
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC2r2LPbOUssIa02EbOIm7NA', # 星球熱點
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCF-Q1Zwyn9681F7du8DMAWg', # 謝宗桓-老謝來了
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCOSmkVK2xsihzKXQgiXPS4w', # 历史哥
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCSYBgX9pWGiUAcBxjnj6JCQ', # 郭正亮頻道
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCNiJNzSkfumLB7bYtXcIEmg', # 真的很博通
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCG_gH6S-2ZUOtEw27uIS_QA', # 7Car小七車觀點
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCJ5rBA0z4WFGtUTS83sAb_A', # POP Radio聯播網
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCN0eCImZY6_OiJbo8cy5bLw', # 屈機TV
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCb3TZ4SD_Ys3j4z0-8o6auA', # BBC News 中文
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCiwt1aanVMoPYUt_CQYCPQg', # 全球大視野
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC000Jn3HGeQSwBuX_cLDK8Q', # 我是柳傑克
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCQFEBaHCJrHu2hzDA_69WQg', # 国漫说
    'https://www.youtube.com/feeds/videos.xml?channel_id=UChJ8YKw6E1rjFHVS9vovrZw', # BNE TV - 新西兰中文国际频道

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

# 翻译主题+链接的
FIFTH_RSS_FEEDS = [
  #  'https://rsshub.app/twitter/media/elonmusk',  #elonmusk
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw', # cnn
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCQeRaTukNYft1_6AZPACnog', # Asmongold TV
]

# Telegram配置
TELEGRAM_BOT_TOKEN = os.getenv("RSS_TWO")  # bbc
RSS_TWO = os.getenv("RSS_TWO")
YOUTUBE_RSS = os.getenv("YOUTUBE_RSS")    # 10086
RSSTWO_TOKEN = os.getenv("YOUTUBE_RSS")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").split(",")
TENCENTCLOUD_SECRET_ID = os.getenv("TENCENTCLOUD_SECRET_ID")
TENCENTCLOUD_SECRET_KEY = os.getenv("TENCENTCLOUD_SECRET_KEY")

MAX_CONCURRENT_REQUESTS = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def remove_html_tags(text):
    """彻底移除HTML标签"""
    return re.sub(r'<[^>]*>', '', text)

def escape_markdown_v2(text, exclude=None):
    """自定义MarkdownV2转义函数"""
    if exclude is None:
        exclude = []
    chars = '_*[]()~`>#+-=|{}.!'
    chars_to_escape = [c for c in chars if c not in exclude]
    pattern = re.compile(f'([{"".join(map(re.escape, chars_to_escape))}])')
    return pattern.sub(r'\\\1', text)

async def send_single_message(bot, chat_id, text, disable_web_page_preview=False):
    try:
        MAX_MESSAGE_LENGTH = 4096
        text_chunks = []
        current_chunk = []
        current_length = 0

        # 按换行符分割保持段落结构
        paragraphs = text.split('\n\n')
        for para in paragraphs:
            para_length = len(para.encode('utf-8'))
            if current_length + para_length + 2 > MAX_MESSAGE_LENGTH:  # +2 是换行符
                text_chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_length = 0
            current_chunk.append(para)
            current_length += para_length + 2

        if current_chunk:
            text_chunks.append('\n\n'.join(current_chunk))

        for chunk in text_chunks:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode='MarkdownV2',
                disable_web_page_preview=disable_web_page_preview
            )
    except BadRequest as e:
        logging.error(f"消息发送失败(Markdown错误): {e} - 文本片段: {chunk[:200]}...")
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
    # 遍历新条目，添加序号
    for idx, entry in enumerate(reversed(new_entries), start=1):
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
        safe_subject = escape_markdown_v2(translated_subject, exclude=['*'])
        safe_summary = escape_markdown_v2(translated_summary)
        safe_source = escape_markdown_v2(source_name, exclude=['[', ']'])
        safe_url = escape_markdown_v2(raw_url)

        # 构建消息
        message = f"*{safe_subject}*\n{safe_summary}\n[{safe_source}]({safe_url})"
        merged_message += message + "\n\n"
    merged_message += f"✅ 新增 {len(new_entries)} 条内容"
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
    # 遍历新条目，添加序号
    for idx, entry in enumerate(reversed(new_entries), start=1):
        # 内容处理
        raw_subject = remove_html_tags(entry.title or "无标题")
        raw_summary = remove_html_tags(getattr(entry, 'summary', "暂无简介"))
        raw_url = entry.link

        # Markdown转义
        safe_subject = escape_markdown_v2(raw_subject, exclude=['*'])
        safe_summary = escape_markdown_v2(raw_summary)
        safe_source = escape_markdown_v2(source_name, exclude=['[', ']'])
        safe_url = escape_markdown_v2(raw_url)

        # 消息构建
        message_content = f"*{safe_subject}*\n{safe_summary}\n[{safe_source}]({safe_url})"
        message_bytes = message_content.encode('utf-8')

        if len(message_bytes) <= 555:
            merged_message += message_content + "\n\n"
        else:
            title_link = f"*{safe_subject}*\n[{safe_source}]({safe_url})"
            merged_message += title_link + "\n\n"
    merged_message += f"✅ 新增 {len(new_entries)} 条内容"
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
    feed_title = f"**{escape_markdown_v2(source_name, exclude=['*'])}**"  # 转义并加粗标题

    # 添加统计信息
    merged_message += f"📢 *{feed_title}*\n\n"

    # 遍历新条目，添加序号
    for idx, entry in enumerate(reversed(new_entries), start=1):
        # 内容处理
        raw_subject = remove_html_tags(entry.title or "无标题")
        raw_url = entry.link

        clean_subject = re.sub(r'[^\w\s\u4e00-\u9fa5.,!?;:"\'()\-]+', '', raw_subject).strip()
        # Markdown转义
        safe_subject = escape_markdown_v2(clean_subject, exclude=['*'])
        safe_url = escape_markdown_v2(raw_url)

        # 构建消息，添加序号
        merged_message += f"*{safe_subject}*\n🔗 {safe_url}\n\n"
    merged_message += f"✅ 新增 {len(new_entries)} 条内容"
    return merged_message

async def process_fifth_feed(session, feed_url, status, bot, translate=True):
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
    feed_title = f"**{escape_markdown_v2(source_name, exclude=['*'])}**"  # 转义并加粗标题

    # 添加统计信息
    merged_message += f"📢 *{feed_title}*\n\n"
    # 遍历新条目，添加序号
    for idx, entry in enumerate(reversed(new_entries), start=1):
        # 原始内容处理
        raw_subject = remove_html_tags(entry.title or "无标题")
        raw_url = entry.link

        # 翻译处理
        if translate:
            translated_subject = await auto_translate_text(raw_subject)
        else:
            translated_subject = raw_subject

        # Markdown转义
        safe_subject = escape_markdown_v2(translated_subject, exclude=['*'])
        safe_source = escape_markdown_v2(source_name, exclude=['[', ']'])
        safe_url = escape_markdown_v2(raw_url)

        # 构建消息, 只发送主题和链接
        message = f"*{safe_subject}*\n🔗 {safe_url}"
        merged_message += message + "\n\n"
    merged_message += f"✅ 新增 {len(new_entries)} 条内容"
    return merged_message

async def main():
    async with aiohttp.ClientSession() as session:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        third_bot = Bot(token=RSS_TWO)
        fourth_bot = Bot(token=YOUTUBE_RSS)
        fifth_bot = Bot(token=RSSTWO_TOKEN) 
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
        
        # 处理第五类源
        for url in FIFTH_RSS_FEEDS:
            if message := await process_fifth_feed(session, url, status, fifth_bot):
                await send_single_message(fifth_bot, TELEGRAM_CHAT_ID[0], message, False)  # 根据需要调整True不浏览

        save_status(status)

if __name__ == "__main__":
    asyncio.run(main())
