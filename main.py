import os
import time
import requests
import random
import urllib.parse
import feedparser
import textwrap
from google import genai
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

GITHUB_LOGO_URL = "https://raw.githubusercontent.com/shuklayes44/News-boat/main/logo.png"

def get_font(font_size=42, bold=True):
    """Downloads Roboto/Montserrat clean font for News Banner Cards"""
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
    """Fetches Breaking News Headlines from Google RSS"""
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
        return None, "india", None

    topics = [
        ("India breaking news live updates", "india"),
        ("world geopolitics breaking news live", "geopolitics"),
        ("technology AI news breaking launch", "technology"),
        ("ISRO NASA space launch breaking news", "space"),
        ("stock market Nifty Sensex breaking news", "finance")
    ]
    
    selected_query, category = random.choice(topics)
    print(f"Fetching Live Breaking News for query: '{selected_query}'...")
    
    live_headline = fetch_live_google_news(selected_query)
    
    if not live_headline:
        print("Primary query skipped, checking fallback news topics...")
        for query, cat in topics:
            live_headline = fetch_live_google_news(query)
            if live_headline:
                category = cat
                break

    if not live_headline:
        print("Error: Could not fetch real live news RSS feed. Aborting execution.")
        return None, category, None

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
    
    # Same Gemini model array requested
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
                return text, category, live_headline
            except Exception as e:
                print(f"Gemini API ({model_name}) Attempt {attempt+1} Failed: {e}")
                time.sleep(2)
                
    return None, category, live_headline

def get_dynamic_unique_image_url(news_text, category):
    """Fetches Dynamic HD Base Background Image"""
    words = [w.strip("!?:;,'\"") for w in news_text.split() if len(w) > 3 and not w.startswith("#")]
    search_keyword = words[0] if words else category

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

    category_pools = {
        "india": ["https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=1080&h=1080&fit=crop&q=80"],
        "geopolitics": ["https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1080&h=1080&fit=crop&q=80"],
        "technology": ["https://images.unsplash.com/photo-1518770660439-4636190af475?w=1080&h=1080&fit=crop&q=80"],
        "space": ["https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&h=1080&fit=crop&q=80"],
        "finance": ["https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1080&h=1080&fit=crop&q=80"]
    }
    
    pool = category_pools.get(category, category_pools["india"])
    return random.choice(pool)

def create_news_card_overlay(base_img_url, headline_text, category_badge):
    """Generates Professional News Graphic Overlay (Jagran/Times Now Style)"""
    try:
        res = requests.get(base_img_url, timeout=10)
        img = Image.open(BytesIO(res.content)).convert("RGBA").resize((1080, 1080))

        # Bottom dark gradient card for headline readability
        overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)
        draw_ov.rectangle([(0, 580), (1080, 1080)], fill=(12, 18, 28, 235))
        draw_ov.rectangle([(0, 572), (1080, 580)], fill=(225, 29, 72, 255))
        
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # Top Right Category Badge
        badge_font = get_font(26, bold=True)
        draw.rounded_rectangle([(780, 40), (1040, 95)], radius=10, fill=(225, 29, 72, 255))
        draw.text((800, 52), category_badge.upper(), fill="white", font=badge_font)

        # Top Left Brand Logo Overlay
        try:
            logo_res = requests.get(GITHUB_LOGO_URL, timeout=5)
            if logo_res.status_code == 200:
                logo = Image.open(BytesIO(logo_res.content)).convert("RGBA").resize((180, 65))
                img.paste(logo, (40, 40), logo)
        except Exception as e:
            print(f"Logo Overlay Error: {e}")

        # Big Bold Headline Overlay
        clean_headline = headline_text.split(" - ")[0]
        title_font = get_font(42, bold=True)
        wrapped_lines = textwrap.wrap(clean_headline, width=32)[:3]
        
        y_text = 620
        for line in wrapped_lines:
            draw.text((45, y_text), line, fill="#FACC15" if y_text == 620 else "#FFFFFF", font=title_font)
            y_text += 60

        output_path = "final_card.png"
        img.convert("RGB").save(output_path)
        return output_path
    except Exception as e:
        print(f"News Card Overlay Creation Error: {e}")
        return None

def upload_to_imgur(image_path):
    """Uploads locally generated image card to public URL for Buffer"""
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
    text, category, headline = generate_news_with_gemini()
    if text and headline:
        base_img = get_dynamic_unique_image_url(text, category)
        card_file = create_news_card_overlay(base_img, headline, category)
        
        final_image_url = None
        if card_file:
            final_image_url = upload_to_imgur(card_file)
            
        if not final_image_url:
            final_image_url = base_img

        print(f"Final Matching Card Image URL: {final_image_url}")
        print(f"Post Text:\n{text}")
        send_direct_to_buffer(text, final_image_url)
    else:
        print("Skipping execution: Live RSS news fetch or Gemini failed.")
