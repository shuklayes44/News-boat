import os
import requests

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

def fetch_latest_news():
    url = f"https://newsapi.org/v2/top-headlines?category=technology&language=en&pageSize=5&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    data = response.json()
    
    if data.get("status") == "ok" and data.get("articles"):
        article = data["articles"][0]
        title = article.get("title", "")
        description = article.get("description", "")
        source_url = article.get("url", "")
        
        post_text = f"🚨 TECH NEWS UPDATE 🚨\n\n{title}\n\n📌 {description}\n\nRead full article: {source_url}\n\n#TechNews #AI #Technology #Updates"
        return post_text
    return None

def send_to_buffer_graphql(post_text):
    url = "https://api.buffer.com/graphql"
    headers = {
        "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 1. Fetch Channels
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
        print("Buffer API Auth Error:", res_data["errors"])
        return
        
    orgs = res_data.get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        print("No Organization found in Buffer!")
        return

    channel_ids = [c["id"] for c in orgs[0].get("channels", [])]
    if not channel_ids:
        print("No connected channels found! Check Buffer Dashboard.")
        return

    # 2. Create Post for each Channel
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
        print(f"Post Response for {ch_id}:", post_res.text)

if __name__ == "__main__":
    text = fetch_latest_news()
    if text:
        send_to_buffer_graphql(text)
    else:
        print("No news fetched!")
