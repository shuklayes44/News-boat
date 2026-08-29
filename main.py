import os
import requests
import xml.etree.ElementTree as ET

BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

def fetch_latest_news():
    url = "https://news.google.com/rss/search?q=technology&hl=en-IN&gl=IN&ceid=IN:en"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        item = root.find('.//item')
        if item is not None:
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            
            post_text = f"🚨 TECH NEWS UPDATE 🚨\n\n{title}\n\nRead full article: {link}\n\n#TechNews #AI #Technology #Updates"
            return post_text
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
    
    # 1. Connected Channels (Instagram/X) Fetch Karna
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
        print("Error: Buffer account me Organization nahi mili!")
        return

    channel_ids = [c["id"] for c in orgs[0].get("channels", [])]
    if not channel_ids:
        print("Error: Buffer me koi Instagram/Twitter Channel connected nahi mila!")
        return

    # 2. GraphQL se Channels par Post Bhejna
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
        print(f"Post Sent Result for {ch_id}:", post_res.text)

if __name__ == "__main__":
    text = fetch_latest_news()
    if text:
        print("Fetched News! Sending via Buffer GraphQL...")
        send_to_buffer_graphql(text)
    else:
        print("News Fetch Nahi Ho Payi!")
