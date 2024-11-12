import os
import asyncio
import aiohttp
import aiomysql
import logging
from dotenv import load_dotenv
from feedparser import parse
from telegram import Bot
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tmt.v20180321 import tmt_client, models

# Load environment variables
load_dotenv()

# RSS Feeds
RSS_FEEDS = [
    ('https://feeds.bbci.co.uk/news/world/rss.xml', 'BBC World'),
  #  ('https://www.cnbc.com/id/100003114/device/rss/rss.html', 'CNBC'),
  #  ('https://feeds.a.dj.com/rss/RSSWorldNews.xml', '华尔街日报'),
  #  ('https://www.aljazeera.com/xml/rss/all.xml', '半岛电视台'),
    ('https://www3.nhk.or.jp/rss/news/cat6.xml', 'NHK World'),
  #  ('https://www3.nhk.or.jp/rss/news/cat5.xml', 'NHK 商业'),
  #  ('https://www.ft.com/?format=rss', '金融时报'),

]

SECOND_RSS_FEEDS = [
    # ('https://www.aljazeera.com/xml/rss/all.xml', '半岛电视台'),

]

# Telegram Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SECOND_TELEGRAM_BOT_TOKEN = os.getenv("SECOND_TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "").split(",")

# Database Config
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'db': os.getenv("DB_NAME"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'minsize': 1,
    'maxsize': 10
}

# Tencent Cloud Translation Config
TENCENTCLOUD_SECRET_ID = os.getenv("TENCENTCLOUD_SECRET_ID")
TENCENTCLOUD_SECRET_KEY = os.getenv("TENCENTCLOUD_SECRET_KEY")

# Message queue for translating and pushing messages
message_queue = asyncio.Queue()

async def auto_translate_text(text):
    """Automatically translate text to Chinese."""
    try:
        cred = credential.Credential(TENCENTCLOUD_SECRET_ID, TENCENTCLOUD_SECRET_KEY)
        http_profile = HttpProfile(endpoint="tmt.tencentcloudapi.com")
        client_profile = ClientProfile(httpProfile=http_profile)
        client = tmt_client.TmtClient(cred, "ap-guangzhou", client_profile)

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

async def fetch_feed(session, feed):
    try:
        async with session.get(feed[0], timeout=15) as response:
            response.raise_for_status()
            content = await response.read()
            return parse(content)
    except Exception as e:
        logging.error(f"Error fetching {feed[0]}: {e}")
        return None

async def send_single_message(bot, chat_id, text, format_type='Markdown', disable_preview=False):
    try:
        kwargs = {'chat_id': chat_id, 'text': text, 'parse_mode': format_type}
        if disable_preview:
            kwargs['disable_web_page_preview'] = True
        await bot.send_message(**kwargs)
        logging.info(f"Message sent to {chat_id}: {text}")
    except Exception as e:
        logging.error(f"Failed to send single message: {e}")

async def process_feed(session, feed, sent_entries, pool, bot, allowed_chat_ids, table_name):
    feed_data = await fetch_feed(session, feed)
    if feed_data is None:
        return []

    new_entries = []
    messages = []

    for entry in feed_data.entries:
        subject = entry.title or "*无标题*"
        url = entry.link
        summary = getattr(entry, 'summary', "暂无简介")
        message_id = f"{subject}_{url}"

        if (url, subject, message_id) not in sent_entries:
            translated_subject = await auto_translate_text(subject)
            translated_summary = await auto_translate_text(summary)

            combined_message = f"*{translated_subject}*\n\n{translated_summary}\n\n[{feed[1]}]({url})"
            messages.append(combined_message)
            new_entries.append((url, subject, message_id))

            await save_sent_entry_to_db(pool, url, subject, message_id, table_name)
            sent_entries.add((url, subject, message_id))

    for message in messages:
        for chat_id in allowed_chat_ids:
            await send_single_message(bot, chat_id, message)

    return new_entries

async def connect_to_db_pool():
    try:
        return await aiomysql.create_pool(**DB_CONFIG)
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return None

async def load_sent_entries_from_db(pool, table_name):
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
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"INSERT INTO {table_name} (url, subject, message_id) VALUES (%s, %s, %s) "
                    f"ON DUPLICATE KEY UPDATE subject=VALUES(subject)",
                    (url, subject, message_id)
                )
                await conn.commit()
                logging.info(f"Saved entry to {table_name}: {url} - {subject}")
    except Exception as e:
        logging.error(f"Error saving entry: {e}")

async def main():
    pool = await connect_to_db_pool()
    if not pool:
        logging.error("Failed to connect to the database.")
        return

    async with pool:
        sent_entries = await load_sent_entries_from_db(pool, "sent_rss")
        sent_entries_second = await load_sent_entries_from_db(pool, "sent_rss2")

        async with aiohttp.ClientSession() as session:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            second_bot = Bot(token=SECOND_TELEGRAM_BOT_TOKEN)

            tasks = [
                process_feed(session, feed, sent_entries, pool, bot, ALLOWED_CHAT_IDS, "sent_rss")
                for feed in RSS_FEEDS
            ] + [
                process_feed(session, feed, sent_entries_second, pool, second_bot, ALLOWED_CHAT_IDS, "sent_rss2")
                for feed in SECOND_RSS_FEEDS
            ]

            await asyncio.gather(*tasks)

        pool.close()
        await pool.wait_closed()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
