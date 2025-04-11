import os
import time
import logging
import random
import sys
import json
from curl_cffi import requests as cf_requests
import requests
import platform
import tqdm
from transformers import pipeline
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta
from truthbrush import Api
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Cookie storage files
COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "truth_social_cookies.json")
CF_COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "truth_social_cf_cookies.json")

def get_auth_token():
    """Get basic auth token"""
    credentials = f"{os.getenv('TRUTHSOCIAL_USERNAME')}:{os.getenv('TRUTHSOCIAL_PASSWORD')}"
    return base64.b64encode(credentials.encode()).decode()

def bypass_cloudflare_auth():
    """Bypass Cloudflare and authenticate"""
    session = cf_requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://truthsocial.com',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Authorization': f'Basic {get_auth_token()}'
    })
    
    try:
        # First get Cloudflare cookies
        logging.info("Getting initial Cloudflare cookies...")
        response = session.get(
            'https://truthsocial.com/',
            impersonate="chrome",
            timeout=30
        )
        
        if response.status_code != 200:
            logging.error(f"Initial request failed: {response.status_code}")
            return None
            
        # Now try to authenticate
        logging.info("Attempting authentication...")
        auth_response = session.post(
            'https://truthsocial.com/api/v1/accounts/verify_credentials',
            impersonate="chrome",
            timeout=30
        )
        
        if auth_response.status_code == 200:
            cookies = dict(session.cookies)
            # Save all cookies
            with open(CF_COOKIES_FILE, 'w') as f:
                json.dump(cookies, f)
            logging.info(f"Saved {len(cookies)} cookies")
            return cookies
        else:
            logging.error(f"Authentication failed: {auth_response.status_code}")
            
    except Exception as e:
        logging.error(f"Cloudflare bypass failed: {e}")
    
    return None

def create_api_instance():
    """Create API instance with Cloudflare bypass"""
    # Try to load or obtain Cloudflare cookies
    cf_cookies = {}
    try:
        if os.path.exists(CF_COOKIES_FILE):
            with open(CF_COOKIES_FILE, 'r') as f:
                cf_cookies = json.load(f)
                cookie_age = time.time() - os.path.getmtime(CF_COOKIES_FILE)
                if cookie_age > 1800:  # Cookies older than 30 minutes
                    logging.info("Cookies expired, obtaining new ones...")
                    cf_cookies = bypass_cloudflare_auth() or {}
        else:
            logging.info("No cookies found, obtaining new ones...")
            cf_cookies = bypass_cloudflare_auth() or {}
    except Exception as e:
        logging.error(f"Error handling cookies: {e}")
        cf_cookies = {}

    # Initialize API
    api = Api(
        username=os.getenv("TRUTHSOCIAL_USERNAME"),
        password=os.getenv("TRUTHSOCIAL_PASSWORD")
    )
    
    # Add cookies to API session
    if hasattr(api, '_session') and cf_cookies:
        for key, value in cf_cookies.items():
            api._session.cookies.set(key, value)
            logging.debug(f"Added cookie: {key}")
        
        # Also update headers
        api._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://truthsocial.com',
            'Authorization': f'Basic {get_auth_token()}'
        })
    
    return api

def fetch_posts_with_retry(username, max_retries=5, initial_delay=15):
    """Fetch posts with retry logic and Cloudflare bypass"""
    global truth_api
    posts = []
    delay = initial_delay
    errors = 0
    
    print(f"Fetching posts from @{username}...")
    
    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"Attempt {attempt}/{max_retries} to fetch posts")
            
            # Create new API instance with fresh cookies on retries
            if attempt > 1:
                logging.info("Rotating session with new cookies...")
                truth_api = create_api_instance()
                time.sleep(random.uniform(2, 5))
            
            # Fetch posts
            posts_iterator = truth_api.pull_statuses(username, replies=False)
            posts = list(posts_iterator) if posts_iterator else []
            
            if posts:
                logging.info(f"Successfully fetched {len(posts)} posts")
                return posts
            else:
                logging.warning("No posts found")
                
        except Exception as e:
            errors += 1
            error_msg = str(e)
            logging.error(f"Error on attempt {attempt}: {error_msg}")
            
            if "Cloudflare" in error_msg or "403" in error_msg:
                logging.info("Detected Cloudflare block, obtaining new cookies...")
                if bypass_cloudflare_auth():
                    truth_api = create_api_instance()
            
            if attempt < max_retries:
                wait_time = min(delay * (1.5 ** (attempt - 1)), 120)
                print(f"\nRetrying in {wait_time:.1f} seconds... (Attempt {attempt + 1}/{max_retries})")
                
                try:
                    for _ in tqdm.tqdm(range(int(wait_time * 10)), 
                                     desc="Waiting",
                                     bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}",
                                     unit="0.1s"):
                        time.sleep(0.1)
                except Exception:
                    time.sleep(wait_time)
            else:
                logging.error("Max retries reached")
                break
    
    return posts

def analyze_and_trade(posts):
    """Analyze posts and execute trades"""
    if not posts:
        logging.warning("No posts to analyze")
        return
        
    sentiment_analyzer = pipeline("sentiment-analysis")
    
    for post in posts[:5]:  # Analyze latest 5 posts
        content = post["content"]
        sentiment = sentiment_analyzer(content)[0]
        
        print(f"\nPost: {content}")
        print(f"Sentiment: {sentiment['label']} ({sentiment['score']:.2f})")
        
        if sentiment['score'] < 0.9:
            continue  # Skip weak signals
        
        try:
            position = alpaca.get_position("SPY")
        except:
            position = None
        
        if sentiment['label'] == "POSITIVE" and (not position or float(position.qty) <= 0):
            print("\nBUYING SPY 🚀")
            try:
                alpaca.submit_order(
                    symbol="SPY",
                    qty=1,
                    side="buy",
                    type="market",
                    time_in_force="gtc"
                )
            except Exception as e:
                logging.error(f"Buy order failed: {e}")
                
        elif sentiment['label'] == "NEGATIVE" and position and float(position.qty) > 0:
            print("\nSELLING SPY 💥")
            try:
                alpaca.submit_order(
                    symbol="SPY",
                    qty=1,
                    side="sell",
                    type="market",
                    time_in_force="gtc"
                )
            except Exception as e:
                logging.error(f"Sell order failed: {e}")
        
        time.sleep(1)  # Rate limiting

def main():
    """Main execution flow"""
    print("Starting Trump Truth Social Trading Bot")
    print("=======================================")
    
    try:
        # Initialize API with Cloudflare bypass
        global truth_api, alpaca
        truth_api = create_api_instance()
        
        # Initialize Alpaca
        alpaca = tradeapi.REST(
            os.getenv("ALPACA_API_KEY"),
            os.getenv("ALPACA_SECRET_KEY"),
            base_url=os.getenv("ALPACA_BASE_URL")
        )
        
        # Fetch and analyze posts
        username = "realDonaldTrump"
        posts = fetch_posts_with_retry(username)
        analyze_and_trade(posts)
        
        print("\nExecution completed successfully")
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
