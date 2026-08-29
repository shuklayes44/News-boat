import os
import requests
import xml.etree.ElementTree as ET

BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

def fetch_latest_news():
    url = "https://news.google.com/rss/search?q=technology&hl=en-IN&gl=IN&ceid=IN:en"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        item = root.find('.//item')
        if item is not None:
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            
            post_text = f"🚨 TECH NEWS UPDATE 🚨\n\n{title}\n\nRead full article: {link}\n\n#TechNews #AI #Technology #Updates"
            return post_text
    return None

def send_to_buffer(post_text):
    if not BUFFER_ACCESS_TOKEN:
        print("Error: BUFFER_ACCESS_TOKEN Secret missing hai!")
        return

    # 1. Connected Profiles Fetch Karna
    profiles_url = f"https://api.bufferapp.com/1/profiles.json?access_token={BUFFER_ACCESS_TOKEN}"
    res = requests.get(profiles_url)
    
    if res.status_code != 200:
        print("Buffer Auth/Profile Error:", res.text)
        return

    profiles = res.json()
    if not profiles:
        print("Buffer account me koi Social Media Channel connected nahi milaa!")
        return

    # 2. Daily Post Create Karna
    create_url = f"https://api.bufferapp.com/1/updates/create.json?access_token={BUFFER_ACCESS_TOKEN}"
    
    for p in profiles:
        profile_id = p.get("id")
        payload = {
            "text": post_text,
            "profile_ids[]": profile_id,
            "now": "true"
        }
        post_res = requests.post(create_url, data=payload)
        print(f"Post Result for Profile {profile_id}:", post_res.text)

if __name__ == "__main__":
    text = fetch_latest_news()
    if text:
        send_to_buffer(text)
    else:
        print("News Fetch Nahi Ho Payi!")
