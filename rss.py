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
import urllib.parse

# 加载.env 文件
load_dotenv()

# rss 翻译单独推送
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
# rss2 不翻译单独推送(仅标题来源)
SECOND_RSS_FEEDS = [
# new
  #  ('https://rsshub.penggan0.us.kg/guancha/headline', '观察网'),
  #  ('https://rsshub.penggan0.us.kg/zaobao/znews/china', '联合早报'),
  #  ('https://rsshub.penggan0.us.kg/zaobao/realtime/world', '联合早报国际'),


# youtube
  #  ('https://www.youtube.com/feeds/videos.xml?channel_id=UCb3TZ4SD_Ys3j4z0-8o6auA', 'BBC 中文'),
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UC000Jn3HGeQSwBuX_cLDK8Q', '我是柳傑克'),
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCvijahEyGtvMpmMHBu4FS2w', '零度解说'),
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UC96OvMh0Mb_3NmuE8Dpu7Gg', '搞机零距离'),
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCQoagx4VHBw3HkAyzvKEEBA', '科技共享'),
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCbCCUH8S3yhlm7__rhxR2QQ', '不良林'),
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCMtXiCoKFrc2ovAGc1eywDg', '一休'), 
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCii04BCvYIdQvshrdNDAcww', '悟空的日常'), 
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCJMEiNh1HvpopPU3n9vJsMQ', '理科男士'), 
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCYjB6uufPeHSwuHs8wovLjg', '中指通'), 
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCSs4A6HYKmHA2MG_0z-F0xw', '李永乐老师'), 
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCZDgXi7VpKhBJxsPuZcBpgA', '可恩KeEn'),  
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCxukdnZiXnTFvjF5B5dvJ5w', '甬哥侃侃侃ygkkk'),  
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCUfT9BAofYBKUTiEVrgYGZw', '科技分享'),  
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UC51FT5EeNPiiQzatlA2RlRA', '乌客wuke'),  
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCDD8WJ7Il3zWBgEYBUtc9xQ', 'jack stone'),  
    ('https://www.youtube.com/feeds/videos.xml?channel_id=UCWurUlxgm7YJPPggDz9YJjw', '一瓶奶油'),  

# bolg
    ('https://blog.090227.xyz/atom.xml', 'CM'),  
    ('https://www.freedidi.com/feed', '零度解说'),

]

# rss3 不翻译合并推送
THIRD_RSS_FEEDS = [
    ('https://36kr.com/feed', '36氪'),
    ('https://rsshub.penggan0.us.kg/10jqka/realtimenews', '同花顺x24'),
]

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RSSTWO_TELEGRAM_BOT_TOKEN = os.getenv("RSSTWO_TELEGRAM_BOT_TOKEN")
SANG_TELEGRAM_BOT_TOKEN = os.getenv("SANG_TELEGRAM_BOT_TOKEN")  # 新的 Telegram 机器人 token
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

def sanitize_markdown(text):
    """移除 Telegram 不支持的 Markdown 符号"""
    # 清理文本中的 Markdown 特殊字符
    cleaned_text = re.sub(r'[*_`|#\[\](){}<>]', '', text)
    return cleaned_text

async def fetch_feed(session, feed):
    try:
        async with session.get(feed[0], timeout=30) as response:
            response.raise_for_status()
            content = await response.read()
            return parse(content)
    except Exception as e:
        logging.error(f"Error fetching {feed[0]}: {e}")
        return None

MAX_MESSAGE_SIZE = 4096  # Telegram 字符串最大字节数限制

def split_message(text):
    """将消息按字节拆分为多个部分，以适应 Telegram 的字节限制"""
    # 判断消息长度是否超过限制
    if len(text.encode('utf-8')) <= MAX_MESSAGE_SIZE:
        return [text]
    
    # 如果消息太长，将其按最大长度拆分
    split_messages = []
    while len(text.encode('utf-8')) > MAX_MESSAGE_SIZE:
        split_point = MAX_MESSAGE_SIZE
        while text[split_point] not in [' ', '\n']:  # 尝试在空格或换行符拆分
            split_point -= 1
        split_messages.append(text[:split_point])
        text = text[split_point:].lstrip()
    
    if text:
        split_messages.append(text)
    
    return split_messages

async def send_single_message(bot, chat_id, text, format_type='Markdown', disable_preview=False):
    """发送消息，处理字节限制"""
    try:
        # 按字节拆分消息
        split_texts = split_message(text)
        
        # 逐个发送拆分后的消息
        for text_part in split_texts:
            if format_type == 'Markdown':
                try:
                    kwargs = {'chat_id': chat_id, 'text': text_part, 'parse_mode': 'Markdown'}
                    if disable_preview:
                        kwargs['disable_web_page_preview'] = True
                    await bot.send_message(**kwargs)
                except Exception as e:
                    logging.error(f"Markdown format sending failed: {e}")
                    await bot.send_message(chat_id=chat_id, text=text_part)
            else:
                await bot.send_message(chat_id=chat_id, text=text_part)
    except Exception as e:
        logging.error(f"Failed to send single message: {e}")

