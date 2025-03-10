import asyncio
import aiohttp
import logging
import os
import re
import json
import html
from dotenv import load_dotenv
from feedparser import parse
from telegram import Bot
from telegram.constants import ParseMode

# 加载环境变量
load_dotenv()

# 配置参数
CONNECTION_POOL_SIZE = 10
REQUEST_TIMEOUT = 30
SEND_INTERVAL = 0.7
MAX_CONCURRENT_TASKS = 10

# RSS 源列表
RSS_FEEDS = [
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCvijahEyGtvMpmMHBu4FS2w', # 零度解说
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC96OvMh0Mb_3NmuE8Dpu7Gg', # 搞机零距离
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCQoagx4VHBw3HkAyzvKEEBA', # 科技共享
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCbCCUH8S3yhlm7__rhxR2QQ', # 不良林
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCMtXiCoKFrc2ovAGc1eywDg', # 一休 
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCii04BCvYIdQvshrdNDAcww', # 悟空的日常 
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCJMEiNh1HvpopPU3n9vJsMQ', # 理科男士 
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCYjB6uufPeHSwuHs8wovLjg', # 中指通 
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCSs4A6HYKmHA2MG_0z-F0xw', # 李永乐老师 
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCZDgXi7VpKhBJxsPuZcBpgA', # 可恩KeEn  
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCxukdnZiXnTFvjF5B5dvJ5w', # 甬哥侃侃侃ygkkk  
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCUfT9BAofYBKUTiEVrgYGZw', # 科技分享  
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC51FT5EeNPiiQzatlA2RlRA', # 乌客wuke  
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCDD8WJ7Il3zWBgEYBUtc9xQ', # jack stone  
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCWurUlxgm7YJPPggDz9YJjw', # 一瓶奶油
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCvENMyIFurJi_SrnbnbyiZw', # 酷友社
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCmhbF9emhHa-oZPiBfcLFaQ', # WenWeekly
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC3BNSKOaphlEoK4L7QTlpbA', # 中外观察
]

SECOND_RSS_FEEDS = [
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCUNciDq-y6I6lEQPeoP-R5A', # 苏恒观察
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCXkOTZJ743JgVhJWmNV8F3Q', # 寒國人
    'https://www.youtube.com/feeds/videos.xml?channel_id=UC2r2LPbOUssIa02EbOIm7NA', # 星球熱點
   # 'https://www.youtube.com/feeds/videos.xml?channel_id=UCF-Q1Zwyn9681F7du8DMAWg', # 謝宗桓-老謝來了
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCOSmkVK2xsihzKXQgiXPS4w', # 历史哥
    'https://www.youtube.com/feeds/videos.xml?channel_id=UCSYBgX9pWGiUAcBxjnj6JCQ', # 郭正亮頻道
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCNiJNzSkfumLB7bYtXcIEmg', # 真的很博通
 #   'https://www.youtube.com/feeds/videos.xml?channel_id=UCG_gH6S-2ZUOtEw27uIS_QA', # 7Car小七車觀點
  #  'https://www.youtube.com/feeds/videos.xml?channel_id=UCJ5rBA0z4WFGtUTS83sAb_A', # POP Radio聯播網
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

async def create_session():
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(
            limit=CONNECTION_POOL_SIZE,
            limit_per_host=5,
            ssl=False
        ),
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    )

async def fetch_feed(session, feed_url):
    try:
        async with session.get(feed_url) as response:
            response.raise_for_status()
            return parse(await response.read())
    except Exception as e:
        logging.error(f"抓取失败 {feed_url}: {e}")
        return None

async def send_message(bot, chat_id, text):
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False
        )
        await asyncio.sleep(SEND_INTERVAL)
    except Exception as e:
        logging.error(f"消息发送失败: {e}")
        for retry in range(3):
            try:
                await asyncio.sleep(2 ** retry)
                await bot.send_message(chat_id=chat_id, text=text)
                return
            except Exception:
                continue

async def process_feed(session, feed_url, bot, chat_ids, sent_urls, filename):
    try:
        feed_data = await fetch_feed(session, feed_url)
        if not feed_data or not hasattr(feed_data, 'feed'):
            return

        feed_title = html.escape(feed_data.feed.get('title', '未命名来源'))
        new_entries = []

        for entry in feed_data.entries:
            url = entry.get('link', '')
            if url and url not in sent_urls:
                title = html.escape(entry.get('title', '无标题'))
                title = re.sub(r'[^\w\s\u4e00-\u9fa5.,!?;:"\'()\-]+', '', title)
                new_entries.append(f"<b>{title}</b>\n{url}")
                sent_urls.add(url)

        if new_entries:
            message = f"【{feed_title}】更新\n\n" + "\n\n".join(new_entries)
            for chat_id in chat_ids:
                await send_message(bot, chat_id, message)
            await save_sent_urls(filename, sent_urls)

    except Exception as e:
        logging.error(f"处理源失败 {feed_url}: {e}")

async def main():
    session = await create_session()
    try:
        bot = Bot(os.getenv("RSS_TOKEN"))
        second_bot = Bot(os.getenv("YOUTUBE_RSS"))
        chat_ids = os.getenv("ALLOWED_CHAT_IDS", "").split(",")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        
        async def limited_task(feed_url, target_bot, filename):
            async with semaphore:
                sent_urls = await load_sent_urls(filename)
                await process_feed(session, feed_url, target_bot, chat_ids, sent_urls, filename)

        tasks = []
        for feed_group, target_bot, filename in [
            (RSS_FEEDS, bot, "youtube.json"),
            (SECOND_RSS_FEEDS, second_bot, "youtube1.json")
        ]:
            for feed_url in feed_group:
                tasks.append(limited_task(feed_url, target_bot, filename))

        await asyncio.gather(*tasks)
        
    finally:
        await session.close()

async def load_sent_urls(filename):
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return set(json.load(f))
    except Exception as e:
        logging.error(f"加载失败 {filename}: {e}")
    return set()

async def save_sent_urls(filename, urls):
    try:
        with open(filename, 'w') as f:
            json.dump(list(urls), f)
    except Exception as e:
        logging.error(f"保存失败 {filename}: {e}")

if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    asyncio.run(main())
