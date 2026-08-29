import os
import requests
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

def generate_news_with_gemini():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing hai Secrets me!")
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = (
            "Write a short, engaging viral social media post about a recent technology or AI update. "
            "Include an eye-catching headline with emojis, 2 core points, and trending hashtags like #TechNews #AI #Technology. "
            "Keep the output clean so it can be posted directly."
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print("Gemini API Error:", e)
        return None

def send_to_buffer_graphql(post_text):
    if not BUFFER_ACCESS_TOKEN:
        print("Error: BUFFER_ACCESS_TOKEN Missing hai Secrets me!")
        return

    url = "https://api.buffer.com/graphql"
    headers = {
        "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Fetch Connected Channels
    channels_query = {
        "query": """
        query GetChannels {
            account {
                organizations {
                    channels {
                        id
                        service
                    }
                }
            }
        }
        """
    }
    
    res = requests.post(url, json=channels_query, headers=headers)
    res_data = res.json()
    
    if "errors" in res_data:
        print("Buffer GraphQL Error:", res_data["errors"])
        return
        
    orgs = res_data.get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        print("Error: Buffer Organization nahi mili!")
        return

    channel_ids = [c["id"] for c in orgs[0].get("channels", [])]
    if not channel_ids:
        print("Error: Buffer Dashboard me connected channels nahi mile!")
        return

    # Post Publish Mutation
    mutation = """
    mutation CreatePost($channelId: String!, $text: String!) {
        createPost(channelId: $channelId, text: $text, mode: NOW) {
            post {
                id
            }
        }
    }
    """
    
    for ch_id in channel_ids:
        payload = {
            "query": mutation,
            "variables": {
                "channelId": ch_id,
                "text": post_text
            }
        }
        post_res = requests.post(url, json=payload, headers=headers)
        print(f"Post Sent Result for Channel {ch_id}:", post_res.text)

if __name__ == "__main__":
    text = generate_news_with_gemini()
    if text:
        print("News generated via Gemini AI! Sending to Buffer...")
        send_to_buffer_graphql(text)
    else:
        print("News generation failed!")
