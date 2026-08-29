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
        
        prompt = (
            "Write a short, engaging social media post about recent tech news. "
            "Include an emoji headline, 2 key bullet points, and popular hashtags like #TechNews #AI. "
            "Keep it plain text."
        )

        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        return response.text
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
    
    # Step 1: Account info se Organization ID Fetch karna
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
    
    if "errors" in acc_data:
        print("Buffer Account Query Error:", acc_data["errors"])
        return
        
    orgs = acc_data.get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        print("Error: Buffer Organization nahi mili!")
        return

    org_id = orgs[0].get("id")

    # Step 2: Correct Organization ID ke sath Channels Fetch karna
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
    
    if "errors" in ch_data:
        print("Buffer Channels Query Error:", ch_data["errors"])
        return

    channels = ch_data.get("data", {}).get("channels", [])
    if not channels:
        print("Error: Connected Channels nahi melein!")
        return

    # Step 3: Post Publish Mutation
    mutation = """
    mutation CreatePost($channelId: String!, $text: String!) {
        createPost(channelId: $channelId, text: $text, mode: NOW) {
            post {
                id
            }
        }
    }
    """
    
    for ch in channels:
        ch_id = ch.get("id")
        payload = {
            "query": mutation,
            "variables": {
                "channelId": ch_id,
                "text": post_text
            }
        }
        post_res = requests.post(url, json=payload, headers=headers)
        print(f"Post Sent Result for Channel {ch.get('service')} ({ch_id}):", post_res.text)

if __name__ == "__main__":
    text = generate_news_with_gemini()
    if text:
        print("News generated via Gemini AI! Sending to Buffer...")
        send_to_buffer_graphql(text)
    else:
        print("News generation failed!")
