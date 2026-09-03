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
        return None, "breaking news"

    topics = [
        ("India breaking news live when:1d", "India news infrastructure"),
        ("world geopolitics breaking news when:1d", "global geopolitics news"),
        ("technology AI launch breaking news when:1d", "technology artificial intelligence"),
        ("ISRO NASA space breaking news when:1d", "space rocket exploration"),
        ("stock market economy breaking news India when:1d", "stock market trading finance")
    ]
    
    selected_query, image_search_keyword = random.choice(topics)
    print(f"Fetching Urgent 24h Breaking News for query: '{selected_query}'...")
    
    live_headline = fetch_live_google_news(selected_query)
    
    if not live_headline:
        print("No urgent RSS headline found, retrying alternative breaking topic...")
        for query, keyword in topics:
            live_headline = fetch_live_google_news(query)
            if live_headline:
                image_search_keyword = keyword
                break

    if not live_headline:
        print("Error: Could not fetch real live news RSS feed. Aborting execution.")
        return None, image_search_keyword

    print(f"SUCCESS: Urgent Breaking Headline Fetched -> {live_headline}")

    prompt = (
        f"STRICT INSTRUCTION: Write a factual breaking news post based ONLY on this real-world headline:\n"
        f"HEADLINE: '{live_headline}'\n\n"
        "STRICT FORMATTING RULES:\n"
        "1. Language: Professional Indian English.\n"
        "2. Keep it punchy, factual, and strictly relevant to this breaking event.\n"
        "3. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with relevant Emoji\n"
        "   - Line 2-3: Core factual breaking news summary\n"
        "   - Line 4: Engagement question for audience\n"
        "   - Line 5: 4-5 dynamic trending hashtags matching THIS exact news\n"
        "4. ABSOLUTELY DO NOT ADD ANY SYSTEM CODE TAGS LIKE #WSX_1234 AT THE END.\n"
        "5. Total Length: Under 230 characters."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            text = response.text.strip()
            return text, image_search_keyword
        except Exception as e:
            print(f"Gemini API Attempt {attempt+1} Failed: {e}")
            time.sleep(2)
            
    return None, image_search_keyword

def get_dynamic_unique_image_url(keyword):
    """Generates 100% UNIQUE HD photo URL directly matching news search terms (no repeating list)"""
    encoded_keyword = urllib.parse.quote(keyword)
    random_sig = random.randint(10000, 999999)
    # Dynamic Unsplash Engine with random signature bypasses caching and fixed groups
    return f"https://source.unsplash.com/1080x1080/?{encoded_keyword}&sig={random_sig}"

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
    text, image_keyword = generate_news_with_gemini()
    if text:
        image_url = get_dynamic_unique_image_url(image_keyword)
        print(f"Final Dynamic Image URL: {image_url}")
        print(f"Post Text:\n{text}")
        send_direct_to_buffer(text, image_url)
    else:
        print("Skipping execution: Live RSS news fetch failed.")
