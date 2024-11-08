import asyncio
import aiohttp
import aiomysql
import logging
import datetime
from feedparser import parse
from telegram import Bot
import re

# 引入 config.py 配置
from config2 import (
    RSS_FEEDS, SECOND_RSS_FEEDS, TELEGRAM_BOT_TOKEN, SECOND_TELEGRAM_BOT_TOKEN,
    ALLOWED_CHAT_IDS, DB_CONFIG
)

async def fetch_feed(session, feed):
    try:
        async with session.get(feed, timeout=88) as response:
            response.raise_for_status()
            content = await response.read()
            return parse(content)
    except Exception as e:
        logging.error(f"Error fetching {feed}: {e}")
        return None

async def send_message(bot, chat_id, text, chunk_size=4000):
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        try:
            # 直接用纯文本推送消息
            await bot.send_message(chat_id=chat_id, text=chunk)
        except Exception as e:
            logging.error(f"Failed to send message: {e}")

async def process_feed(session, feed, sent_entries, pool, bot, allowed_chat_ids, table_name):
    feed_data = await fetch_feed(session, feed)
    if feed_data is None:
        return []

    new_entries = []
    messages = []  # 用于存储新条目的消息

    for entry in feed_data.entries:
        subject = entry.title if entry.title else None
        url = entry.link if entry.link else None

        # 使用正则表达式去除主题中的特殊符号
        if subject:
            subject = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]+', '', subject)  # 保留中英文及数字

        message_id = f"{subject}_{url}" if subject and url else None

        if (url, subject, message_id) not in sent_entries:
            message = f"{subject}\n{url}"  # 使用清理后的标题
            messages.append(message)
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

    # 合并为一个消息进行推送
    if messages:
        combined_message = "\n\n".join(messages)
        for chat_id in allowed_chat_ids:
            await send_message(bot, chat_id, combined_message)
        await asyncio.sleep(6)  # 避免触发 Telegram API 速率限制

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
                    f"INSERT IGNORE INTO {table_name} (url, subject, message_id) VALUES (%s, %s, %s)",
                    (url, subject, message_id)
                )
                await conn.commit()
    except Exception as e:
        logging.error(f"Error saving entry: {e}")

async def main():
    pool = await connect_to_db_pool()
    if not pool:
        logging.error("Failed to connect to the database.")
        return

    sent_entries = await load_sent_entries_from_db(pool, "sent_rss")
    sent_entries_second = await load_sent_entries_from_db(pool, "sent_youtube")

    async with aiohttp.ClientSession() as session:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        second_bot = Bot(token=SECOND_TELEGRAM_BOT_TOKEN)

        tasks = [
            process_feed(session, feed, sent_entries, pool, bot, ALLOWED_CHAT_IDS, "sent_rss")
            for feed in RSS_FEEDS
        ]
        tasks += [
            process_feed(session, feed, sent_entries_second, pool, second_bot, ALLOWED_CHAT_IDS, "sent_youtube")
            for feed in SECOND_RSS_FEEDS
        ]

        await asyncio.gather(*tasks)

    pool.close()
    await pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
