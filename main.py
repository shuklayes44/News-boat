import os
import time
import requests
import random
import io
import base64
import feedparser
from google import genai
from PIL import Image, ImageDraw

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_live_google_news(topic_query):
    formatted_query = topic_query.replace(' ', '+')
    # YAHAN RSS FEED CHAL RAHA HAI
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            # Top 5 headlines me se random headline fetch karna duplication prevent karta hai
            selected = random.choice(feed.entries[:5])
            return selected.title
    except Exception as e:
        print(f"Google News RSS Error: {e}")
    return None

def generate_news_with_gemini():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing!")
        return None, "space"

    topics = [
        ("technology artificial intelligence hardware", "technology"),
        ("stock market finance global business", "business"),
        ("geopolitics international relations diplomacy", "politics"),
        ("space exploration defense technology science", "space"),
        ("India infrastructure highways mega projects", "infrastructure")
    ]
    
    selected_query, image_keyword = random.choice(topics)
    print(f"Fetching Live Google News for query: '{selected_query}'...")
    
    # Live headline fetch logic call
    live_headline = fetch_live_google_news(selected_query)
    prompt_content = f"LIVE BREAKING NEWS: '{live_headline}'" if live_headline else f"TOPIC: '{selected_query}'"

    prompt = (
        f"You are the senior journalist for 'WorldScopeX'. Create a high-impact viral post:\n"
        f"{prompt_content}\n\n"
        "STRICT RULES:\n"
        "1. Language: Professional Indian English.\n"
        "2. Factual news summary.\n"
        "3. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with Emoji\n"
        "   - Line 2-3: Core factual news summary\n"
        "   - Line 4: Engagement question\n"
        "   - Line 5: #WorldScopeX #NewsUpdate #Global #Tech\n"
        "4. Total Length: Strictly 200 to 230 characters."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            text = response.text.strip()
            return text, image_keyword
        except Exception as e:
            print(f"Gemini API Attempt {attempt+1} Failed: {e}")
            time.sleep(2)
            
    return None, "space"

# ... (Logo rendering aur Buffer posting functions yahan intact hain) ...

if __name__ == "__main__":
    text, image_keyword = generate_news_with_gemini()
    # (image processing aur buffer logic yahan run hogi)
