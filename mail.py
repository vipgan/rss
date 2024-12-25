import imaplib
import email
import requests
import re
import logging
from datetime import datetime
import pytz
from email.utils import parsedate_to_datetime
from telegram import Bot
from telegram.constants import ParseMode
from email.utils import parseaddr
import os
from dotenv import load_dotenv
import hashlib
import html
import asyncio
from bs4 import BeautifulSoup

# 设置日志记录并分级
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# 加载 .env 文件
load_dotenv()

# 从环境变量获取配置信息
email_user = os.getenv("EMAIL_USER")
email_password = os.getenv("EMAIL_PASSWORD")
imap_server = os.getenv("IMAP_SERVER")

TELEGRAM_API_KEY = os.getenv("TELEGRAM_API_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 初始化 Telegram Bot
bot = Bot(token=TELEGRAM_API_KEY)

# 获取邮件哈希值
def get_email_hash(msg):
    subject = clean_subject(decode_header(msg['subject']))
    body = get_email_body(msg)
    return hashlib.md5((subject + body).encode('utf-8')).hexdigest()

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        fragment.decode(encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# 清理邮件主题
def clean_subject(subject):
    """
    清理邮件主题，去除 HTML 标签、Markdown 格式标签（如 *、_）以及特殊字符和方括号 [ ]。
    """
    # 去除 HTML 标签
    subject = re.sub(r'<[^>]+>', '', subject)
    
    # 去除 Markdown 中的星号 * 和下划线 _
    subject = re.sub(r'(\*|_)+', '', subject)
    
    # 去除特殊字符和方括号
    subject = re.sub(r'[^\w\s]', '', subject).replace('[', '').replace(']', '')
    
    return subject

def clean_email_body(body):
    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(body, 'html.parser')
    # 获取文本内容
    text = soup.get_text()
    # 去除多余的空白和连字符
    text = re.sub(r'-{2,}', '-', text)
    text = re.sub(r'—{4,}', '-' * 8, text)
    # 新增代码：去除文本中的 * 符号
    text = text.replace('*', '-')
    # 新增代码：去除文本中的 _ 符号
    text = text.replace('```', '-')
    text = text.replace('~', '-')
    text = text.replace('_', '-')
    # 处理连续的空行
    text = re.sub(r'\n\s*\n+', '\n', text)
    return text.strip()

# 获取邮件正文
def get_email_body(msg):
    """
    从邮件中提取正文内容，支持多部分格式。
    """
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            charset = part.get_content_charset() or 'utf-8'
            
            if content_type in ['text/html', 'text/plain']:
                body = part.get_payload(decode=True).decode(charset, errors='ignore')
                break
    else:
        charset = msg.get_content_charset() or 'utf-8'
        body = msg.get_payload(decode=True).decode(charset, errors='ignore')
        
    return clean_email_body(body)

# 发送消息到 Telegram
async def send_message(text):
    try:
        MAX_MESSAGE_LENGTH = 4096
        messages = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
        
        for message_part in messages:
            try:
                # 发送消息并处理 Markdown 格式
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_part, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                logger.info(f"消息以 Markdown 格式成功发送: {message_part[:50]}...")
            except Exception as e:
                logger.warning(f"以 Markdown 格式发送消息失败: {e}。切换到纯文本格式。")
                try:
                    # 如果 Markdown 发送失败，则尝试发送纯文本格式
                    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_part, disable_web_page_preview=True)
                    logger.info(f"消息以纯文本格式成功发送: {message_part[:50]}...")
                except Exception as e:
                    logger.error(f"即使以纯文本格式也无法发送消息: {message_part[:50]}..., 错误: {e}")
    
    except Exception as e:
        logger.error(f"发送消息到 Telegram 时出错: {e}")

# 获取并处理未读邮件
async def fetch_emails():
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        status, messages = mail.search(None, '(UNSEEN)')
        if status != 'OK':
            logger.error("搜索邮件时出错")
            return
        
        email_ids = messages[0].split()
        
        for email_id in email_ids:
            try:
                _, msg_data = mail.fetch(email_id, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])

                subject = clean_subject(decode_header(msg['subject']))
                sender = decode_header(msg['from'])

                # 解析发件人
                name, email_address = parseaddr(sender)
                
                # 检查邮件日期字段
                date_str = msg.get('date')
                if date_str is None:
                    logger.warning(f"邮件 ID {email_id} 没有日期头部，使用当前时间作为备用。")
                    email_date_bj = datetime.now(pytz.timezone('Asia/Shanghai'))
                else:
                    try:
                        email_date = parsedate_to_datetime(date_str)
                        email_date_bj = email_date.astimezone(pytz.timezone('Asia/Shanghai'))
                    except Exception as e:
                        logger.warning(f"解析邮件 ID {email_id} 的日期时出错: {e}，使用当前时间作为备用。")
                        email_date_bj = datetime.now(pytz.timezone('Asia/Shanghai'))

                body = get_email_body(msg)

                url = f"https://mail.qq.com/{sender}"

                message = f'''
✉️ *{name}* <{email_address}>
{subject}

{body}
'''
                await send_message(message)

                # 将邮件标记为已读
                mail.store(email_id, '+FLAGS', '\\Seen')
                logger.info(f"邮件编号 {email_id} 已标记为已读")

            except Exception as e:
                logger.error(f"处理邮件 ID {email_id} 时出错: {e}")

    except Exception as e:
        logger.error(f"获取邮件时出错: {e}")
    finally:
        mail.logout()

if __name__ == '__main__':
    asyncio.run(fetch_emails())
