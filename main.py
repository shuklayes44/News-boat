import os
import feedparser
from google import genai

# 1. Google News se Real-Time News Fetch karna
def get_latest_news():
    url = "https://news.google.com/rss/search?q=India+geopolitics+technology&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    if feed.entries:
        return feed.entries[0].title
    return None

# 2. Latest Google GenAI SDK Summarizer
def generate_ai_post(news_title):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY secret not found in environment!")
        return None

    # New SDK Client Setup
    client = genai.Client(api_key=api_key)
    prompt = f"Write a short engaging tweet with 2 hashtags for this news: {news_title}"

    # Stable Gemini Model
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return response.text

if __name__ == "__main__":
    print("Fetching news...")
    news = get_latest_news()
    if news:
        print(f"News Found: {news}\n")
        post_text = generate_ai_post(news)
        if post_text:
            print("--- AI Generated Tweet ---")
            print(post_text)
    else:
        print("No news found.")
