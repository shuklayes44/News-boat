import os
import requests

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

def fetch_latest_news():
    url = f"https://newsapi.org/v2/top-headlines?category=technology&language=en&pageSize=5&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    data = response.json()
    
    if data.get("status") == "ok" and data.get("articles"):
        article = data["articles"][0]
        title = article.get("title", "")
        description = article.get("description", "")
        source_url = article.get("url", "")
        
        post_text = f"🚨 TECH NEWS UPDATE 🚨\n\n{title}\n\n📌 {description}\n\nRead full article: {source_url}\n\n#TechNews #AI #Technology #Updates"
        return post_text
    return None

def get_buffer_profiles():
    # Buffer me connected Social Media Profiles ki IDs fetch karna
    url = f"https://api.bufferapp.com/1/profiles.json?access_token={BUFFER_ACCESS_TOKEN}"
    response = requests.get(url)
    
    if response.status_code == 200:
        profiles = response.json()
        return [p["id"] for p in profiles]
    else:
        print("Error fetching Buffer profiles:", response.text)
        return []

def send_to_buffer(post_text):
    profile_ids = get_buffer_profiles()
    
    if not profile_ids:
        print("Error: Buffer se koi connected social account nahi mila. Buffer dashboard check karein!")
        return

    url = f"https://api.bufferapp.com/1/updates/create.json?access_token={BUFFER_ACCESS_TOKEN}"
    
    # Sabhi connected accounts (X aur Insta) par post publish karna
    for p_id in profile_ids:
        payload = {
            "text": post_text,
            "profile_ids[]": p_id,
            "now": True  # Immediate auto-post ke liye
        }
        response = requests.post(url, data=payload)
        
        if response.status_code == 200:
            print(f"Successfully posted to Profile ID: {p_id}")
        else:
            print(f"Failed to post on Profile ID {p_id}:", response.text)

if __name__ == "__main__":
    text = fetch_latest_news()
    if text:
        send_to_buffer(text)
    else:
        print("No news fetched!")
