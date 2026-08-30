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

def send_to_buffer_rest_api(post_text):
    if not BUFFER_ACCESS_TOKEN:
        print("Error: BUFFER_ACCESS_TOKEN Missing!")
        return

    # 1. Fetch Profiles/Channels
    profiles_url = f"https://api.bufferapp.com/1/profiles.json?access_token={BUFFER_ACCESS_TOKEN}"
    try:
        profiles_res = requests.get(profiles_url)
        profiles = profiles_res.json()
    except Exception as e:
        print(f"Profiles fetch error: {e}")
        return

    if not isinstance(profiles, list) or len(profiles) == 0:
        print("Error: Channels/Profiles nahi mile!", profiles)
        return

    # Image setup
    timestamp_seed = int(time.time())
    news_image_url = f"https://picsum.photos/seed/{timestamp_seed}/1200/675"

    # 2. Post Directly Using REST API v1
    create_url = "https://api.bufferapp.com/1/updates/create.json"

    for profile in profiles:
        profile_id = profile.get("id")
        service = profile.get("service")

        payload = {
            "access_token": BUFFER_ACCESS_TOKEN,
            "profile_ids[]": profile_id,
            "text": post_text,
            "now": "true",  # Direct Instant Share
            "media[photo]": news_image_url
        }

        try:
            res = requests.post(create_url, data=payload)
            print(f"Result for {service} ({profile_id}):", res.text)
        except Exception as e:
            print(f"Failed posting to {service}: {e}")

if __name__ == "__main__":
    text = generate_news_with_gemini()
    if text:
        print(f"Generated News Text for WorldScopeX:\n{text}\n\nSending via Buffer REST API...")
        send_to_buffer_rest_api(text)
    else:
        print("News generation failed!")
