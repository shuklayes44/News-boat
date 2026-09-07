import os
import time
import requests
import random
import urllib.parse
import feedparser
from google import genai
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Repository Logo URL
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/shuklayes44/News-boat/main/logo.png"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def get_hindi_font(font_size=46):
    """Google Fonts se Auto-Download Hindi Font (Hind-Bold)"""
    font_path = "Hind-Bold.ttf"
    if not os.path.exists(font_path):
        try:
            print("Downloading Hindi Font (Hind-Bold)...")
            font_url = "https://github.com/google/fonts/raw/main/ofl/hind/Hind-Bold.ttf"
            res = requests.get(font_url, timeout=10)
            if res.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(res.content)
        except Exception as e:
            print(f"Font download error: {e}")

    if os.path.exists(font_path):
        return ImageFont.truetype(font_path, font_size)
    return ImageFont.load_default()

def fetch_live_google_news(topic_query):
    """Google News RSS Feed se Hindi Breaking Headlines Fetch Karna"""
    formatted_query = topic_query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=hi&gl=IN&ceid=IN:hi"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries and len(feed.entries) > 0:
            selected = random.choice(feed.entries[:10])
            return selected.title
    except Exception as e:
        print(f"Google News RSS Error: {e}")
    return None

def generate_news_with_gemini():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing!")
        return None, "india", None

    # Topics List
    topics = [
        ("India breaking news live updates hindi", "india"),
        ("world geopolitics breaking news hindi", "geopolitics"),
        ("technology AI news breaking hindi", "technology"),
        ("ISRO NASA space launch news hindi", "space"),
        ("stock market Nifty Sensex breaking news hindi", "finance")
    ]
    
    selected_query, category = random.choice(topics)
    print(f"Fetching Live Breaking News for query: '{selected_query}'...")
    
    live_headline = fetch_live_google_news(selected_query)
    
    if not live_headline:
        for query, cat in topics:
            live_headline = fetch_live_google_news(query)
            if live_headline:
                category = cat
                break

    if not live_headline:
        print("Error: Could not fetch real live news RSS feed.")
        return None, category, None

    print(f"SUCCESS: Fresh Live Headline Fetched -> {live_headline}")

    prompt = (
        f"STRICT INSTRUCTION: Write a high-impact, short news post in pure Hindi based on this headline:\n"
        f"HEADLINE: '{live_headline}'\n\n"
        "STRICT RULES:\n"
        "1. Write 1 Punchy Line Headline (Max 10-12 words in Hindi).\n"
        "2. Write 2 Lines Factual Summary in Hindi.\n"
        "3. Add 4-5 relevant hashtags."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Exact Working Models for google-genai SDK
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    
    for model_name in models_to_try:
        print(f"Attempting content generation using model: {model_name}...")
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    text = response.text.strip()
                    print(f"SUCCESS: Generated content using {model_name}")
                    return text, category, live_headline
            except Exception as e:
                print(f"Gemini API ({model_name}) Attempt {attempt+1} Failed: {e}")
                time.sleep(2)
                
    return None, category, live_headline

def get_dynamic_base_image(category):
    """Category wise dynamic HD images"""
    category_pools = {
        "india": ["https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=1080&h=1080&fit=crop&q=80"],
        "geopolitics": ["https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1080&h=1080&fit=crop&q=80"],
        "technology": ["https://images.unsplash.com/photo-1518770660439-4636190af475?w=1080&h=1080&fit=crop&q=80"],
        "space": ["https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&h=1080&fit=crop&q=80"],
        "finance": ["https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1080&h=1080&fit=crop&q=80"]
    }
    pool = category_pools.get(category, category_pools["india"])
    return random.choice(pool)

def create_news_card_overlay(base_img_url, headline_text):
    """News Card Graphic Generation with Pillow"""
    try:
        res = requests.get(base_img_url, timeout=10)
        img = Image.open(BytesIO(res.content)).convert("RGBA").resize((1080, 1080))

        # Bottom Overlay Gradient
        overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)
        draw_ov.rectangle([(0, 620), (1080, 1080)], fill=(0, 0, 0, 200)) # Dark Overlay
        draw_ov.rectangle([(0, 610), (1080, 620)], fill=(255, 0, 0, 255)) # Red Accent Line
        img = Image.alpha_composite(img, overlay)

        draw = ImageDraw.Draw(img)

        # Hindi Font Auto Load
        font = get_hindi_font(46)

        # Headline Text Formatting
        headline_clean = headline_text.split(" - ")[0]
        draw.text((40, 700), headline_clean[:75], fill="yellow", font=font)

        # Logo Paste
        try:
            logo_res = requests.get(GITHUB_LOGO_URL, timeout=5)
            if logo_res.status_code == 200:
                logo = Image.open(BytesIO(logo_res.content)).convert("RGBA").resize((180, 70))
                img.paste(logo, (850, 40), logo)
        except Exception as e:
            print(f"Logo Paste Error: {e}")

        output_path = "final_card.png"
        img.convert("RGB").save(output_path)
        return output_path
    except Exception as e:
        print(f"Pillow Overlay Error: {e}")
        return None

def upload_to_imgur(image_path):
    """Imgur Direct Upload for Public HTTP Image Link"""
    try:
        headers = {"Authorization": "Client-ID 544172540b707d0"}
        with open(image_path, "rb") as file:
            res = requests.post("https://api.imgur.com/3/upload", headers=headers, files={"image": file})
            data = res.json()
            if data.get("success"):
                return data["data"]["link"]
    except Exception as e:
        print(f"Imgur Upload Error: {e}")
    return None

def send_direct_to_buffer(post_text, image_url):
    """Buffer API Integration for Direct Posting"""
    if not BUFFER_ACCESS_TOKEN or not image_url:
        print("Error: Missing Access Token or Image URL!")
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
        print(f"Post Result for {service}: {post_res.text}")

if __name__ == "__main__":
    text, category, headline = generate_news_with_gemini()
    if text and headline:
        base_img = get_dynamic_base_image(category)
        local_card_path = create_news_card_overlay(base_img, headline)
        
        if local_card_path:
            public_image_url = upload_to_imgur(local_card_path)
            if not public_image_url:
                public_image_url = base_img # Fallback
            
            print(f"Generated News Card Public URL: {public_image_url}")
            send_direct_to_buffer(text, public_image_url)
    else:
        print(f"Skipping Post: Gemini Generation Failed. (Headline was: {headline})")
