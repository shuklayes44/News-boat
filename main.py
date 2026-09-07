import os
import time
import requests
import random
import feedparser
import textwrap
from google import genai
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

GITHUB_LOGO_URL = "https://raw.githubusercontent.com/shuklayes44/News-boat/main/logo.png"

def get_font(font_size=42, bold=True):
    """Download clean Roboto/Montserrat sans-serif font for Twitter-style news card"""
    font_filename = "Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf"
    if not os.path.exists(font_filename):
        try:
            url = f"https://github.com/google/fonts/raw/main/apache/roboto/static/{font_filename}"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                with open(font_filename, "wb") as f:
                    f.write(res.content)
        except Exception as e:
            print(f"Font download error: {e}")

    if os.path.exists(font_filename):
        return ImageFont.truetype(font_filename, font_size)
    return ImageFont.load_default()

def fetch_live_google_news(topic_query):
    """Fetch fresh breaking headlines in English from Google News RSS"""
    formatted_query = topic_query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=en-IN&gl=IN&ceid=IN:en"
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
        return None, "INDIA NEWS", None

    topics = [
        ("India breaking news live updates", "INDIA NEWS"),
        ("world geopolitics breaking news", "GEOPOLITICS"),
        ("artificial intelligence tech news breaking", "TECH & AI"),
        ("ISRO NASA space exploration news", "SPACE"),
        ("stock market Nifty Sensex global economy news", "FINANCE")
    ]
    
    selected_query, category = random.choice(topics)
    print(f"Fetching Live English News for query: '{selected_query}'...")
    
    live_headline = fetch_live_google_news(selected_query)
    
    if not live_headline:
        for query, cat in topics:
            live_headline = fetch_live_google_news(query)
            if live_headline:
                category = cat
                break

    if not live_headline:
        print("Error: Could not fetch RSS news feed.")
        return None, category, None

    print(f"SUCCESS: Fresh Live Headline Fetched -> {live_headline}")

    prompt = (
        f"STRICT INSTRUCTION: Write a high-impact, professional social media post in English based on this headline:\n"
        f"HEADLINE: '{live_headline}'\n\n"
        "STRICT RULES:\n"
        "1. Write 1 Punchy Headline Line (Max 10-12 words in English).\n"
        "2. Write 2 Lines Concise Factual Summary in English.\n"
        "3. Add 4-5 high-engagement hashtags."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Updated Gemini models for google-genai SDK
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
    category_pools = {
        "INDIA NEWS": ["https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=1080&h=1080&fit=crop&q=80"],
        "GEOPOLITICS": ["https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1080&h=1080&fit=crop&q=80"],
        "TECH & AI": ["https://images.unsplash.com/photo-1518770660439-4636190af475?w=1080&h=1080&fit=crop&q=80"],
        "SPACE": ["https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&h=1080&fit=crop&q=80"],
        "FINANCE": ["https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1080&h=1080&fit=crop&q=80"]
    }
    pool = category_pools.get(category, category_pools["INDIA NEWS"])
    return random.choice(pool)

def create_news_card_overlay(base_img_url, headline_text, category_badge):
    """
    Twitter-Style News Graphic Layout:
    - Top Category Badge
    - Top Right Branding Logo Overlay
    - Dark Bottom Card Box Overlay
    - High contrast English Headline
    """
    try:
        res = requests.get(base_img_url, timeout=10)
        img = Image.open(BytesIO(res.content)).convert("RGBA").resize((1080, 1080))

        # Bottom dark overlay for text readability
        overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)
        
        draw_ov.rectangle([(0, 600), (1080, 1080)], fill=(12, 18, 28, 230))
        draw_ov.rectangle([(0, 592), (1080, 600)], fill=(225, 29, 72, 255))
        
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # Category Pill Badge (Top Left)
        badge_font = get_font(28, bold=True)
        draw.rounded_rectangle([(40, 40), (280, 95)], radius=12, fill=(225, 29, 72, 255))
        draw.text((60, 52), category_badge, fill="white", font=badge_font)

        # Logo Overlay (Top Right)
        try:
            logo_res = requests.get(GITHUB_LOGO_URL, timeout=5)
            if logo_res.status_code == 200:
                logo = Image.open(BytesIO(logo_res.content)).convert("RGBA").resize((180, 65))
                img.paste(logo, (860, 40), logo)
        except Exception as e:
            print(f"Logo Overlay Error: {e}")

        # Multiline Headline Wrapping
        clean_headline = headline_text.split(" - ")[0]
        title_font = get_font(44, bold=True)
        
        wrapped_lines = textwrap.wrap(clean_headline, width=32)
        display_lines = wrapped_lines[:3]
        
        y_text = 640
        for line in display_lines:
            draw.text((45, y_text), line, fill="#FFFFFF", font=title_font)
            y_text += 60

        output_path = "final_card.png"
        img.convert("RGB").save(output_path)
        return output_path
        
    except Exception as e:
        print(f"Pillow Graphic Overlay Error: {e}")
        return None

def upload_to_imgur(image_path):
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
        local_card_path = create_news_card_overlay(base_img, headline, category)
        
        if local_card_path:
            public_image_url = upload_to_imgur(local_card_path)
            if not public_image_url:
                public_image_url = base_img # Fallback
            
            print(f"Generated News Card Public URL: {public_image_url}")
            send_direct_to_buffer(text, public_image_url)
    else:
        print(f"Skipping Post: Gemini Generation Failed. (Headline was: {headline})")
