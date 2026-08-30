import os
import time
import requests
import random
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

def generate_news_with_gemini():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing hai!")
        return None

    topics = [
        "Major Global Tech Breakthroughs & AI Hardware Innovations",
        "World Economy, Stock Markets & Global Trade Developments",
        "Geopolitics, International Relations & Diplomacy Updates",
        "Space Exploration, Defense Tech & Science Discoveries",
        "India Governance, Infrastructure & Mega Projects News"
    ]
    
    selected_topic = random.choice(topics)
    print(f"Generating post for WorldScopeX Category: {selected_topic}")

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

    print("All Gemini API attempts failed.")
    return None

def send_to_buffer_graphql(post_text):
    if not BUFFER_ACCESS_TOKEN:
        print("Error: BUFFER_ACCESS_TOKEN Missing!")
        return

    url = "https://api.buffer.com/graphql"
    headers = {
        "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 1. Fetch Organization ID
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

    # 2. Fetch Connected Channels
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

    timestamp_seed = int(time.time())
    news_image_url = f"https://picsum.photos/seed/{timestamp_seed}/1200/675"

    # 3. Post to Channels (Direct Instant Mode)
    for ch in channels:
        ch_id = ch.get("id")
        service = ch.get("service")
        
        if service.lower() == 'instagram':
            metadata_param = ', metadata: { instagram: { type: post, shouldShareToFeed: true } }'
        else:
            metadata_param = ''

        media_input = f', assets: {{ image: {{ url: "{news_image_url}" }} }}'

        # Correct Enum Query String for Buffer GraphQL
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
    text = generate_news_with_gemini()
    if text:
        print(f"Generated News Text for WorldScopeX:\n{text}\n\nSending to Buffer via GraphQL...")
        send_to_buffer_graphql(text)
    else:
        print("News generation failed!")
