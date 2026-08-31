import os
import time
import requests
import random
import io
import base64
import feedparser
from google import genai
from PIL import Image, ImageDraw, ImageFont

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

# Headers to prevent Pexels / ImgBB request blocking in GitHub Runners
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

def fetch_live_google_news(topic_query):
    formatted_query = topic_query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            return random.choice(feed.entries[:5]).title
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
        "2. Do NOT invent fake facts.\n"
        "3. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with Emoji\n"
        "   - Line 2-3: Factual news summary\n"
        "   - Line 4: Short engagement question\n"
        "   - Line 5: #WorldScopeX #NewsUpdate #Global #Tech\n"
        "4. Total Length: 200 to 230 characters."
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

def apply_watermark_logo(bg_bytes):
    """Guaranteed Watermark Layer - Merges logo or draws dynamic watermark text"""
    try:
        bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
        
        # Check if logo.png exists in local repo
        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            logo_w = 220
            w_percent = logo_w / float(logo.size[0])
            logo_h = int(float(logo.size[1]) * float(w_percent))
            logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
            
            pos_x = bg.width - logo_w - 30
            pos_y = 30
            bg.paste(logo, (pos_x, pos_y), logo)
            print("LOGO OVERLAY: logo.png applied successfully!")
        else:
            print("LOGO WARNING: logo.png missing in repo root. Fallback text badge drawn!")
            draw = ImageDraw.Draw(bg)
            draw.rectangle([bg.width - 250, 30, bg.width - 30, 80], fill=(10, 15, 30, 230), outline=(255, 215, 0, 255), width=2)
            draw.text((bg.width - 230, 48), "WORLDSCOPEX", fill=(255, 255, 255, 255))

        output = io.BytesIO()
        bg.convert("RGB").save(output, format="JPEG", quality=95)
        return output.getvalue()
    except Exception as e:
        print(f"Watermark Failed: {e}")
        return bg_bytes

def upload_to_imgbb(image_bytes):
    api_key = "3b0ad8ee6d8606aa1dce444bf19b45bb"
    encoded_string = base64.b64encode(image_bytes).decode('utf-8')
    payload = {'key': api_key, 'image': encoded_string}
    try:
        res = requests.post('https://api.imgbb.com/1/upload', data=payload, timeout=25)
        data = res.json()
        if data.get('success'):
            print(f"ImgBB Upload Success: {data['data']['url']}")
            return data['data']['url']
    except Exception as e:
        print(f"ImgBB Upload Error: {e}")
    return None

def get_branded_image_url(keyword):
    # Topic specific diverse images
    images_map = {
        "technology": "https://images.pexels.com/photos/8386440/pexels-photo-8386440.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "business": "https://images.pexels.com/photos/6801874/pexels-photo-6801874.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "politics": "https://images.pexels.com/photos/1550337/pexels-photo-1550337.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "space": "https://images.pexels.com/photos/2156/sky-space-shuttle-start.jpg?auto=compress&cs=tinysrgb&w=1200",
        "infrastructure": "https://images.pexels.com/photos/169647/pexels-photo-169647.jpeg?auto=compress&cs=tinysrgb&w=1200"
    }
    
    selected_img_url = images_map.get(keyword, "https://images.pexels.com/photos/2156/sky-space-shuttle-start.jpg?auto=compress&cs=tinysrgb&w=1200")
    
    try:
        print(f"Fetching base stock image for '{keyword}'...")
        res = requests.get(selected_img_url, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            watermarked_bytes = apply_watermark_logo(res.content)
            hosted_url = upload_to_imgbb(watermarked_bytes)
            if hosted_url:
                return hosted_url
    except Exception as e:
        print(f"Base image fetch error: {e}")

    # FORCE WATERMARK EVEN ON FALLBACK IMAGE
    print("Executing watermark logic on fallback image...")
    fallback_res = requests.get("https://images.pexels.com/photos/2156/sky-space-shuttle-start.jpg?auto=compress&cs=tinysrgb&w=1200", headers=HEADERS, timeout=15)
    watermarked_fallback = apply_watermark_logo(fallback_res.content)
    return upload_to_imgbb(watermarked_fallback)

def send_to_buffer_graphql(post_text, image_url):
    if not BUFFER_ACCESS_TOKEN:
        print("Error: BUFFER_ACCESS_TOKEN Missing!")
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
        print(f"Sending Post to Buffer (Instagram & X)...\nText:\n{text}\nImage: {image_url}")
        send_to_buffer_graphql(text, image_url)
