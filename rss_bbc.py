import asyncio
import aiohttp
import logging
import re
import os
import json
from datetime import datetime
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
    'https://feeds.bbci.co.uk/news/world/rss.xml',  # bbc
    # 'https://www3.nhk.or.jp/rss/news/cat6.xml',  # nhk
    # 'http://www3.nhk.or.jp/rss/news/cat5.xml',  # nhk金融
    # 'https://www.cnbc.com/id/100003114/device/rss/rss.html',  # CNBC
    # 'https://feeds.a.dj.com/rss/RSSWorldNews.xml',  # 华尔街日报
    # 'https://www.aljazeera.com/xml/rss/all.xml',  # 半岛电视台
    # 'https://www.ft.com/?format=rss',  # 金融时报
    # 'http://rss.cnn.com/rss/edition.rss',  # cnn
]

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv("RSS_TWO")  # bbc
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").split(",")

# 本地文件存储配置
SENT_ENTRIES_FILE = "rss.json"

TENCENTCLOUD_SECRET_ID = os.getenv("TENCENTCLOUD_SECRET_ID")
TENCENTCLOUD_SECRET_KEY = os.getenv("TENCENTCLOUD_SECRET_KEY")

MAX_ENTRIES_TO_KEEP = 900    #本地保存条目
TELEGRAM_DELAY = 0.5  # 发送消息后的延迟时间（秒）
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 1  # 初始重试延迟（秒）


def sanitize_markdown(text):
    # 首先去除 HTML 标签
    text = re.sub(r'<[^>]*>', '', text)
    # 然后去除 Telegram 不支持的 Markdown 符号
    text = re.sub(r'[*_`|#\\[\\](){}<>~+\-=!@%^&]', '', text)
    return text


async def send_single_message(bot, chat_id, text, disable_web_page_preview=False, retry_count=0):
    try:
        # Telegram 最大消息字节数限制：4096字节
        MAX_MESSAGE_LENGTH = 4096
        # 计算消息的字节数
        if len(text.encode('utf-8')) > MAX_MESSAGE_LENGTH:
            # 如果超长，拆分为多个消息
            for i in range(0, len(text), MAX_MESSAGE_LENGTH):
                await bot.send_message(
                    chat_id=chat_id,
                    text=text[i:i + MAX_MESSAGE_LENGTH],
                    parse_mode='Markdown',
                    disable_web_page_preview=disable_web_page_preview
                )
                await asyncio.sleep(TELEGRAM_DELAY)  # 添加延迟
        else:
            # 如果没有超长，直接发送
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown',
                disable_web_page_preview=disable_web_page_preview
            )
            await asyncio.sleep(TELEGRAM_DELAY)  # 添加延迟
    except Exception as e:
        logging.error(f"Failed to send message (attempt {retry_count + 1}): {e}")
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
        async with session.get(feed_url, headers=headers, timeout=60) as response:  # 增加超时时间
            response.raise_for_status()
            content = await response.read()
            return parse(content)
    except aiohttp.ClientError as e:
        logging.error(f"Error fetching {feed_url} (attempt {retry_count + 1}): {e}")
        if retry_count < MAX_RETRIES:
            delay = RETRY_DELAY * (2 ** retry_count)
            logging.info(f"Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
            return await fetch_feed(session, feed_url, retry_count + 1)
        else:
            logging.error(f"Max retries exceeded for feed: {feed_url}")
            return None
    except Exception as e:
        logging.error(f"Error fetching {feed_url} (attempt {retry_count + 1}): {e}")
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

        if url in sent_entries:
            continue  # 如果链接已存在，跳过当前条目

        if translate:
            translated_subject = await auto_translate_text(subject)
            translated_summary = await auto_translate_text(summary)
        else:
            translated_subject = subject
            translated_summary = summary

        cleaned_subject = sanitize_markdown(translated_subject)
        message = f"*{cleaned_subject}*\n{translated_summary}\n[{source_name}]({url})"
        try:
            await send_single_message(bot, TELEGRAM_CHAT_ID[0], message)
        except Exception as e:
            logging.error(f"Error sending message for subject '{cleaned_subject}': {e}")

        new_entries.append((url, subject))
        sent_entries.add(url)
        await save_sent_entries(sent_entries, file_path)

    return new_entries


# 加载本地保存的已发送条目
def load_sent_entries(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 将加载的数据转换为集合，并限制大小
                return set(data[-MAX_ENTRIES_TO_KEEP:])
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
            json.dump(
                entries_to_save,  # 将要序列化的数据作为第一个参数
                f,               # 文件对象作为第二个参数
                ensure_ascii=False,
                indent=4
            )
    except Exception as e:
        logging.error(f"Error saving sent entries to {file_path}: {e}")


async def main():
    sent_entries = load_sent_entries(SENT_ENTRIES_FILE)

    connector = aiohttp.TCPConnector(limit=200)  # 增加连接池大小
    async with aiohttp.ClientSession(connector=connector) as session:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        tasks = [
            process_feed(session, feed_url, sent_entries, bot, SENT_ENTRIES_FILE, translate=True)
            for feed_url in RSS_FEEDS
        ]

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
