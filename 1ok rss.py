import asyncio
import aiohttp
import aiomysql
import logging
import datetime
from feedparser import parse
import re
import os
from dotenv import load_dotenv
from telegram import Bot
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tmt.v20180321 import tmt_client, models
import queue


# 加载.env 文件
load_dotenv()

# RSS 源列表
RSS_FEEDS = [
    ('https://feeds.bbci.co.uk/news/world/rss.xml', 'BBC World News'),
    ('https://www.cnbc.com/id/100003114/device/rss/rss.html', 'CNBC'),
    ('https://feeds.a.dj.com/rss/RSSWorldNews.xml', '华尔街日报'),
    ('https://www.aljazeera.com/xml/rss/all.xml', '半岛电视台'),
    ('https://www3.nhk.or.jp/rss/news/cat6.xml', 'NHK World'),
    ('https://www3.nhk.or.jp/rss/news/cat5.xml', 'NHK 商业'),
    ('https://www.ft.com/?format=rss', '金融时报'),
]

SECOND_RSS_FEEDS = [
    # ('https://www.aljazeera.com/xml/rss/all.xml', '半岛电视台'),
]

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SECOND_TELEGRAM_BOT_TOKEN = os.getenv("SECOND_TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "").split(",")

# 数据库连接配置
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'db': os.getenv("DB_NAME"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'minsize': 1,
    'maxsize': 10
}

# 腾讯云翻译配置
TENCENTCLOUD_SECRET_ID = os.getenv("TENCENTCLOUD_SECRET_ID")
TENCENTCLOUD_SECRET_KEY = os.getenv("TENCENTCLOUD_SECRET_KEY")

# 消息队列，用于存储待翻译和推送的消息
message_queue = queue.Queue()


async def fetch_feed(session, feed):
    """异步获取 RSS 源内容。"""
    try:
        async with session.get(feed[0], timeout=15) as response:
            response.raise_for_status()
            content = await response.read()
            return parse(content)
    except Exception as e:
        logging.error(f"Error fetching {feed[0]}: {e}")
        return None


async def send_message(bot, chat_id, text, format_type='Markdown', chunk_size=4000, disable_preview=False):
    """发送消息到指定聊天 ID。"""
    try:
        if format_type == 'Markdown':
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                try:
                    kwargs = {'chat_id': chat_id, 'text': chunk, 'parse_mode': 'Markdown'}
                    if disable_preview:
                        kwargs['disable_web_page_preview'] = True
                    await bot.send_message(**kwargs)
                except Exception as e:
                    logging.error(f"Markdown format sending failed for chunk: {e}")
                    await bot.send_message(chat_id=chat_id, text=chunk)
        else:
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                await bot.send_message(chat_id=chat_id, text=chunk)
    except Exception as e:
        logging.error(f"Failed to send message: {e}")


async def process_feed(session, feed, sent_entries, pool, bot, allowed_chat_ids, table_name):
    """处理单个 RSS 源。"""
    feed_data = await fetch_feed(session, feed)
    if feed_data is None:
        return []

    new_entries = []
    messages = []

    for entry in feed_data.entries:
        subject = entry.title if entry.title else None
        url = entry.link if entry.link else None
        summary = entry.summary if hasattr(entry, 'summary') else "暂无简介"

        message_id = f"{subject}_{url}" if subject and url else None

        if (url, subject, message_id) not in sent_entries:
            original_message_parts = await create_message_parts(subject, summary, url, feed[1])
            combined_message = "\n\n".join(original_message_parts)
            messages.append(combined_message)
            new_entries.append((url, subject, message_id))

            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await save_sent_entry_to_db(
                pool,
                url if url else current_time,
                subject if subject else current_time,
                message_id if message_id else current_time,
                table_name
            )
            sent_entries.add((url, subject, message_id))

    if messages:
        combined_message = "\n\n".join(messages)
        message_queue.put((combined_message, bot, allowed_chat_ids))
    return new_entries


async def connect_to_db_pool():
    """连接到数据库池。"""
    try:
        return await aiomysql.create_pool(**DB_CONFIG)
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return None


async def load_sent_entries_from_db(pool, table_name):
    """从数据库加载已发送的条目。"""
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT url, subject, message_id FROM {table_name}")
                rows = await cursor.fetchall()
                return {(row[0], row[1], row[2]) for row in rows}
    except Exception as e:
        logging.error(f"Error loading sent entries: {e}")
        return set()


async def save_sent_entry_to_db(pool, url, subject, message_id, table_name):
    """将条目保存到数据库。"""
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"INSERT IGNORE INTO {table_name} (url, subject, message_id) VALUES (%s, %s, %s)",
                    (url, subject, message_id)
                )
                await conn.commit()
    except Exception as e:
        logging.error(f"Error saving entry: {e}")


