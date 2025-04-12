import requests
from bs4 import BeautifulSoup
from transformers import pipeline
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get Alpaca API keys from environment variables
alpaca_api_key = os.getenv("ALPACA_API_KEY")
alpaca_api_secret = os.getenv("ALPACA_API_SECRET")

# Initialize the sentiment analysis pipeline
sentiment_analyzer = pipeline("sentiment-analysis")

# Alpaca API setup
api = tradeapi.REST(alpaca_api_key, alpaca_api_secret, base_url='https://paper-api.alpaca.markets')

# URL of the website to scrape
url = "https://trumpstruth.org/?per_page=50"
headers = {
    "User-Agent": "Mozilla/5.0"
}

# Send GET request to the website
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, "html.parser")

# Find the most recent truth post within the div class "status__body" (just the first one)
truth = soup.find("div", class_="status__body")

# Function to analyze sentiment and stock market outlook
def analyze_sentiment(text):
    sentiment = sentiment_analyzer(text)
    label = sentiment[0]['label']
    
    # Mapping sentiment to stock market outlook
    if label == 'POSITIVE':
        outlook = 'Bullish'
    elif label == 'NEGATIVE':
        outlook = 'Bearish'
    else:
        outlook = 'Neutral'
    
    return outlook, label

# Function to execute trades based on sentiment
def execute_trade(outlook):
    if outlook == 'Bullish':
        # Buy SPY if market outlook is bullish
        api.submit_order(
            symbol='SPY',
            qty=1,  # Number of shares to trade
            side='buy',
            type='market',
            time_in_force='gtc'
        )
        print("Bought 1 share of SPY (Bullish outlook)")

    elif outlook == 'Bearish':
        # Sell SPY and buy SH (inverse ETF) if market outlook is bearish
        api.submit_order(
            symbol='SPY',
            qty=1,  # Sell SPY
            side='sell',
            type='market',
            time_in_force='gtc'
        )
        api.submit_order(
            symbol='SH',  # Buy inverse ETF (short SPY)
            qty=1,
            side='buy',
            type='market',
            time_in_force='gtc'
        )
        print("Sold 1 share of SPY and bought 1 share of SH (Bearish outlook)")

# Extract the timestamp
meta = truth.find_previous("div", class_="status-info__body")
if meta:
    timestamp_tag = meta.find_all("a", class_="status-info__meta-item")
    if len(timestamp_tag) > 1:
        timestamp = timestamp_tag[1].get_text(strip=True)  # The second <a> contains the timestamp
    else:
        timestamp = "No timestamp found"
else:
    timestamp = "No timestamp found"

# Extract the content inside <div class="status__content">, which contains the truth text
content = truth.find("div", class_="status__content")
if content:
    text = content.get_text(strip=True)
else:
    text = "No text found"  # Fallback if no content is found

# Analyze sentiment and market outlook
outlook, sentiment = analyze_sentiment(text)

# Print the results
print(f"Timestamp: {timestamp}")
print(f"Truth: {text}")
print(f"Sentiment: {sentiment} -> Market Outlook: {outlook}")
print("-" * 50)  # Separator

# Execute trading logic based on the sentiment
execute_trade(outlook)
