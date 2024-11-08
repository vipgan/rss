import asyncio
import aiohttp
import aiomysql
import logging
from feedparser import parse
from telegram import Bot
from config import (
    RSS_FEEDS, SECOND_RSS_FEEDS, TELEGRAM_BOT_TOKEN, SECOND_TELEGRAM_BOT_TOKEN,
    ALLOWED_CHAT_IDS, DB_CONFIG, auto_translate_text
)

# 消息队列，用于存储待翻译和推送的消息
message_queue = asyncio.Queue()

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

        # 仅处理未发送过的条目
        if (url, subject, message_id) not in sent_entries:
            translated_subject = await auto_translate_text(subject)
            translated_summary = await auto_translate_text(summary)

            combined_message = f"*{translated_subject}*\n\n{translated_summary}\n\n[{feed[1]}]({url})"
            messages.append(combined_message)
            new_entries.append((url, subject, message_id))

            await save_sent_entry_to_db(pool, url, subject, message_id, table_name)
            sent_entries.add((url, subject, message_id))

    # 发送消息
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
        # 载入已发送记录，避免重复处理
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