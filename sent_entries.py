import asyncio
import aiohttp
import logging
import os
import json
from feedparser import parse
from dotenv import load_dotenv
from telegram import Bot
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tmt.v20180321 import tmt_client, models
import queue
import re

# 加载.env 文件
load_dotenv()

# RSS 源列表
RSS_FEEDS = [
    ('https://feeds.bbci.co.uk/news/world/rss.xml', 'BBC'),
    ('https://www3.nhk.or.jp/rss/news/cat6.xml', 'NHK'),
  #  ('https://www.cnbc.com/id/100003114/device/rss/rss.html', 'CNBC'),
  #  ('https://feeds.a.dj.com/rss/RSSWorldNews.xml', '华尔街日报'),
  #  ('https://www.aljazeera.com/xml/rss/all.xml', '半岛电视台'),
  #  ('https://www3.nhk.or.jp/rss/news/cat5.xml', 'NHK 商业'),
  #  ('https://www.ft.com/?format=rss', '金融时报'),
  #  ('https://www.aljazeera.com/xml/rss/all.xml', '半岛电视台'),


]

SECOND_RSS_FEEDS = [
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCUNciDq-y6I6lEQPeoP-R5A', # 苏恒观察
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCXkOTZJ743JgVhJWmNV8F3Q', # 寒國人
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC2r2LPbOUssIa02EbOIm7NA', # 星球熱點
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCF-Q1Zwyn9681F7du8DMAWg', # 謝宗桓-老謝來了
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCOSmkVK2xsihzKXQgiXPS4w', # 历史哥
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCSYBgX9pWGiUAcBxjnj6JCQ', # 郭正亮頻道
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCNiJNzSkfumLB7bYtXcIEmg', # 真的很博通
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCG_gH6S-2ZUOtEw27uIS_QA', # 7Car小七車觀點
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCJ5rBA0z4WFGtUTS83sAb_A', # POP Radio聯播網
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCiwt1aanVMoPYUt_CQYCPQg', # 全球大視野
 
    

# 影视
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC7Xeh7thVIgs_qfTlwC-dag', # Marc TV
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCqWNOHjgfL8ADEdXGznzwUw', # 悦耳音乐酱
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCCD14H7fJQl3UZNWhYMG3Mg', # 温城鲤
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCQO2T82PiHCYbqmCQ6QO6lw', # 月亮說
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCKyDmY3R_xGKz8IjvbijiHA', # 珊珊追剧社
    'https://www.youtube.com/feeds/videos.xml?channel_id=UClyVC2wh_2fQhU0hPdXA4rw', # 热门古风曲
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC1ISajIKfRN359MMmtckUTg', # Taiwanese Pop Mix
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCQFyMGc6h30NMCd6HCk0ZPA', # 哔哩哔哩动画
]

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RSSTWO_TELEGRAM_BOT_TOKEN = os.getenv("RSSTWO_TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "").split(",")

# 腾讯云翻译配置
TENCENTCLOUD_SECRET_ID = os.getenv("TENCENTCLOUD_SECRET_ID")
TENCENTCLOUD_SECRET_KEY = os.getenv("TENCENTCLOUD_SECRET_KEY")

# 消息队列，用于存储待翻译和推送的消息
message_queue = queue.Queue()

# 存储sent_entries的文件路径
SENT_ENTRIES_FILE = 'sent_entries.json'

def load_sent_entries():
    """加载已发送的条目，如果文件不存在则返回空集合"""
    if os.path.exists(SENT_ENTRIES_FILE):
        try:
            with open(SENT_ENTRIES_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Error loading sent entries from file: {e}")
            return set()
    else:
        # 如果文件不存在，返回空集合并创建文件
        return set()

def save_sent_entries(sent_entries):
    """将已发送的条目保存到本地文件"""
    try:
        with open(SENT_ENTRIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(sent_entries), f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving sent entries to file: {e}")

# 用于记录已发送消息的标志位集合
sent_entries = load_sent_entries()

async def fetch_feed(session, feed):
    try:
        async with session.get(feed[0], timeout=30) as response:
            response.raise_for_status()
            content = await response.read()
            return parse(content)
    except Exception as e:
        logging.error(f"Error fetching {feed[0]}: {e}")
        return None

async def send_single_message(bot, chat_id, text, format_type='HTML', disable_preview=False):
    try:
        # 拆分消息，确保每条消息不会超过 4096 字节
        for chunk in split_message(text):
            kwargs = {'chat_id': chat_id, 'text': chunk, 'parse_mode': format_type}
            if disable_preview:
                kwargs['disable_web_page_preview'] = True
            await bot.send_message(**kwargs)
    except Exception as e:
        logging.error(f"Failed to send single message in {format_type} format: {e}")
        # 失败时用原文推送
        for chunk in split_message(text):
            await bot.send_message(chat_id=chat_id, text=chunk)

async def process_feed(session, feed, bot, allowed_chat_ids, translate=True, only_title_and_link=False):
    feed_data = await fetch_feed(session, feed)
    if feed_data is None:
        return

    messages = []
    for entry in feed_data.entries:
        subject = entry.title or "*无标题*"
        url = entry.link
        summary = getattr(entry, 'summary', "暂无简介")
        message_id = f"{subject}_{url}"

        # 使用标志位集合判断是否发送过
        if message_id not in sent_entries:
            translated_subject = await auto_translate_text(subject) if translate else subject
            if only_title_and_link:
                combined_message = f"<b>{translated_subject}</b>\n\n<a href='{url}'>{feed[1]}</a>"
            else:
                translated_summary = await auto_translate_text(summary) if translate else summary
                combined_message = f"<b>{translated_subject}</b>\n\n{sanitize_html(translated_summary)}\n\n<a href='{url}'>{feed[1]}</a>"

            messages.append(combined_message)
            sent_entries.add(message_id)  # 更新标志位集合

    for message in messages:
        for chat_id in allowed_chat_ids:
            await send_single_message(bot, chat_id, message)

    # 每次发送完消息后，保存已发送条目
    save_sent_entries(sent_entries)

async def auto_translate_text(text):
    try:
        cred = credential.Credential(TENCENTCLOUD_SECRET_ID, TENCENTCLOUD_SECRET_KEY)
        httpProfile = HttpProfile()
        httpProfile.endpoint = "tmt.tencentcloudapi.com"

        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        client = tmt_client.TmtClient(cred, "ap-guangzhou", clientProfile)

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

def sanitize_html(text):
    # 删除Telegram不支持的HTML标签，保留图片、视频链接
    text = re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', r'<a href="\1">Image</a>', text)  # 图片标签只保留链接
    text = re.sub(r'<video[^>]*src="([^"]+)"[^>]*>', r'<a href="\1">Video</a>', text)  # 视频标签只保留链接
    # 删除其他不必要的HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    return text

def split_message(text, limit=4096):
    """确保消息不超过 Telegram 的字符限制"""
    # 如果消息长度大于限制，拆分消息
    if len(text) <= limit:
        return [text]
    
    # 按字符限制拆分消息
    chunks = []
    while len(text) > limit:
        # 查找最后一个可以切割的位置
        cut_pos = text.rfind(' ', 0, limit)
        if cut_pos == -1:  # 如果没有找到空格，直接截断
            cut_pos = limit
        chunks.append(text[:cut_pos])
        text = text[cut_pos:].strip()
    
    # 添加剩余部分
    if text:
        chunks.append(text)
    
    return chunks

async def main():
    async with aiohttp.ClientSession() as session:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        second_bot = Bot(token=RSSTWO_TELEGRAM_BOT_TOKEN)

        tasks = [
            process_feed(session, feed, bot, ALLOWED_CHAT_IDS, translate=True)
            for feed in RSS_FEEDS
        ] + [
            process_feed(session, feed, second_bot, ALLOWED_CHAT_IDS, translate=False, only_title_and_link=True)
            for feed in SECOND_RSS_FEEDS
        ]

        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
