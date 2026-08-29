import os
import requests
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

def generate_news_with_gemini():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing hai!")
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        # Indian English + strict character length
        prompt = (
            "Write a short, engaging tech news update in simple Indian English. "
            "Use 1 emoji headline, 1 concise detail bullet, and hashtags like #TechNews #IndiaTech. "
            "STRICT REQUIREMENT: Total output text MUST BE BETWEEN 200 AND 230 CHARACTERS."
        )
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        text = response.text.strip()
        
        # Twitter safety cap
        if len(text) > 240:
            text = text[:237] + "..."
        return text
    except Exception as e:
        print("Gemini API Error:", e)
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
    
    # 1. Fetch Account Organizations
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

    # Tech Image URL
    news_image_url = "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1080&q=80"

    # 3. Post to channels with Instagram Type
    for ch in channels:
        ch_id = ch.get("id")
        service = ch.get("service")
        
        # Instagram requires type parameter
        type_param = ', type: post' if service.lower() == 'instagram' else ''
        media_input = f', assets: {{ image: {{ url: "{news_image_url}" }} }}'

        mutation = f"""
        mutation {{
            createPost(input: {{
                channelId: "{ch_id}",
                text: {requests.compat.json.dumps(post_text)},
                schedulingType: automatic,
                mode: shareNow{type_param}{media_input}
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
        print("News generated via Gemini AI! Sending to Buffer...")
        send_to_buffer_graphql(text)
    else:
        print("News generation failed!")
