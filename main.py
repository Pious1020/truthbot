import requests
from bs4 import BeautifulSoup
from transformers import pipeline
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
import os
from datetime import datetime
from datetime import timedelta

# Load .env variables
load_dotenv()

# Get Alpaca API keys from environment variables
alpaca_api_key = os.getenv("ALPACA_API_KEY")
alpaca_api_secret = os.getenv("ALPACA_API_SECRET")

# Initialize Alpaca API
api = tradeapi.REST(alpaca_api_key, alpaca_api_secret, base_url='https://paper-api.alpaca.markets')

# Telegram Bot Setup
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

# Initialize the sentiment analysis pipeline
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    revision="714eb0f"
)

LAST_POST_FILE = "last_post.txt"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": message
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def is_regular_trading_hours():
    clock = api.get_clock()
    now = datetime.now(clock.timestamp.tzinfo)
    return clock.is_open and clock.next_open <= now <= clock.next_close

def load_last_timestamp():
    if os.path.exists(LAST_POST_FILE):
        with open(LAST_POST_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_last_timestamp(timestamp):
    with open(LAST_POST_FILE, 'w') as f:
        f.write(timestamp)

def analyze_sentiment(text):
    result = sentiment_analyzer(text)[0]
    label = result["label"]
    if label == "POSITIVE":
        return "Bullish"
    elif label == "NEGATIVE":
        return "Bearish"
    else:
        return "Neutral"

def get_current_position(symbol):
    try:
        pos = api.get_position(symbol)
        return float(pos.qty)
    except:
        return 0

def close_position(symbol):
    try:
        api.close_position(symbol)
        print(f"Closed position in {symbol}")
    except:
        print(f"No open position in {symbol} to close.")

def close_all_positions_if_market_closing():
    clock = api.get_clock()
    now = clock.timestamp

    # Time delta to determine "closing soon"
    close_threshold = timedelta(minutes=10)

    if clock.is_open and (clock.next_close - now) <= close_threshold:
        positions = api.list_positions()
        if not positions:
            print("📭 No positions to close.")
            send_telegram_message("📭 No positions to close.")
            return

        print("🔔 Market closing within 10 minutes. Closing all positions.")
        send_telegram_message("🔔 Market closing within 10 minutes. Closing all positions.")

        for position in positions:
            symbol = position.symbol
            try:
                api.close_position(symbol)
                print(f"✅ Closed {symbol}")
                send_telegram_message(f"✅ Closed {symbol}")
            except Exception as e:
                print(f"⚠️ Error closing {symbol}: {e}")
                send_telegram_message(f"⚠️ Error closing {symbol}: {e}")


def calculate_max_shares(symbol):
    try:
        buying_power = float(api.get_account().buying_power)
        latest_price = float(api.get_latest_trade(symbol).price)
        return int(buying_power // latest_price)
    except Exception as e:
        print(f"Error calculating max shares: {e}")
        return 0

def execute_trade(outlook):
    spy_qty = get_current_position("SPY")
    sh_qty = get_current_position("SH")

    max_shares = calculate_max_shares("SPY" if outlook == "Bullish" else "SH")

    if outlook == "Bullish":
        if sh_qty > 0:
            close_position("SH")
        if spy_qty == 0:
            api.submit_order(
                symbol='SPY',
                qty=max_shares,
                side='buy',
                type='market',
                time_in_force='gtc'
            )
            print("✅ Bought shares of SPY (Bullish)")
            send_telegram_message("📈 Action Taken → Bought shares of SPY (Bullish)")

    elif outlook == "Bearish":
        if spy_qty > 0:
            close_position("SPY")
        if sh_qty == 0:
            api.submit_order(
                symbol='SH',
                qty=max_shares,
                side='buy',
                type='market',
                time_in_force='gtc'
            )
            print("✅ Bought shares of SH (Bearish)")
            send_telegram_message("📉 Action Taken → Bought shares of SH (Bearish)")

    else:
        print("Sentiment is Neutral. No trade executed.")
        send_telegram_message("❗ Action Taken → No trade executed (Neutral sentiment)")

# Scrape the most recent post
url = "https://trumpstruth.org/?per_page=50"
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, "html.parser")
truth = soup.find("div", class_="status__body")

meta = truth.find_previous("div", class_="status-info__body")
timestamp = "No timestamp"
if meta:
    tags = meta.find_all("a", class_="status-info__meta-item")
    if len(tags) > 1:
        timestamp = tags[1].get_text(strip=True)

content = truth.find("div", class_="status__content")
text = content.get_text(strip=True) if content else "No text found"

# Send Telegram update with post details
message = f"📰 Newest Trump Post\nTimestamp: {timestamp}\n\n{text}"
print(message)
send_telegram_message(message)




last_seen = load_last_timestamp()
if timestamp == last_seen:
    print("⏳ No new post. Holding current position.")
    send_telegram_message("⏳ No new post. Holding current position.")
    exit()

# New post detected
market_outlook = analyze_sentiment(text)
print(f"Sentiment → {market_outlook}")
print("-" * 50)

if is_regular_trading_hours():
    execute_trade(market_outlook)
else:
    msg = "⏱ Market closed. No trade executed."
    print(msg)
    send_telegram_message(msg)


execute_trade(market_outlook)

save_last_timestamp(timestamp)
close_all_positions_if_market_closing()
