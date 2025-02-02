import imaplib
import email
from email.header import decode_header
import html2text
import telegram
import logging
import os
import asyncio
import re
from dotenv import load_dotenv
import google.generativeai as genai
from urllib.parse import quote

load_dotenv()

# 邮箱配置
IMAP_SERVER = os.getenv("IMAP_SERVER")
EMAIL_ADDRESS = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# 电报配置
TELEGRAM_TOKEN = os.getenv("TELEGRAM_API_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Gemini 配置
GOOGLE_API_KEY = os.getenv("OPENAI_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# 最大消息长度限制
MAX_MESSAGE_LENGTH = 4000

# 初始化日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def decode_email_header(header):
    if header:
        decoded_header = decode_header(header)
        parts = []
        for part, encoding in decoded_header:
            if isinstance(part, bytes):
                try:
                    if encoding:
                        parts.append(part.decode(encoding))
                    else:
                        parts.append(part.decode('utf-8'))
                except UnicodeDecodeError:
                    try:
                        parts.append(part.decode('gbk')) 
                    except UnicodeDecodeError:
                        parts.append(part.decode('latin1', errors='ignore')) 
            else:
                parts.append(part)

        return "".join(parts)
    return ""


def get_email_content(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if "attachment" not in content_disposition:
                try:
                    if content_type == "text/plain":
                        body = part.get_payload(decode=True).decode(part.get_content_charset(), errors='ignore')
                        return body
                    elif content_type == "text/html":
                        html_body = part.get_payload(decode=True).decode(part.get_content_charset(), errors='ignore')
                        text_body = html2text.html2text(html_body)
                        return text_body

                except Exception as e:
                    logging.error(f"Error decoding part: {e}")

    elif msg.get_content_type() == "text/plain":
        try:
            body = msg.get_payload(decode=True).decode(msg.get_content_charset(), errors='ignore')
            return body
        except Exception as e:
           logging.error(f"Error decoding plain text body: {e}")
    elif msg.get_content_type() == "text/html":
        try:
             html_body = msg.get_payload(decode=True).decode(msg.get_content_charset(), errors='ignore')
             text_body = html2text.html2text(html_body)
             return text_body
        except Exception as e:
            logging.error(f"Error decoding html text body: {e}")
    return ""

def clean_html_text(text):
    """清理残留的 HTML 标签和特殊字符"""
    text = re.sub(r'<.*?>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e]', '', text)
    return text

def process_text(text):
     """处理文本，只保留一个空行"""
     text = re.sub(r'\n{2,}', '\n', text) # 将3个以上的换行符替换为2个
     return text

def url_encode_links(text):
    """只对链接地址进行 URL 编码"""
    def replace_link(match):
        link = match.group(2)
        encoded_link = quote(link)
        return f"[{match.group(1)}]({encoded_link})"
    
    # 使用正则表达式查找链接，并对链接地址进行 URL 编码
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, text)
    return text

def remove_markdown_tags(text):
    """移除 Markdown 标签，但保留链接格式"""
    # 移除标题标签 (如 #, ##, ###)
    text = re.sub(r'#+\s*', '', text)
    # 移除加粗和斜体标签 (如 **, __, *, _)
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text) # 保留加粗内容，移除标签
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text) # 保留斜体内容，移除标签
    # 移除列表标签 (如 *, -)
    text = re.sub(r'^[\*\-\+]\s*', '', text, flags=re.MULTILINE)
    # 移除代码块标签 (如 ```)
    text = re.sub(r'```(.*?)```', r'\1', text, flags=re.DOTALL)
    # 移除引用标签 (如 >)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    return text


async def send_telegram_message(bot, message):
    try:
        logging.info(f"Attempting to send message: {message}")
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, disable_web_page_preview=True) # 使用纯文本模式
        logging.info(f"Message sent to Telegram successfully.")
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")


def split_message(message, max_length):
    """按段落分割消息"""
    parts = []
    current_part = ""
    paragraphs = message.split("\n\n") # 按两个换行符分割段落
    for paragraph in paragraphs:
        if len(current_part) + len(paragraph) + 2 <= max_length:
            current_part += paragraph + "\n\n"
        else:
            parts.append(current_part)
            current_part = paragraph + "\n\n"
    parts.append(current_part)
    return parts

async def process_email(bot):
    try:
        logging.info("Connecting to IMAP server...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        logging.info("Successfully logged in.")
        mail.select("INBOX")
        logging.info("Selected INBOX.")

        _, msg_nums = mail.search(None, "UNSEEN")  # 获取所有未读邮件的编号
        if not msg_nums[0]:
            logging.info("No new emails found.")
            mail.close()
            mail.logout()
            return

        for num in msg_nums[0].split():
            logging.info(f"Processing email number: {num}")
            _, data = mail.fetch(num, "(RFC822)")
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            sender = decode_email_header(msg.get("From"))
            subject = decode_email_header(msg.get("Subject"))
            # 删除主题中的 " 符号
            subject = subject.replace('"', '')
            content = get_email_content(msg)

            if content:
                 # 清理 HTML 标签和特殊字符
                message = clean_html_text(content)
                # URL 编码链接
                message = url_encode_links(message)

            
                 # 使用 Gemini API 处理
                try:
                    response = model.generate_content(f"请将以下文本整理为纯文本格式:\n{message}")
                    gemini_output = response.text
                    if gemini_output:
                       message = gemini_output
                       message = process_text(message) # 处理连续空行
                       message = remove_markdown_tags(message) # 移除 Markdown 标签
                    else:
                        logging.warning("Gemini API returned empty response, using original cleaned message.")
                except Exception as e:
                    logging.error(f"Error using Gemini API: {e}")

                # 构建最终消息格式
                message = f"✉️ {sender}\n{subject}\n>>>\n{message}"
            else:
                logging.warning(f"Email content is empty for message {num}. Skipping.")
                continue


            # 分割消息
            message_parts = split_message(message, MAX_MESSAGE_LENGTH)

            for part in message_parts:
                await send_telegram_message(bot, part)

            mail.store(num, "+FLAGS", "\\Seen")  # 标记为已读
        mail.close()
        mail.logout()
        logging.info("Finished processing emails.")

    except Exception as e:
        logging.error(f"Error in process_email function: {e}")


async def main():
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.info("Checking for new emails...")
    await process_email(bot)


if __name__ == "__main__":
    asyncio.run(main())