async def process_feed(session, feed, sent_entries, pool, bot, allowed_chat_ids, table_name, translate=True, only_title_and_link=False):
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
            if translate:
                translated_subject = await auto_translate_text(subject)
            else:
                translated_subject = subject

            # 清理主题中的不支持的 Markdown 符号
            cleaned_subject = sanitize_markdown(translated_subject)
                 # 如果 URL 存在，进行 URL 编码
            if url:
                url = urllib.parse.quote(url, safe=':/?&=#~')  # 对 URL 进行编码，保留常见的特殊字符
            # 根据only_title_and_link参数决定是否包含摘要
            if only_title_and_link:
                combined_message = f"*{cleaned_subject}*\n[{feed[1]}]({url})"
            else:
                translated_summary = await auto_translate_text(summary) if translate else summary
                combined_message = f"*{cleaned_subject}*\n{translated_summary}\n[{feed[1]}]({url})"
            
            messages.append(combined_message)
            new_entries.append((url, subject, message_id))

            await save_sent_entry_to_db(pool, url, subject, message_id, table_name)
            sent_entries.add((url, subject, message_id))

    # 处理消息字节限制
    for message in messages:
        for chat_id in allowed_chat_ids:
            await send_single_message(bot, chat_id, message)

    return new_entries

async def process_third_feed(session, feed, sent_entries, pool, bot, allowed_chat_ids, table_name):
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
            # 清理主题中的不支持的 Markdown 符号
            cleaned_subject = sanitize_markdown(subject)

            combined_message = f"*{cleaned_subject}*\n{summary}\n[{feed[1]}]({url})"
            messages.append(combined_message)
            new_entries.append((url, subject, message_id))

            await save_sent_entry_to_db(pool, url, subject, message_id, table_name)
            sent_entries.add((url, subject, message_id))

    # 合并所有消息并推送到第三个 Telegram 机器人
    combined_message = "\n\n".join(messages)
    third_bot = Bot(token=SANG_TELEGRAM_BOT_TOKEN)  # 使用新的 Telegram 机器人
    for chat_id in allowed_chat_ids:
        await send_single_message(third_bot, chat_id, combined_message)

    return new_entries

async def process_third_feed(session, feed, sent_entries, pool, bot, allowed_chat_ids, table_name):
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
            # 清理主题中的不支持的 Markdown 符号
            cleaned_subject = sanitize_markdown(subject)

            combined_message = f"*{cleaned_subject}*\n{summary}\n{feed[1]}\n\n"
            messages.append(combined_message)
            new_entries.append((url, subject, message_id))

            await save_sent_entry_to_db(pool, url, subject, message_id, table_name)
            sent_entries.add((url, subject, message_id))

    # 合并所有消息并推送到第三个 Telegram 机器人
    combined_message = "\n\n".join(messages)
    third_bot = Bot(token=SANG_TELEGRAM_BOT_TOKEN)  # 使用新的 Telegram 机器人
    for chat_id in allowed_chat_ids:
        await send_single_message(third_bot, chat_id, combined_message)

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

        print(f"Sending translation request for text: {text}")
        resp = client.TextTranslate(req)
        return resp.TargetText
    except Exception as e:
        logging.error(f"Translation error for text '{text}': {e}")
        return text

async def main():
    pool = await connect_to_db_pool()
    if not pool:
        logging.error("Failed to connect to the database.")
        return

    async with pool:
        sent_entries = await load_sent_entries_from_db(pool, "sent_rss")
        sent_entries_second = await load_sent_entries_from_db(pool, "sent_rss2")
        sent_entries_third = await load_sent_entries_from_db(pool, "sent_rss3")

        async with aiohttp.ClientSession() as session:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            second_bot = Bot(token=RSSTWO_TELEGRAM_BOT_TOKEN)

            tasks = [
                process_feed(session, feed, sent_entries, pool, bot, ALLOWED_CHAT_IDS, "sent_rss", translate=True)
                for feed in RSS_FEEDS
            ] + [
                process_feed(session, feed, sent_entries_second, pool, second_bot, ALLOWED_CHAT_IDS, "sent_rss2", translate=False, only_title_and_link=True)
                for feed in SECOND_RSS_FEEDS
            ] + [
                process_third_feed(session, feed, sent_entries_third, pool, second_bot, ALLOWED_CHAT_IDS, "sent_rss3")
                for feed in THIRD_RSS_FEEDS
            ]

            await asyncio.gather(*tasks)

        pool.close()
        await pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
