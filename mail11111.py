import imaplib
import email
from email.header import decode_header
import html2text
import telegram
from telegram.helpers import escape_markdown
from telegram.constants import ParseMode
import os
import asyncio
import re
import chardet
from dotenv import load_dotenv
from email.utils import parseaddr

load_dotenv()

# 配置信息
IMAP_SERVER = os.getenv("IMAP_SERVER")
EMAIL_ADDRESS = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_API_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAX_MESSAGE_LENGTH = 3900  # 保留安全余量
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

class EmailDecoder:
    @staticmethod
    def decode_email_header(header):
        """智能解码邮件头"""
        if not header:
            return ""
        try:
            decoded = decode_header(header)
            return ''.join([
                t[0].decode(t[1] or 'utf-8', errors='ignore') 
                if isinstance(t[0], bytes) 
                else str(t[0])
                for t in decoded
            ])
        except Exception as e:
            return str(header)

    @staticmethod
    def detect_encoding(content):
        """编码检测优化"""
        try:
            result = chardet.detect(content)
            if result['confidence'] > 0.7:
                return result['encoding']
            return 'gb18030' if b'\x80' in content[:100] else 'utf-8'
        except Exception as e:
            return 'gb18030'

class ContentProcessor:
    @staticmethod
    def normalize_newlines(text):
        """统一换行符并合并空行"""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        return re.sub(r'\n{3,}', '\n\n', text)

    @staticmethod
    def clean_text(text):
        """终极文本清洗"""
        text = text.replace('|', '')
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        text = ContentProcessor.normalize_newlines(text)
        text = '\n'.join(line.strip() for line in text.split('\n'))
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()

    @staticmethod
    def extract_urls(html):
        """智能链接过滤"""
        url_pattern = re.compile(
            r'(https?://[^\s>"\'{}|\\^`]+)',
            re.IGNORECASE
        )
        urls = []
        seen = set()
        exclude_domains = {'w3.org', 'schema.org', 'example.com'}

        for match in url_pattern.finditer(html):
            raw_url = match.group(1)
            clean_url = re.sub(r'[{}|\\)(<>`]', '', raw_url.split('"')[0])
            
            if not (10 < len(clean_url) <= 100):
                continue
                
            if any(d in clean_url for d in exclude_domains):
                continue
                
            if clean_url not in seen:
                seen.add(clean_url)
                urls.append(clean_url)
                
        return urls[:5]

    @staticmethod
    def convert_html_to_text(html_bytes):
        """HTML转换强化"""
        try:
            encoding = EmailDecoder.detect_encoding(html_bytes)
            html = html_bytes.decode(encoding, errors='replace')
            
            converter = html2text.HTML2Text()
            converter.body_width = 0
            converter.ignore_links = True
            converter.ignore_images = True
            converter.ignore_emphasis = True
            
            text = converter.handle(html)
            text = ContentProcessor.clean_text(text)
            text = escape_markdown(text, version=2)  # 转义普通文本
            
            urls = ContentProcessor.extract_urls(html)
            formatted_urls = []
            for url in urls:
                escaped_text = escape_markdown(url, version=2)
                escaped_url = url.replace(')', '\\)').replace('\\', '\\\\')
                formatted_urls.append(f"[{escaped_text}]({escaped_url})")
            
            final_text = text
            if formatted_urls:
                final_text += "\n\n相关链接：\n" + "\n".join(formatted_urls)
                
            return ContentProcessor.normalize_newlines(final_text)
            
        except Exception as e:
            return "⚠️ 内容解析异常"

class EmailHandler:
    @staticmethod
    def get_email_content(msg):
        """统一内容获取"""
        try:
            content = ""
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    html_bytes = part.get_payload(decode=True)
                    content = ContentProcessor.convert_html_to_text(html_bytes)
                    break
                    
            if not content:
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        text_bytes = part.get_payload(decode=True)
                        encoding = EmailDecoder.detect_encoding(text_bytes)
                        raw_text = text_bytes.decode(encoding, errors='replace')
                        content = ContentProcessor.clean_text(raw_text)
                        content = escape_markdown(content, version=2)  # 转义纯文本
                        break
                        
            if not content and any(part.get_content_maintype() == 'image' for part in msg.walk()):
                content = "📨 图片内容（文本信息如下）\n" + "\n".join(
                    f"{k}: {v}" for k,v in msg.items() if k.lower() in ['subject', 'from', 'date']
                )
                content = escape_markdown(content, version=2)
                
            return ContentProcessor.normalize_newlines(content or "⚠️ 无法解析内容")
            
        except Exception as e:
            return "⚠️ 内容提取异常"

