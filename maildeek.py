import imaplib
import email
from email.header import decode_header
import html2text
import telegram
import logging
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
MAX_MESSAGE_LENGTH = 3800
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# 日志配置
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_bot.log'),
        logging.StreamHandler()
    ]
)

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
            logging.error(f"Header decode error: {e}")
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
            logging.error(f"Encoding detection error: {e}")
            return 'gb18030'

class ContentProcessor:
    @staticmethod
    def normalize_newlines(text):
        """统一换行符并合并空行"""
        # 替换所有换行符为\n
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # 合并3个以上换行为2个
        return re.sub(r'\n{3,}', '\n\n', text)

    @staticmethod
    def clean_text(text):
        """终极文本清洗"""
        # 去除所有 | 符号
        text = text.replace('|', '')
        
        # 清理特殊字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # 合并连续空行（先标准化换行）
        text = ContentProcessor.normalize_newlines(text)
        
        # 去除行首尾空白
        text = '\n'.join(line.strip() for line in text.split('\n'))
        
        # 清理残留HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        return text.strip()

    @staticmethod
    def extract_urls(html):
        """智能链接过滤"""
        url_pattern = re.compile(
            r'(https?://[^\s>"\'{}|\\^`]+)',  # 更严格的匹配
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
            converter.body_width = 0          # 禁用自动换行
            converter.ignore_links = True     # 由extract_urls单独处理
            converter.ignore_images = True
            converter.ignore_emphasis = True
            
            text = converter.handle(html)
            text = ContentProcessor.clean_text(text)
            
            urls = ContentProcessor.extract_urls(html)
            
            final_text = text
            if urls:
                final_text += "\n\n相关链接：\n" + "\n".join(urls)
                
            # 最终空行处理
            return ContentProcessor.normalize_newlines(final_text)
            
        except Exception as e:
            logging.error(f"HTML处理失败: {e}")
            return "⚠️ 内容解析异常"

class EmailHandler:
    @staticmethod
    def get_email_content(msg):
        """统一内容获取"""
        try:
            content = ""
            # 优先处理HTML
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    html_bytes = part.get_payload(decode=True)
                    content = ContentProcessor.convert_html_to_text(html_bytes)
                    break
                    
            # 次选纯文本
            if not content:
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        text_bytes = part.get_payload(decode=True)
                        encoding = EmailDecoder.detect_encoding(text_bytes)
                        raw_text = text_bytes.decode(encoding, errors='replace')
                        content = ContentProcessor.clean_text(raw_text)
                        break
                        
            # 图片邮件处理
            if not content and any(part.get_content_maintype() == 'image' for part in msg.walk()):
                content = "📨 图片内容（文本信息如下）\n" + "\n".join(
                    f"{k}: {v}" for k,v in msg.items() if k.lower() in ['subject', 'from', 'date']
                )
                
            # 最终空行处理
            return ContentProcessor.normalize_newlines(content or "⚠️ 无法解析内容")
            
        except Exception as e:
            logging.error(f"内容提取失败: {e}")
            return "⚠️ 内容提取异常"

class MessageFormatter:
    @staticmethod
    def format_message(sender, subject, content):
        """消息格式化强化"""
        # 解析发件人信息
        realname, email_address = parseaddr(sender)
        
        # 清理信息
        clean_realname = re.sub(r'[|]', '', realname).strip()
        clean_email = email_address.strip()
        clean_subject = re.sub(r'\s+', ' ', subject).replace('|', '')
        
        # 构建发件人显示信息
        sender_lines = []
        if clean_realname:
            sender_lines.append(f"✉️ {clean_realname}")
        if clean_email:
            sender_lines.append(f"{clean_email}")
        
        # 组合消息内容
        formatted_content = ContentProcessor.normalize_newlines(content)
        
        return (
            f"{' '.join(sender_lines)}\n"
            f"{clean_subject}\n\n"
            f"{formatted_content}"
        )

    @staticmethod
    def split_content(text):
        """智能分割优化"""
        # 按空行分割段落
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks = []
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para_length = len(para) + 2  # 加上换行符
            if current_length + para_length > MAX_MESSAGE_LENGTH:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_length = 0
                
            current_chunk.append(para)
            current_length += para_length

        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks

class TelegramBot:
    def __init__(self):
        self.bot = telegram.Bot(TELEGRAM_TOKEN)
        
    async def send_message(self, text):
        """最终发送处理"""
        try:
            # 发送前最后清理
            final_text = ContentProcessor.normalize_newlines(text)
            
            # 新增：删除仅含两个或以上减号的行（包含前后空格）
            final_text = re.sub(
                r'^\s*[-]{2,}\s*$', 
                '', 
                final_text, 
                flags=re.MULTILINE
            )
            
            # 重新处理换行符确保格式
            final_text = ContentProcessor.normalize_newlines(final_text)
            
            await self.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=final_text,
                parse_mode=None,
                disable_web_page_preview=True
            )
        except Exception as e:
            logging.error(f"发送失败: {str(e)[:200]}")

async def main():
    bot = TelegramBot()
    
    try:
        with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
            mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            mail.select("INBOX")
            
            _, nums = mail.search(None, "UNSEEN")
            if not nums[0]:
                logging.info("无未读邮件")
                return

            for num in nums[0].split():
                try:
                    _, data = mail.fetch(num, "(RFC822)")
                    msg = email.message_from_bytes(data[0][1])
                    
                    sender = EmailDecoder.decode_email_header(msg.get("From"))
                    subject = EmailDecoder.decode_email_header(msg.get("Subject"))
                    content = EmailHandler.get_email_content(msg)

                    formatted = MessageFormatter.format_message(sender, subject, content)
                    
                    for chunk in MessageFormatter.split_content(formatted):
                        await bot.send_message(chunk)
                        
                    mail.store(num, "+FLAGS", "\\Seen")
                    
                except Exception as e:
                    logging.error(f"处理异常: {str(e)[:200]}")
                    continue

    except Exception as e:
        logging.error(f"连接异常: {str(e)[:200]}")

if __name__ == "__main__":
    asyncio.run(main())