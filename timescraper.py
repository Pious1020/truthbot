import requests
from bs4 import BeautifulSoup
import csv

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

# CSV file to save the results
csv_file = "trump_truths_timestamps.csv"

# Open CSV file and write header
with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp"])

    # Loop through the truth posts
    for truth in truths:
        # Extract the timestamp
        meta = truth.find_previous("div", class_="status-info__body")
        if meta:
            timestamp_tag = meta.find_all("a", class_="status-info__meta-item")
            if len(timestamp_tag) > 1:
                timestamp = timestamp_tag[1].get_text(strip=True)
            else:
                timestamp = "No timestamp found"
        else:
            timestamp = "No timestamp found"

        # Write to CSV
        writer.writerow([timestamp])
        print(f"Saved: {timestamp}")

print(f"\n✅ Done! Saved {len(truths)} timestamps to {csv_file}")
