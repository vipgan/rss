import re
from bs4 import BeautifulSoup
import email
import html

def clean_subject(subject):
    """
    清理邮件主题,去除 HTML 标签、Markdown 格式标签(如 *、_)以及特殊字符和方括号 [ ]。
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
    
    # 处理连续的空行
    text = re.sub(r'\n\s*\n+', '\n', text)
    
    # 去除多余的空白和连字符
    text = re.sub(r'-{2,}', '-', text)
    text = re.sub(r'—{4,}', '-' * 8, text)
    text = re.sub(r'<[^>]+>', '', text)
    # 新增代码:去除文本中的 * 符号
    text = text.replace('*', '')
    # 新增代码:去除文本中的 _ 符号
    text = text.replace('_', '')

    return text.strip()

def get_email_body(msg):
    """
    从邮件中提取正文内容,支持多部分格式。
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

async def send_message(text):
    try:
        # 正则表达式模式来匹配 URL
        url_pattern = r'(?<!\[)(https?://\S+)(?!\])'
        
        # 找到所有匹配的 URL
        urls = re.findall(url_pattern, text)
        
        # 对每一个 URL,创建一个 HTML 链接
        for url in urls:
            url_index = text.find(url)
            before_text = text[:url_index].strip().split()[-1] if text[:url_index].strip() else ''
            after_text = text[url_index + len(url):].strip().split()[0] if text[url_index + len(url):].strip() else ''
            
            if before_text:
                display_text = html.escape(before_text)  # 转义显示文本中的特殊字符
            elif after_text:
                display_text = html.escape(after_text)
            else:
                display_text = url  # 如果没有前面的文本或后面的文本,使用 URL 本身作为显示文本
            
            # 确保 URL 本身的特殊字符也被转义
            escaped_url = html.escape(url)
            
            # 替换 URL 为 HTML 格式的链接
            text = text.replace(url, f'<a href="{escaped_url}">{display_text}</a>')
        
        # 确保整个文本中的 HTML 特殊字符被转义,以避免解析冲突
        text = html.escape(text)
        
        # 恢复我们刚刚创建的 HTML 链接,因为它们已经被转义了
        text = re.sub(r'&lt;a href=&quot;(.*?)&quot;&gt;(.*?)&lt;/a&gt;', r'<a href="\1">\2</a>', text)
        
        MAX_MESSAGE_LENGTH = 4096
        messages = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
        
        for message_part in messages:
            try:
                # 发送消息并处理 HTML 格式
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_part, parse_mode='HTML', disable_web_page_preview=True)
                logger.info(f"消息以 HTML 格式成功发送: {message_part[:50]}...")
            except Exception as e:
                logger.warning(f"以 HTML 格式发送消息失败: {e}。切换到纯文本格式。")
                try:
                    # 如果 HTML 发送失败，则尝试发送纯文本格式
                    # 这里我们需要再次转义 HTML 链接,以确保纯文本中不会出现 HTML 标签
                    text = html.unescape(text)
                    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_part, disable_web_page_preview=True)
                    logger.info(f"消息以纯文本格式成功发送: {message_part[:50]}...")
                except Exception as e:
                    logger.error(f"即使以纯文本格式也无法发送消息: {message_part[:50]}..., 错误: {e}")
    
    except Exception as e:
        logger.error(f"发送消息到 Telegram 时出错: {e}")
