import os
import time
import requests
import random
import io
import base64
import feedparser
from google import genai
from PIL import Image

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

# Raw GitHub Public URL for your uploaded logo.png
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/shuklayes44/News-boat/main/logo.png"

def fetch_live_google_news(topic_query):
    """Google News RSS Feed se exact live trending headline fetch karta hai"""
    formatted_query = topic_query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            top_entries = feed.entries[:3]
            selected_entry = random.choice(top_entries)
            return selected_entry.title
    except Exception as e:
        print(f"Google News RSS error: {e}")
    
    return None

def generate_news_with_gemini():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing hai!")
        return None, "news"

    topics = [
        ("technology artificial intelligence hardware", "technology,artificial intelligence,robotics"),
        ("stock market finance global business", "stock market,finance,business"),
        ("geopolitics international relations diplomacy", "geopolitics,war,diplomacy"),
        ("space exploration defense technology science", "space,rocket,galaxy"),
        ("India infrastructure highways mega projects", "infrastructure,highway,bridge,city")
    ]
    
    selected_query, image_keywords = random.choice(topics)
    print(f"Fetching Live Google News for query: '{selected_query}'...")
    
    live_headline = fetch_live_google_news(selected_query)
    
    if live_headline:
        print(f"Live News Found: {live_headline}")
        prompt_content = f"LIVE REAL BREAKING NEWS HEADLINE: '{live_headline}'"
    else:
        print("Fallback: Direct topic prompt using Gemini knowledge base.")
        prompt_content = f"TOPIC: '{selected_query}'"

    prompt = (
        f"You are the senior journalist for 'WorldScopeX'. Transform the following input into a high-impact, factual viral post:\n"
        f"{prompt_content}\n\n"
        "STRICT RULES:\n"
        "1. Language: Professional Indian English.\n"
        "2. Do NOT invent fake facts. Use real info from the headline.\n"
        "3. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with relevant Emoji\n"
        "   - Line 2-3: Core factual news summary (numbers/figures if available)\n"
        "   - Line 4: Short engagement question\n"
        "   - Line 5: #WorldScopeX #NewsUpdate #Global #Tech\n"
        "4. Length: Strictly between 200 and 230 characters TOTAL."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            text = response.text.strip()
            if len(text) > 240:
                text = text[:237] + "..."
            return text, image_keywords
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(3)

    return None, "news"

def upload_to_imgbb(image_bytes):
    """ImgBB API se Image ko permanent public URL me convert karta hai (Buffer/Instagram Fix)"""
    api_key = "3b0ad8ee6d8606aa1dce444bf19b45bb" 
    encoded_string = base64.b64encode(image_bytes).decode('utf-8')
    payload = {
        'key': api_key,
        'image': encoded_string
    }
    try:
        res = requests.post('https://api.imgbb.com/1/upload', data=payload, timeout=20)
        data = res.json()
        if data.get('success'):
            return data['data']['url']
    except Exception as e:
        print(f"ImgBB upload error: {e}")
    return None

def get_topic_matched_image_url(image_keywords):
    keyword = random.choice(image_keywords.split(','))
    unique_seed = f"{keyword}_{int(time.time())}_{random.randint(100, 999)}"
    base_image_url = f"https://picsum.photos/seed/{unique_seed}/1200/675.jpg"
    
    try:
        print("Downloading background image...")
        bg_res = requests.get(base_image_url, timeout=15)
        bg = Image.open(io.BytesIO(bg_res.content)).convert("RGBA")
        
        print(f"Fetching Logo from GitHub Raw URL: {GITHUB_LOGO_URL} ...")
        logo_res = requests.get(GITHUB_LOGO_URL, timeout=15)
        
        if logo_res.status_code == 200:
            logo = Image.open(io.BytesIO(logo_res.content)).convert("RGBA")

            logo_w = 200
            w_percent = logo_w / float(logo.size[0])
            logo_h = int(float(logo.size[1]) * float(w_percent))
            logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

            pos_x = bg.width - logo_w - 30
            pos_y = 30
            bg.paste(logo, (pos_x, pos_y), logo)
            print("Watermark merged successfully!")
        else:
            print("Logo fetch failed from GitHub, continuing without logo overlay.")

        final_img = bg.convert("RGB")
        img_byte_arr = io.BytesIO()
        final_img.save(img_byte_arr, format='JPEG', quality=95)
        
        print("Uploading branded image to ImgBB for permanent public URL...")
        hosted_url = upload_to_imgbb(img_byte_arr.getvalue())
        if hosted_url:
            print(f"Public Branded Image URL: {hosted_url}")
            return hosted_url

    except Exception as e:
        print(f"Watermark or Image Processing Error: {e}")
            
    print("Fallback: Uploading base image to ImgBB...")
    try:
        res = requests.get(base_image_url, timeout=15)
        if res.status_code == 200:
            return upload_to_imgbb(res.content)
    except Exception as e:
        print(f"Direct base image upload error: {e}")

    return base_image_url

def send_to_buffer_graphql(post_text, image_url):
    if not BUFFER_ACCESS_TOKEN:
        print("Error: BUFFER_ACCESS_TOKEN Missing!")
        return

    url = "https://api.buffer.com/graphql"
    headers = {
        "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    account_query = {"query": "query GetAccount { account { organizations { id } } }"}
    acc_res = requests.post(url, json=account_query, headers=headers)
    orgs = acc_res.json().get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        return
    org_id = orgs[0].get("id")

    channels_query = {
        "query": "query GetChannels($input: ChannelsInput!) { channels(input: $input) { id service } }",
        "variables": {"input": {"organizationId": org_id}}
    }
    ch_res = requests.post(url, json=channels_query, headers=headers)
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
        print(f"Result for {service} ({ch_id}):", post_res.text)

if __name__ == "__main__":
    text, image_keywords = generate_news_with_gemini()
    if text:
        image_url = get_topic_matched_image_url(image_keywords)
        print(f"Generated News Text for WorldScopeX:\n{text}\n\nSending to Buffer...")
        send_to_buffer_graphql(text, image_url)
