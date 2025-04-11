import requests
import csv
from datetime import datetime, timedelta

API_KEY = '4LN57MX3WQRKMU6S'
SYMBOL = 'SPY'

# Replace with your real timestamps
timestamps = [
    "April 11, 2025, 12:42 PM",
    "April 11, 2025, 12:39 PM",
    "April 11, 2025, 12:25 PM",
    "April 11, 2025, 12:21 PM",
    "April 11, 2025, 12:21 PM",
    "April 11, 2025, 12:19 PM",
    "April 11, 2025, 12:19 PM",
    "April 11, 2025, 9:52 AM",
    "April 11, 2025, 9:35 AM",
    "April 11, 2025, 9:20 AM",
    "April 10, 2025, 3:06 PM",
    "April 10, 2025, 3:03 PM",
    "April 10, 2025, 11:28 AM",
    "April 10, 2025, 10:52 AM",
    "April 10, 2025, 9:38 AM",
    "April 10, 2025, 9:35 AM",
    "April 10, 2025, 8:28 AM",
    "April 9, 2025, 1:18 PM",
    "April 9, 2025, 12:16 PM",
    "April 9, 2025, 9:37 AM",
    "April 9, 2025, 9:33 AM",
    "April 9, 2025, 9:25 AM",
    "April 9, 2025, 8:58 AM"

]

def get_1min_intraday(symbol, date):
    url = f'https://www.alphavantage.co/query'
    params = {
        'function': 'TIME_SERIES_INTRADAY',
        'symbol': symbol,
        'interval': '1min',
        'outputsize': 'full',
        'apikey': API_KEY
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get("Time Series (1min)", {})
    else:
        print(f"Error fetching data for {symbol} on {date}")
        return {}

# Convert timestamps to datetime
timestamp_objects = [datetime.strptime(ts, "%B %d, %Y, %I:%M %p") for ts in timestamps]

# Track all data
all_rows = []

for ts in timestamp_objects:
    print(f"Fetching data for {ts}...")

    intraday_data = get_1min_intraday(SYMBOL, ts.date())

    # Find 2 minutes before to 2 minutes after
    for i in range(-2, 3):
        minute = ts + timedelta(minutes=i)
        key = minute.strftime('%Y-%m-%d %H:%M:%S')

        if key in intraday_data:
            data = intraday_data[key]
            all_rows.append([
                key,
                data['1. open'],
                data['2. high'],
                data['3. low'],
                data['4. close'],
                data['5. volume']
            ])

# Save to CSV
with open('spy_vantage_window.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    writer.writerows(all_rows)

print("✅ Data saved to spy_vantage_window.csv")
