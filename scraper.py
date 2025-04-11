import requests
from bs4 import BeautifulSoup
from transformers import pipeline

# Initialize the sentiment analysis pipeline
sentiment_analyzer = pipeline("sentiment-analysis")

# URL of the website to scrape
url = "https://trumpstruth.org/?per_page=50"
headers = {
    "User-Agent": "Mozilla/5.0"
}

# Send GET request to the website
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, "html.parser")

# Find all truth posts within the div class "status__body"
truths = soup.find_all("div", class_="status__body")

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

# Loop through the truth posts and analyze sentiment
for truth in truths:
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