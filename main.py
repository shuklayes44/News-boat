import os
import time
import requests
import random
import feedparser
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_live_google_news(topic_query):
    """Fetches real-time headlines directly using Google News RSS feed"""
    formatted_query = topic_query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            # Random pick from top 10 to avoid repetitive posts
            selected = random.choice(feed.entries[:10])
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
    
    live_headline = fetch_live_google_news(selected_query)
    prompt_content = f"LIVE BREAKING NEWS HEADLINE: '{live_headline}'" if live_headline else f"TOPIC: '{selected_query}'"

    prompt = (
        f"You are the senior journalist for 'WorldScopeX'. Create a high-impact viral post based on this live news:\n"
        f"{prompt_content}\n\n"
        "STRICT RULES:\n"
        "1. Language: Professional Indian English.\n"
        "2. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with Emoji\n"
        "   - Line 2-3: Core factual news summary\n"
        "   - Line 4: Engagement question\n"
        "   - Line 5: 4-5 dynamic trending hashtags matching THIS specific news (e.g. #BreakingNews #TechNews #WorldScopeX)\n"
        "3. STRICTLY DO NOT ADD ANY NUMERIC CODE TAGS OR SYSTEM CODES LIKE #WSX_1234 AT THE END.\n"
        "4. Total Length: Strictly under 240 characters."
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

def get_direct_stock_image_url(keyword):
    """Returns stable direct HD Unsplash Image URL without rendering overhead"""
    images_pool = [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1080&q=80",
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1080&q=80",
        "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1080&q=80",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&q=80",
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1080&q=80",
        "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=1080&q=80",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1080&q=80"
    ]
    return random.choice(images_pool)

def send_to_buffer_graphql(post_text, image_url):
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
        
        metadata_param = ', metadata: { instagram: { type: post, shouldShareToFeed: true } }' if service.lower() == 'instagram' else ''
        media_input = f', assets: [{{ image: {{ url: "{image_url}" }} }}]'

        mutation = f"""
        mutation {{
            createPost(input: {{
                channelId: "{ch_id}",
                text: {requests.compat.json.dumps(post_text)},
                schedulingType: automatic,
                mode: shareNow{metadata_param}{media_input}
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
        print(f"Result for {service} ({ch_id}): {post_res.text}")

if __name__ == "__main__":
    text, image_keyword = generate_news_with_gemini()
    if text:
        image_url = get_direct_stock_image_url(image_keyword)
        print(f"Final Image URL: {image_url}")
        print(f"Post Text:\n{text}")
        send_to_buffer_graphql(text, image_url)
