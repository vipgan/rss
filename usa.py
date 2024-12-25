import yfinance as yf
import pandas as pd
from pandas_datareader import data as web
from datetime import datetime
from dotenv import load_dotenv
import os
import requests

load_dotenv()


def send_telegram_message(message):
    api_key = os.getenv('TELEGRAM_API_KEY')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{api_key}/sendMessage?chat_id={chat_id}&text={message}"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"发送Telegram消息失败: {e}")

def get_price(ticker, period="1d"):
    try:
        data = yf.Ticker(ticker).history(period=period)
        if not data.empty:
            return data['Close'].iloc[-1]
        else:
            return None
    except Exception as e:
        print(f"获取{ticker}价格失败: {e}")
        return None

def fetch_and_send_financial_data():
    try:
        # 获取美元指数
        dxy = get_price("DX-Y.NYB")  # 使用yfinance获取美元指数
        if dxy is None:
            dxy = "N/A"
        else:
            dxy = round(dxy, 2)

        tickers = {
            "上证指数": "000001.SS",
            "BTC": "BTC-USD",
            "CNY/USD": "CNY=X",
            "JPY/USD": "JPY=X",
        }

        data = {}
        for key, value in tickers.items():
            if key == "美元指数":
                data[key] = dxy
            else:
                price = get_price(value)
                data[key] = round(price, 2) if price is not None else "N/A"

        message = "金融数据更新:\n"
        for key, value in data.items():
            message += f"{key}: {value}\n"

        send_telegram_message(message)

        df = pd.DataFrame([data])
        df.to_csv("financial_data.csv", mode='a', header=False, index=False)

        print("数据已更新并推送到Telegram")
    except Exception as e:
        print(f"数据更新或推送失败: {e}")

if __name__ == "__main__":
    fetch_and_send_financial_data()
