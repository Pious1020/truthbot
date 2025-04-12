import requests
from bs4 import BeautifulSoup
from transformers import pipeline
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
import os
from datetime import datetime

# Load .env variables
load_dotenv()

alpaca_api_key = os.getenv("ALPACA_API_KEY")
alpaca_api_secret = os.getenv("ALPACA_API_SECRET")

api = tradeapi.REST(alpaca_api_key, alpaca_api_secret, base_url='https://paper-api.alpaca.markets')


# Initialize the sentiment analysis pipeline with specific model and revision
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    revision="714eb0f"
)


LAST_POST_FILE = "last_post.txt"


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

def execute_trade(outlook):
    spy_qty = get_current_position("SPY")
    sh_qty = get_current_position("SH")

    if outlook == "Bullish":
        if sh_qty > 0:
            close_position("SH")
        if spy_qty == 0:
            api.submit_order(
                symbol='SPY',
                qty=1,
                side='buy',
                type='market',
                time_in_force='gtc'
            )
            print("✅ Bought 1 share of SPY (Bullish)")

    elif outlook == "Bearish":
        if spy_qty > 0:
            close_position("SPY")
        if sh_qty == 0:
            api.submit_order(
                symbol='SH',
                qty=1,
                side='buy',
                type='market',
                time_in_force='gtc'
            )
            print("✅ Bought 1 share of SH (Bearish)")

    else:
        print("Sentiment is Neutral. No trade executed.")

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

print(f"Timestamp: {timestamp}")
print(f"Post: {text}")

last_seen = load_last_timestamp()
if timestamp == last_seen:
    print("⏳ No new post. Holding current position.")
    exit()

# New post detected
market_outlook = analyze_sentiment(text)
print(f"Sentiment → {market_outlook}")
print("-" * 50)

if is_regular_trading_hours():
    execute_trade(market_outlook)
else:
    print("Not regular market hours. Trade not executed.")

save_last_timestamp(timestamp)
