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
        "India National News & Major Governance/Infrastructure Update",
        "Global Geopolitics & High-Impact World News",
        "Indian & Global Economy, Stock Market, Business or Startups",
        "Latest Breakthrough Tech, AI Innovation or Frontier Gadgets",
        "Indian Politics & Major Policy Updates"
    ]
    
    selected_topic = random.choice(topics)
    print(f"Generating post for WorldScopeX Category: {selected_topic}")

    prompt = (
        f"You are the head content strategist for 'WorldScopeX'. Write a high-engagement viral news post about: {selected_topic}.\n"
        "STRICT RULES:\n"
        "1. Language: Crisp Indian English.\n"
        "2. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with Emoji\n"
        "   - Line 2-3: Core facts / Key numbers & metrics\n"
        "   - Line 4: Engagement Question (e.g., 'What is your take on this?')\n"
        "   - Line 5: #WorldScopeX #India #WorldNews #Economy\n"
        "3. Character Limit: MUST BE STRICTLY BETWEEN 200 AND 230 CHARACTERS TOTAL."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Exact model that worked in Run #49
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

    random_id = random.randint(100, 9999)
    news_image_url = f"https://picsum.photos/seed/{random_id}/1080/1080"

    # 3. Execution Loop across connected accounts
    for ch in channels:
        ch_id = ch.get("id")
        service = ch.get("service")
        
        # Buffer Instagram Meta Payload Fix
        if service.lower() == 'instagram':
            metadata_param = ', metadata: { instagram: { type: post } }'
        else:
            metadata_param = ''

        media_input = f', assets: {{ image: {{ url: "{news_image_url}" }} }}'

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
        print(f"Generated News Text for WorldScopeX:\n{text}\n\nSending to Buffer...")
        send_to_buffer_graphql(text)
    else:
        print("News generation failed!")
