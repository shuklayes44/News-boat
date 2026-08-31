import os
import time
import requests
import random
import io
import base64
import feedparser
from datetime import datetime
from google import genai
from PIL import Image, ImageDraw

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def get_repo_logo_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_names = ["logo.png", "Logo.png", "LOGO.PNG", "logo.jpg", "logo.jpeg", "LOGO.JPG"]
    
    for name in possible_names:
        full_path = os.path.join(base_dir, name)
        if os.path.exists(full_path):
            return full_path
        if os.path.exists(name):
            return name
    return None

def fetch_live_google_news(topic_query):
    formatted_query = topic_query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            selected = random.choice(feed.entries[:5])
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
    prompt_content = f"LIVE BREAKING NEWS: '{live_headline}'" if live_headline else f"TOPIC: '{selected_query}'"

    prompt = (
        f"You are the senior journalist for 'WorldScopeX'. Create a high-impact viral post:\n"
        f"{prompt_content}\n\n"
        "STRICT RULES:\n"
        "1. Language: Professional Indian English.\n"
        "2. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with Emoji\n"
        "   - Line 2-3: Core factual news summary\n"
        "   - Line 4: Short engagement question\n"
        "   - Line 5: #WorldScopeX #NewsUpdate #Global\n"
        "3. Total Length: Strictly between 170 and 200 characters."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            text = response.text.strip()
            time_code = datetime.utcnow().strftime("%M%S")
            unique_tag = f" #WSX_{time_code}"
            
            if len(text) + len(unique_tag) <= 240:
                text += unique_tag
            
            return text, image_keyword
        except Exception as e:
            print(f"Gemini API Attempt {attempt+1} Failed: {e}")
            time.sleep(2)
            
    return None, "space"

def create_solid_branded_canvas():
    colors = [(15, 23, 42), (24, 24, 27), (15, 30, 45)]
    bg_color = random.choice(colors)
    img = Image.new('RGB', (1080, 1080), color=bg_color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 1050, 1050], outline=(59, 130, 246), width=6)
    
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=90)
    return output.getvalue()

def apply_watermark_logo(bg_bytes):
    try:
        bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    except Exception:
        bg = Image.open(io.BytesIO(create_solid_branded_canvas())).convert("RGBA")

    try:
        logo_path = get_repo_logo_path()
        if logo_path:
            print(f"LOGO EMBED SUCCESS: Found logo file at '{logo_path}'")
            logo = Image.open(logo_path).convert("RGBA")
            
            logo_w = 220
            w_percent = logo_w / float(logo.size[0])
            logo_h = int(float(logo.size[1]) * float(w_percent))
            logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
            
            pos_x = bg.width - logo_w - 30
            pos_y = 30
            bg.paste(logo, (pos_x, pos_y), logo)
        else:
            print("LOGO WARNING: logo.png not uploaded in repo root. Using fallback text overlay...")
            draw = ImageDraw.Draw(bg)
            draw.rectangle([bg.width - 270, 30, bg.width - 30, 85], fill=(15, 23, 42, 235), outline=(255, 215, 0, 255), width=2)
            draw.text((bg.width - 240, 50), "WORLDSCOPEX", fill=(255, 255, 255, 255))

        output = io.BytesIO()
        bg.convert("RGB").save(output, format="JPEG", quality=90)
        return output.getvalue()
    except Exception as e:
        print(f"Watermark rendering error: {e}")
        return bg_bytes

def upload_image_fail_safe(image_bytes):
    encoded_string = base64.b64encode(image_bytes).decode('utf-8')
    
    # Primary Uploader: ImgBB
    try:
        res = requests.post(
            'https://api.imgbb.com/1/upload',
            data={'key': '3b0ad8ee6d8606aa1dce444bf19b45bb', 'image': encoded_string},
            timeout=25
        )
        data = res.json()
        if data.get('success'):
            url = data['data']['url']
            print(f"ImgBB Upload Success: {url}")
            return url
    except Exception as e:
        print(f"ImgBB Upload Failed: {e}")

    # Backup Direct URL Guarantee (Never return None)
    backup_urls = [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1080&q=80",
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1080&q=80",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&q=80"
    ]
    selected_backup = random.choice(backup_urls)
    print(f"Using Guarantee Direct Stock URL Fallback: {selected_backup}")
    return selected_backup

def get_branded_image_url(keyword):
    images_pool = [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1080&q=80",
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1080&q=80",
        "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1080&q=80",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&q=80",
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1080&q=80"
    ]
    
    selected_url = random.choice(images_pool)
    try:
        print(f"Fetching stock background image for '{keyword}'...")
        res = requests.get(selected_url, headers=HEADERS, timeout=15)
        if res.status_code == 200 and len(res.content) > 3000:
            watermarked_bytes = apply_watermark_logo(res.content)
            uploaded_url = upload_image_fail_safe(watermarked_bytes)
            if uploaded_url:
                return uploaded_url
    except Exception as e:
        print(f"Stock image fetch error: {e}")

    fallback_bytes = apply_watermark_logo(create_solid_branded_canvas())
    return upload_image_fail_safe(fallback_bytes)

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
        image_url = get_branded_image_url(image_keyword)
        print(f"Final Image URL: {image_url}")
        print(f"Post Text:\n{text}")
        send_to_buffer_graphql(text, image_url)
