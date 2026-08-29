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

def send_to_buffer_rest(post_text):
    if not BUFFER_ACCESS_TOKEN:
        print("Error: BUFFER_ACCESS_TOKEN Missing!")
        return

    # 1. Fetch connected profiles via REST
    profiles_url = f"https://api.bufferapp.com/1/profiles.json?access_token={BUFFER_ACCESS_TOKEN}"
    p_res = requests.get(profiles_url)
    profiles = p_res.json()

    if not isinstance(profiles, list):
        print("Error fetching profiles:", profiles)
        return

    profile_ids = [p["id"] for p in profiles]
    print(f"Found {len(profile_ids)} profiles: {profile_ids}")

    # 2. Post updates via REST
    update_url = "https://api.bufferapp.com/1/updates/create.json"
    
    payload = {
        "access_token": BUFFER_ACCESS_TOKEN,
        "text": post_text,
        "now": "true"
    }
    
    # Add profile IDs array
    for i, pid in enumerate(profile_ids):
        payload[f"profile_ids[{i}]"] = pid

    res = requests.post(update_url, data=payload)
    print("Buffer Post Result:", res.text)

if __name__ == "__main__":
    text = generate_news_with_gemini()
    if text:
        print("News generated via Gemini AI! Sending to Buffer REST API...")
        send_to_buffer_rest(text)
    else:
        print("News generation failed!")
