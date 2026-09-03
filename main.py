import os
import time
import requests
import random
import urllib.parse
import feedparser
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_live_google_news(topic_query):
    """Fetches STRICT 24-Hour Real Live Breaking News Headlines from Google News RSS"""
    formatted_query = topic_query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries and len(feed.entries) > 0:
            selected = random.choice(feed.entries[:5])
            return selected.title
    except Exception as e:
        print(f"Google News RSS Error: {e}")
    return None

def generate_news_with_gemini():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing!")
        return None, "india"

    # Strictly 24h Breaking Topics + Matching HD Image Categories
    topics = [
        ("India breaking news live updates when:1d", "india"),
        ("world geopolitics breaking news live when:1d", "geopolitics"),
        ("technology AI news breaking launch when:1d", "technology"),
        ("ISRO NASA space launch breaking news when:1d", "space"),
        ("stock market Nifty Sensex breaking news when:1d", "finance")
    ]
    
    selected_query, category = random.choice(topics)
    print(f"Fetching 24h Live Breaking News for query: '{selected_query}'...")
    
    live_headline = fetch_live_google_news(selected_query)
    
    # Fallback Loop
    if not live_headline:
        print("Primary query skipped, checking fallback 24h news topics...")
        for query, cat in topics:
            live_headline = fetch_live_google_news(query)
            if live_headline:
                category = cat
                break

    if not live_headline:
        print("Error: Could not fetch real live news RSS feed. Aborting execution.")
        return None, category

    print(f"SUCCESS: Fresh Live Headline Fetched -> {live_headline}")

    prompt = (
        f"STRICT INSTRUCTION: Write a high-impact, factual breaking news post based ONLY on this live headline:\n"
        f"HEADLINE: '{live_headline}'\n\n"
        "STRICT FORMATTING RULES:\n"
        "1. Language: Professional Indian English.\n"
        "2. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with relevant Emoji\n"
        "   - Line 2-3: Core factual news summary\n"
        "   - Line 4: Short engagement question for audience\n"
        "   - Line 5: 4-5 dynamic trending hashtags matching THIS exact news\n"
        "3. ABSOLUTELY DO NOT ADD ANY SYSTEM CODE TAGS LIKE #WSX_1234 AT THE END.\n"
        "4. Total Length: Under 230 characters."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            text = response.text.strip()
            return text, category
        except Exception as e:
            print(f"Gemini API Attempt {attempt+1} Failed: {e}")
            time.sleep(2)
            
    return None, category

def get_dynamic_unique_image_url(category):
    """Generates 100% Unique, Dynamic HD Image URL fully compatible with Instagram & Twitter"""
    category_photos = {
        "india": [
            "photo-1532375810709-75b1da00537c", "photo-1524492412937-b28074a5d7da", 
            "photo-1587474260584-136574528ed5", "photo-1506461883276-594a12b11cf3"
        ],
        "geopolitics": [
            "photo-1541872703-74c5e44368f9", "photo-1486406146926-c627a92ad1ab", 
            "photo-1526304640581-d334cdbbf45e", "photo-1529107386315-e1a2ed48a620"
        ],
        "technology": [
            "photo-1518770660439-4636190af475", "photo-1526374965328-7f61d4dc18c5", 
            "photo-1485827404703-89b55fcc595e", "photo-1531297484001-80022131f5a1"
        ],
        "space": [
            "photo-1451187580459-43490279c0fa", "photo-1517976487492-5750f3195933", 
            "photo-1446776811953-b23d57bd21aa", "photo-1506703719100-a0f3a48c0f86"
        ],
        "finance": [
            "photo-1611974789855-9c2a0a7236a3", "photo-1590283603385-17ffb3a7f29f", 
            "photo-1535320903710-d993d3d77d29", "photo-1460925895917-afdab827c52f"
        ]
    }
    photo_list = category_photos.get(category, category_photos["india"])
    selected_photo = random.choice(photo_list)
    random_sig = random.randint(1000, 99999)
    # Direct high-res cropped 1080x1080 CDN URL with random cache-busting signature
    return f"https://images.unsplash.com/{selected_photo}?w=1080&h=1080&fit=crop&q=80&sig={random_sig}"

def send_direct_to_buffer(post_text, image_url):
    """Posts INSTANTLY to live social media channels via Buffer Direct Publish Engine"""
    if not BUFFER_ACCESS_TOKEN or not image_url:
        print("Error: BUFFER_ACCESS_TOKEN or Image URL Missing!")
        return

    url = "https://api.buffer.com/graphql"
    headers = {
        "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    acc_res = requests.post(url, json={"query": "query GetAccount { account { organizations { id } } }"}, headers=headers)
    orgs = acc_res.json().get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        return
    org_id = orgs[0].get("id")

    ch_res = requests.post(
        url,
        json={"query": "query GetChannels($input: ChannelsInput!) { channels(input: $input) { id service } }", "variables": {"input": {"organizationId": org_id}}},
        headers=headers
    )
    channels = ch_res.json().get("data", {}).get("channels", [])

    for ch in channels:
        ch_id = ch.get("id")
        service = ch.get("service")
        
        extra_metadata = ', metadata: { instagram: { type: post, shouldShareToFeed: true } }' if service.lower() == 'instagram' else ''
        media_asset = f', assets: [{{ image: {{ url: "{image_url}" }} }}]'

        mutation = f"""
        mutation {{
            createPost(input: {{
                channelId: "{ch_id}",
                text: {requests.compat.json.dumps(post_text)},
                schedulingType: automatic,
                mode: shareNow{extra_metadata}{media_asset}
            }}) {{
                ... on PostActionSuccess {{
                    post {{ id status }}
                }}
                ... on MutationError {{
                    message
                }}
            }}
        }}
        """
        post_res = requests.post(url, json={"query": mutation}, headers=headers)
        print(f"Direct Post Result for {service} ({ch_id}): {post_res.text}")

if __name__ == "__main__":
    text, category = generate_news_with_gemini()
    if text:
        image_url = get_dynamic_unique_image_url(category)
        print(f"Final Image URL: {image_url}")
        print(f"Post Text:\n{text}")
        send_direct_to_buffer(text, image_url)
    else:
        print("Skipping execution: Live RSS news fetch failed.")
