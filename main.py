import os
import feedparser
import google.generativeai as genai

# 1. Google News se Real-Time News Ingestion
def get_latest_news():
    url = "https://news.google.com/rss/search?q=India+geopolitics+technology&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    if feed.entries:
        return feed.entries[0].title
    return None

# 2. Gemini AI Summarizer
def generate_ai_post(news_title):
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"Write a short engaging tweet with 2 hashtags for this news: {news_title}"
    
    response = model.generate_content(prompt)
    return response.text

if __name__ == "__main__":
    news = get_latest_news()
    if news:
        print("News Found:", news)
        post_text = generate_ai_post(news)
        print("\n--- AI Generated Tweet ---\n", post_text)
    else:
        print("No news found.")