async def translate_and_send():
    """翻译并发送消息。"""
    while True:
        try:
            message_data = message_queue.get()
            if message_data is None:
                break
            original_message, bot, allowed_chat_ids = message_data
            parts = original_message.split('\n\n')
            translated_message_parts = []
            for part in parts:
                if part.startswith("*"):
                    subject = part.replace('*', '').strip()
                    translated_subject = await auto_translate_text(subject)
                    translated_message_parts.append(f"*{translated_subject}*")
                else:
                    if not part.startswith("["):
                        translated_part = await auto_translate_text(part)
                        translated_message_parts.append(translated_part)
                    else:
                        translated_message_parts.append(part)
            translated_message = "\n\n".join(translated_message_parts)
            for chat_id in allowed_chat_ids:
                await send_message(bot, chat_id, translated_message, 'Markdown')
            await asyncio.sleep(6)
        except Exception as e:
            logging.error(f"Error in translation and sending: {e}")


async def auto_translate_text(text):
    """使用腾讯云翻译服务自动翻译文本。"""
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

        print(f"Sending translation request for text: {text}")
        resp = client.TextTranslate(req)
        return resp.TargetText
    except Exception as e:
        logging.error(f"Translation error for text '{text}': {e}")
        return text


def sanitize_markdown(text):
    """清理 Markdown 文本中的可能的 HTML 标签。"""
    # 移除可能的 HTML 标签
    cleaned_text = re.sub(r'<.*?>', '', text)
    return cleaned_text


async def create_message_parts(subject, summary, url, source_name):
    """创建消息的各个部分。"""
    original_message_parts = []
    if subject:
        translated_subject = await auto_translate_text(subject)
        original_message_parts.append(f"*{translated_subject}*")
    else:
        original_message_parts.append("*无标题*")

    if summary:
        translated_summary = await auto_translate_text(summary)
        original_message_parts.append(translated_summary)
    else:
        original_message_parts.append("无简介")

    if url:
        source_link = f"[{source_name}]({url})"
        original_message_parts.append(source_link)

    return original_message_parts


async def main():
    pool = await connect_to_db_pool()
    if not pool:
        logging.error("Failed to connect to the database.")
        return

    sent_entries = await load_sent_entries_from_db(pool, "sent_rss")
    sent_entries_second = await load_sent_entries_from_db(pool, "sent_rss2")

    async with aiohttp.ClientSession() as session:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        second_bot = Bot(token=SECOND_TELEGRAM_BOT_TOKEN)

        tasks = [
            process_feed(session, feed, sent_entries, pool, bot, ALLOWED_CHAT_IDS, "sent_rss")
            for feed in RSS_FEEDS
        ]
        tasks += [
            process_feed(session, feed, sent_entries_second, pool, second_bot, ALLOWED_CHAT_IDS, "sent_rss2")
            for feed in SECOND_RSS_FEEDS
        ]

        await asyncio.gather(*tasks)

        translation_task = asyncio.create_task(translate_and_send())

        await asyncio.sleep(0)

        message_queue.put(None)
        await translation_task

    pool.close()
    await pool.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())