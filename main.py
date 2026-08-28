import os
import random
import feedparser
import asyncio
from PIL import Image, ImageDraw
from google import genai
from twikit import Client
from instagrapi import Client as InstaClient

# 1. Multi-Topic Feeds (India, Global, Geopolitics, Economy, Tech)
NEWS_TOPICS = [
    "https://news.google.com/rss/search?q=India+news&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Global+Geopolitics&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Economy+Business+India&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Technology+AI+news&hl=en-IN&gl=IN&ceid=IN:en"
]

def get_latest_news():
    selected_url = random.choice(NEWS_TOPICS)
    feed = feedparser.parse(selected_url)
    if feed.entries:
        return feed.entries[0].title
    return "India advances global strategic and technology initiatives"

# 2. Gemini AI Content Generator
def generate_ai_post(news_title):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY missing!")
        return None

    client = genai.Client(api_key=api_key)
    prompt = f"Write a short engaging update with 2 hashtags for this news: {news_title}. Keep it strictly under 220 characters."

    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt
    )
    return response.text

# 3. Dynamic News Image Banner Generator
def create_news_image(text):
    img = Image.new('RGB', (1080, 1080), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Top Header
    draw.rectangle([0, 0, 1080, 140], fill=(30, 41, 59))
    draw.text((50, 45), "GLOBAL & INDIA NEWS UPDATE", fill=(56, 189, 248))

    # Text Wrapper
    words = text.split()
    lines = []
    curr_line = ""
    for w in words:
        if len(curr_line + " " + w) < 28:
            curr_line += " " + w
        else:
            lines.append(curr_line)
            curr_line = w
    lines.append(curr_line)

    y = 300
    for line in lines:
        draw.text((50, y), line.strip(), fill=(255, 255, 255))
        y += 70

    img_path = "news_post.jpg"
    img.save(img_path)
    return img_path

# 4. Twitter Auto Post (Twikit - Free Browser Automation)
async def post_to_twitter(text, img_path):
    username = os.getenv("TWITTER_USERNAME")
    password = os.getenv("TWITTER_PASSWORD")
    email = os.getenv("TWITTER_EMAIL")

    if not username or not password:
        print("Skipping Twitter: Credentials missing.")
        return

    client = Client('en-US')
    await client.login(auth_info_1=username, auth_info_2=email, password=password)

    media_id = await client.upload_media(img_path)
    await client.create_tweet(text=text, media_ids=[media_id])
    print("Successfully posted to Twitter (X)!")

# 5. Instagram Auto Post
def post_to_instagram(text, img_path):
    insta_user = os.getenv("INSTA_USERNAME")
    insta_pass = os.getenv("INSTA_PASSWORD")

    if not insta_user or not insta_pass:
        print("Skipping Instagram: Credentials missing.")
        return

    cl = InstaClient()
    cl.login(insta_user, insta_pass)
    cl.photo_upload(img_path, caption=text)
    print("Successfully posted to Instagram!")

if __name__ == "__main__":
    print("Fetching News...")
    news = get_latest_news()
    print(f"News Selected: {news}\n")

    post_text = generate_ai_post(news)
    if post_text:
        print(f"Generated AI Text:\n{post_text}\n")
        banner_img = create_news_image(news)

        # Twitter Run
        try:
            asyncio.run(post_to_twitter(post_text, banner_img))
        except Exception as e:
            print(f"Twitter Error: {e}")

        # Instagram Run
        try:
            post_to_instagram(post_text, banner_img)
        except Exception as e:
            print(f"Instagram Error: {e}")
