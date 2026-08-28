import os
import requests

# GitHub Secrets se Webhook URL aur News API key fetch karna
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")

def fetch_latest_news():
    # Fresh Technology News Fetching
    url = f"https://newsapi.org/v2/top-headlines?category=technology&language=en&pageSize=5&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    data = response.json()
    
    if data.get("status") == "ok" and data.get("articles"):
        article = data["articles"][0]
        title = article.get("title", "")
        description = article.get("description", "")
        source_url = article.get("url", "")
        
        # Social Media Post Content Format
        post_text = f"🚨 TECH NEWS UPDATE 🚨\n\n{title}\n\n📌 {description}\n\nRead more: {source_url}\n\n#TechNews #Updates #AI #Trending"
        return post_text
    else:
        print("News fetch karne me issue aaya ya content khali hai.")
        return None

def send_to_webhook(post_text):
    if not MAKE_WEBHOOK_URL:
        print("Error: MAKE_WEBHOOK_URL secret missing hai!")
        return
        
    payload = {"text": post_text}
    response = requests.post(MAKE_WEBHOOK_URL, json=payload)
    
    if response.status_code == 200:
        print("Successfully sent to Make.com Webhook!")
    else:
        print(f"Webhook error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    text = fetch_latest_news()
    if text:
        send_to_webhook(text)
