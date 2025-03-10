import imaplib
import email
import re
import uuid
import requests
from email.header import decode_header
from email.utils import parseaddr
import html2text
from telegram.helpers import escape_markdown

# 配置信息（需要替换为实际值）
QQ_EMAIL = "penggan0@qq.com"  # 替换为QQ邮箱地址
QQ_AUTH_CODE = "hbkzbvpyojnibhid"  # QQ邮箱授权码
TELEGRAM_TOKEN = "7422217982:AAGcyh0Do-RzggL8i61BksdVZModB6wfHzc"  # Telegram机器人Token
TELEGRAM_CHAT_ID = "7071127210"  # Telegram Chat ID

def fetch_unread_emails():
    """获取所有未读邮件"""
    mail = imaplib.IMAP4_SSL("imap.qq.com", 993)
    mail.login(QQ_EMAIL, QQ_AUTH_CODE)
    mail.select("INBOX")
    status, messages = mail.search(None, "UNSEEN")
    if status != "OK":
        return [], mail
    return messages[0].split(), mail

def decode_mime_header(header):
    """解码MIME编码的邮件头"""
    decoded_parts = []
    for part, encoding in decode_header(header):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return " ".join(decoded_parts)

def extract_email_info(msg):
    """解析邮件信息"""
    from_header = msg.get("From", "")
    username, email_addr = parseaddr(from_header)
    username = decode_mime_header(username)
    
    subject = decode_mime_header(msg.get("Subject", ""))
    
    html_content = None
    text_content = None
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/html" and not html_content:
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            html_content = payload.decode(charset, errors="replace")
        elif content_type == "text/plain" and not text_content:
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            text_content = payload.decode(charset, errors="replace")
    
    return {
        "username": username,
        "email": email_addr,
        "subject": subject,
        "html": html_content,
        "text": text_content
    }

def html_to_markdown(html):
    """将HTML转换为Markdown并清理标签"""
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0
    converter.mark_code = False  # 防止代码块转义
    converter.escape_all = False  # 关闭全局转义
    markdown = converter.handle(html)
    return re.sub(r"<[^>]+>", "", markdown)  # 移除残留HTML标签

def protect_links(content):
    """保护Markdown链接不被转义"""
    link_pattern = re.compile(r"(\[[^\]]*?\]\(\s*?(?:\\\()?.*?\s*?\))", re.DOTALL)
    links = link_pattern.findall(content)
    placeholders = [f"__LINK_{uuid.uuid4().hex}__" for _ in links]
    link_map = dict(zip(placeholders, links))
    for ph, link in link_map.items():
        content = content.replace(link, ph, 1)
    return content, link_map

def send_telegram_message(text):
    """发送消息到Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2"
    }
    response = requests.post(url, data=payload)
    return response.json()

def process_content(markdown_content):
    """处理内容转义与链接恢复"""
    # 保护链接并生成占位符
    protected_content, link_map = protect_links(markdown_content)
    
    # 转义整个内容（此时占位符不会受影响）
    escaped_content = escape_markdown(protected_content, version=2)
    
    # 恢复原始链接
    for placeholder, original_link in link_map.items():
        escaped_content = escaped_content.replace(placeholder, original_link)
    
    return escaped_content

def main():
    mail_ids, mail_conn = fetch_unread_emails()
    if not mail_ids:
        print("没有未读邮件")
        return

    for mail_id in mail_ids:
        try:
            status, data = mail_conn.fetch(mail_id, "(RFC822)")
            if status != "OK":
                continue
            
            msg = email.message_from_bytes(data[0][1])
            email_info = extract_email_info(msg)
            
            # 获取有效内容
            if email_info["html"]:
                markdown_content = html_to_markdown(email_info["html"])
            elif email_info["text"]:
                markdown_content = email_info["text"]
            else:
                continue
            
            # 处理内容转义
            final_content = process_content(markdown_content)
            
            # 构建消息格式
            username = escape_markdown(email_info["username"], version=2)
            email_addr = escape_markdown(email_info["email"], version=2)
            subject = escape_markdown(email_info["subject"], version=2)
            
            message = (
                f"*{username}* `{email_addr}`\n"
                f"*Subject*: {subject}\n\n"
                f"{final_content}"
            )
            
            # 发送并标记已读
            send_telegram_message(message)
            mail_conn.store(mail_id, "+FLAGS", "\\Seen")
        except Exception as e:
            print(f"处理邮件时出错: {e}")

    mail_conn.close()
    mail_conn.logout()

if __name__ == "__main__":
    main()