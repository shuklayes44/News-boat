import os
import time
import requests
import random
import io
from google import genai

# Try loading PIL safely for watermark overlay
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: Pillow missing in environment. Using direct image.")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

def generate_news_with_gemini():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing hai!")
        return None, "news"

    topics = [
        ("Major Global Tech Breakthroughs & AI Hardware Innovations", "technology,artificial intelligence,robotics"),
        ("World Economy, Stock Markets & Global Trade Developments", "stock market,finance,business"),
        ("Geopolitics, International Relations & Diplomacy Updates", "geopolitics,war,diplomacy"),
        ("Space Exploration, Defense Tech & Science Discoveries", "space,rocket,galaxy"),
        ("India Governance, Infrastructure & Mega Projects News", "infrastructure,highway,bridge,city")
    ]
    
    selected_topic, image_keywords = random.choice(topics)
    print(f"Generating post for WorldScopeX Topic: {selected_topic}")

    prompt = (
        f"You are the senior journalist for 'WorldScopeX'. Write a real-time viral news summary on: {selected_topic}.\n"
        "STRICT RULES:\n"
        "1. Language: Professional Indian English.\n"
        "2. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with relevant Emoji\n"
        "   - Line 2-3: Core factual news update with key figures or numbers\n"
        "   - Line 4: Short engagement question\n"
        "   - Line 5: #WorldScopeX #NewsUpdate #Global #Tech\n"
        "3. Length: Strictly between 200 and 230 characters TOTAL."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Official standard model for google-genai SDK
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
            )
            text = response.text.strip()
            if len(text) > 240:
                text = text[:237] + "..."
            return text, image_keywords
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(3)

    print("All Gemini API attempts failed.")
    return None, "news"

def get_topic_matched_image_url(image_keywords):
    keyword = random.choice(image_keywords.split(','))
    unique_seed = f"{keyword}_{int(time.time())}_{random.randint(100, 999)}"
    base_image_url = f"https://picsum.photos/seed/{unique_seed}/1200/675.jpg"
    
    logo_path = "logo.png"
    if HAS_PIL and os.path.exists(logo_path):
        try:
            print("Logo found in repo! Applying WorldScopeX Watermark...")
            res = requests.get(base_image_url, timeout=15)
            if res.status_code == 200:
                bg = Image.open(io.BytesIO(res.content)).convert("RGBA")
                logo = Image.open(logo_path).convert("RGBA")

                logo_w = 200
                w_percent = logo_w / float(logo.size[0])
                logo_h = int(float(logo.size[1]) * float(w_percent))
                logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

                pos_x = bg.width - logo_w - 30
                pos_y = 30
                bg.paste(logo, (pos_x, pos_y), logo)

                final_img = bg.convert("RGB")
                final_img.save("branded_post.jpg", quality=95)
                print("Branded image created successfully.")
        except Exception as e:
            print(f"Watermark overlay error: {e}. Using direct image URL.")
    else:
        print("Using direct image URL.")

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
    
    account_query = {
        "query": """
        query GetAccount {
            account {
                organizations {
                    id
                }
            }
        }
        """
    }
    
    acc_res = requests.post(url, json=account_query, headers=headers)
    acc_data = acc_res.json()
    orgs = acc_data.get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        print("Error: Organization nahi mili!", acc_data)
        return

    org_id = orgs[0].get("id")

    channels_query = {
        "query": """
        query GetChannels($input: ChannelsInput!) {
            channels(input: $input) {
                id
                service
            }
        }
        """,
        "variables": {
            "input": {
                "organizationId": org_id
            }
        }
    }
    
    ch_res = requests.post(url, json=channels_query, headers=headers)
    ch_data = ch_res.json()
    channels = ch_data.get("data", {}).get("channels", [])

    if not channels:
        print("Error: Channels nahi mile!", ch_data)
        return

    for ch in channels:
        ch_id = ch.get("id")
        service = ch.get("service")
        
        if service.lower() == 'instagram':
            metadata_param = ', metadata: { instagram: { type: post, shouldShareToFeed: true } }'
        else:
            metadata_param = ''

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
                    post {{
                        id
                        status
                    }}
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
    else:
        print("News generation failed!")
