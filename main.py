import os
import time
import requests
import random
import urllib.parse
import feedparser
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_live_google_news(topic_query):
    """Fetches STRICT 24-Hour Breaking News Headlines from Google RSS"""
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
        "3. ABSOLUTELY DO NOT ADD ANY SYSTEM CODE TAGS AT THE END.\n"
        "4. Total Length: Under 230 characters."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Updated Gemini API Model Names (As requested in logs)
    models_to_try = ['gemini-3.6-flash', 'gemini-2.5-flash']
    
    for model_name in models_to_try:
        print(f"Attempting content generation using model: {model_name}...")
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = response.text.strip()
                return text, category
            except Exception as e:
                print(f"Gemini API ({model_name}) Attempt {attempt+1} Failed: {e}")
                time.sleep(2)
                
    return None, category

def get_dynamic_unique_image_url(news_text, category):
    """Fetches Dynamic HD Image using Pexels or Working Direct CDN Pools"""
    words = [w.strip("!?:;,'\"") for w in news_text.split() if len(w) > 3 and not w.startswith("#")]
    search_keyword = words[0] if words else category

    # Option 1: Pexels API
    if PEXELS_API_KEY:
        try:
            pex_url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(search_keyword)}&per_page=15"
            pex_headers = {"Authorization": PEXELS_API_KEY}
            res = requests.get(pex_url, headers=pex_headers, timeout=5)
            if res.status_code == 200:
                photos = res.json().get('photos', [])
                if photos:
                    selected = random.choice(photos)
                    return selected['src']['large2x']
        except Exception as e:
            print(f"Pexels API Fetch Error: {e}")

    # Option 2: Direct Unsplash CDN Fallback Pool
    category_pools = {
        "india": [
            "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1532375810709-75b1da00537c?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1587474260584-136574528ed5?w=1080&h=1080&fit=crop&q=80"
        ],
        "geopolitics": [
            "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=1080&h=1080&fit=crop&q=80"
        ],
        "technology": [
            "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=1080&h=1080&fit=crop&q=80"
        ],
        "space": [
            "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1517976487492-5750f3195933?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=1080&h=1080&fit=crop&q=80"
        ],
        "finance": [
            "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=1080&h=1080&fit=crop&q=80",
            "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?w=1080&h=1080&fit=crop&q=80"
        ]
    }
    
    pool = category_pools.get(category, category_pools["india"])
    selected_base = random.choice(pool)
    random_sig = random.randint(1000, 99999)
    return f"{selected_base}&sig={random_sig}"

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
        print("Error: No Buffer Organization Found!")
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
        image_url = get_dynamic_unique_image_url(text, category)
        print(f"Final Matching Image URL: {image_url}")
        print(f"Post Text:\n{text}")
        send_direct_to_buffer(text, image_url)
    else:
        print("Skipping execution: Live RSS news fetch failed.")
