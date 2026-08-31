import os
import time
import requests
import random
import io
import base64
import feedparser
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

def fetch_live_google_news(topic_query):
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
        print("Error: GEMINI_API_KEY Missing!")
        return None

    topics = [
        "technology artificial intelligence hardware",
        "stock market finance global business",
        "geopolitics international relations diplomacy",
        "space exploration defense technology science",
        "India infrastructure highways mega projects"
    ]
    
    selected_query = random.choice(topics)
    print(f"Fetching Live Google News for query: '{selected_query}'...")
    
    live_headline = fetch_live_google_news(selected_query)
    
    if live_headline:
        print(f"Live News Found: {live_headline}")
        prompt_content = f"LIVE REAL BREAKING NEWS HEADLINE: '{live_headline}'"
    else:
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
            return text
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(3)

    return None

def upload_to_imgbb(image_bytes):
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

def get_guaranteed_public_image_url():
    # High-resolution stable stock images stream
    stock_urls = [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200",
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1200",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1200"
    ]
    selected_url = random.choice(stock_urls)
    
    try:
        print("Fetching background image stream...")
        res = requests.get(selected_url, timeout=15)
        if res.status_code == 200:
            print("Uploading image to ImgBB for permanent public URL...")
            hosted_url = upload_to_imgbb(res.content)
            if hosted_url:
                print(f"Public Hosted Image URL: {hosted_url}")
                return hosted_url
    except Exception as e:
        print(f"Image download/upload error: {e}")

    # Solid Fallback direct CDN image URL
    return "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200"

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
    text = generate_news_with_gemini()
    if text:
        image_url = get_guaranteed_public_image_url()
        print(f"Generated News Text for WorldScopeX:\n{text}\n\nSending to Buffer...")
        send_to_buffer_graphql(text, image_url)