class MessageFormatter:
    @staticmethod
    def format_message(sender, subject, content):
        """返回分离的header和body"""
        realname, email_address = parseaddr(sender)
        
        clean_realname = re.sub(r'[|]', '', realname).strip()
        clean_email = email_address.strip()
        clean_subject = re.sub(r'\s+', ' ', subject).replace('|', '')
        
        # 转义Markdown特殊字符
        clean_realname = escape_markdown(clean_realname, version=2)
        clean_email = escape_markdown(clean_email, version=2)
        clean_subject = escape_markdown(clean_subject, version=2)
        
        sender_lines = []
        if clean_realname:
            sender_lines.append(f"✉️ {clean_realname}")
        if clean_email:
            sender_lines.append(f"{clean_email}")
        
        formatted_content = ContentProcessor.normalize_newlines(content)
        
        header = (
            f"{' '.join(sender_lines)}\n"
            f"*{clean_subject}*\n\n"  # 主题使用加粗
        )
        return header, formatted_content

    @staticmethod
    def split_content(text, max_length):
        """智能分割优化（返回分割后的块列表）"""
        chunks = []
        current_chunk = []
        current_length = 0

        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        for para in paragraphs:
            potential_add = len(para) + (2 if current_chunk else 0)

            if current_length + potential_add > max_length:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                    
                    if len(para) > max_length:
                        start = 0
                        while start < len(para):
                            end = start + max_length
                            chunks.append(para[start:end])
                            start = end
                        continue
                    else:
                        current_chunk.append(para)
                        current_length = len(para)
                else:
                    start = 0
                    while start < len(para):
                        end = start + max_length
                        chunks.append(para[start:end])
                        start = end
            else:
                current_chunk.append(para)
                current_length += potential_add

        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        # 最终长度校验
        final_chunks = []
        for chunk in chunks:
            while len(chunk) > max_length:
                final_chunks.append(chunk[:max_length])
                chunk = chunk[max_length:]
            if chunk:
                final_chunks.append(chunk)
        
        return final_chunks

class TelegramBot:
    def __init__(self):
        self.bot = telegram.Bot(TELEGRAM_TOKEN)
        
    async def send_message(self, text):
        """最终发送处理"""
        try:
            final_text = ContentProcessor.normalize_newlines(text)
            final_text = re.sub(r'^\s*[-]{2,}\s*$', '', final_text, flags=re.MULTILINE)
            
            await self.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=final_text,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
        except telegram.error.BadRequest as e:
            pass
        except Exception as e:
            pass

async def main():
    bot = TelegramBot()
    
    try:
        with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
            mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            mail.select("INBOX")
            
            _, nums = mail.search(None, "UNSEEN")
            if not nums[0]:
                return

            for num in nums[0].split():
                try:
                    _, data = mail.fetch(num, "(RFC822)")
                    msg = email.message_from_bytes(data[0][1])
                    
                    sender = EmailDecoder.decode_email_header(msg.get("From"))
                    subject = EmailDecoder.decode_email_header(msg.get("Subject"))
                    content = EmailHandler.get_email_content(msg)

                    header, body = MessageFormatter.format_message(sender, subject, content)
                    header_len = len(header)
                    max_body_len = MAX_MESSAGE_LENGTH - header_len

                    if max_body_len <= 0:
                        header = header[:MAX_MESSAGE_LENGTH-4] + "..."
                        header_len = len(header)
                        max_body_len = MAX_MESSAGE_LENGTH - header_len

                    first_part_chunks = MessageFormatter.split_content(body, max_body_len)
                    
                    if first_part_chunks:
                        first_chunk = first_part_chunks[0]
                        await bot.send_message(header + first_chunk)
                        
                        remaining_body = '\n\n'.join(
                            para 
                            for chunk in first_part_chunks[1:] 
                            for para in chunk.split('\n\n')
                        )
                    else:
                        remaining_body = body

                    subsequent_chunks = MessageFormatter.split_content(remaining_body, MAX_MESSAGE_LENGTH)
                    
                    for chunk in subsequent_chunks:
                        await bot.send_message(chunk)
                        
                    mail.store(num, "+FLAGS", "\\Seen")
                    
                except Exception as e:
                    continue

    except Exception as e:
        pass

if __name__ == "__main__":
    asyncio.run(main())