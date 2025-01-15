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

load_dotenv()

# 邮箱配置
IMAP_SERVER = os.getenv("IMAP_SERVER")
EMAIL_ADDRESS = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# 电报配置
TELEGRAM_TOKEN = os.getenv("TELEGRAM_API_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

async def send_telegram_message(bot, message):
    try:
        logging.info(f"Attempting to send message: {message}")
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, disable_web_page_preview=True)
        logging.info(f"Message sent to Telegram successfully.")
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")

def clean_message(message):
    # 1. 连续换行只保留一个
    message = re.sub(r'\n+', '\n', message)
    # 2. '-' 符号限制
    message = re.sub(r'-{28,}', '-' * 27, message)
    message = re.sub(r'_{19,}', '_' * 18, message)
    message = re.sub(r'—{19,}', '—' * 18, message)

    # 连续多个保留一个
    message = re.sub(r'\*+', '*', message)
    message = re.sub(r'\[+', '[', message)
    message = re.sub(r'\]+', ']', message)
    message = re.sub(r'\)+', ')', message)
    message = re.sub(r'\(+', '(', message)
    message = re.sub(r'\#+', '#', message)

    # 3. 过滤过长链接, 并替换链接中的 - 为 %2D
    urls = re.findall(r'(https?://\S+)', message)
    for url in urls:
        if len(url) > 100:
           logging.warning(f"Removed long URL: {url}")
           message = message.replace(url, "[Long URL Removed]")
        else:
            # 将链接中的 - 替换为 %2D
            modified_url = url.replace('-', '%2D')
            message = message.replace(url, modified_url)

    # 4. 移除 "|" 符号
    message = message.replace("|", "")
    message = message.replace("()", "")
    message = message.replace("[]", "")
    message = message.replace("<>", "")
    # 5. 将非链接中的 - 替换为 _
    def replace_non_link_hyphens(match):
        url_match = re.match(r'(https?://\S*)', match.group(0))
        if url_match:
            return match.group(0) # 如果是链接，保持原样
        else:
            return match.group(0).replace('_', '-') # 否则，替换 - 为 _

    message = re.sub(r'[^ ]+', replace_non_link_hyphens, message)

    # 7. 移除重复行
    lines = message.splitlines()
    unique_lines = []
    for line in lines:
        if not unique_lines or line != unique_lines[-1]:
            unique_lines.append(line)

    message = "\n".join(unique_lines)
    return message

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
            content = get_email_content(msg)

            # 移除图片标签、 &nbsp; 并把 &emsp; 替换为换行符
            if content:
                content = re.sub(r'!\[.*?\]\((.*?)\)', r'\1', content)
                content = content.replace('&nbsp;', ' ')  # 替换 &nbsp; 为空格
                content = content.replace('&emsp;', '\n')  # 替换 &emsp; 为换行符
                message = f"✉️ {sender}\n{subject}\n>>>\n{content}"
            else:
                logging.warning(f"Email content is empty for message {num}. Skipping.")
                continue
            
            # 清理消息
            cleaned_message = clean_message(message)
            if cleaned_message is None:
                continue # 跳过此消息

            # 分割消息
            message_parts = []
            current_part = ""
            for line in cleaned_message.splitlines():
                if len(current_part) + len(line) + 1 <= MAX_MESSAGE_LENGTH:
                    current_part += line + "\n"
                else:
                    message_parts.append(current_part)
                    current_part = line + "\n"
            message_parts.append(current_part)

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
