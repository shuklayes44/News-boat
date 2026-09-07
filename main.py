import os
import time
import requests
import random
import urllib.parse
import feedparser
import textwrap
import base64
from google import genai
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Local paths (repo is private, so we read committed files instead of
# downloading over HTTP from raw.githubusercontent.com).
LOGO_PATH = "logo.png"
FONT_BOLD_PATH = "fonts/Roboto-Bold.ttf"
FONT_REGULAR_PATH = "fonts/Roboto-Regular.ttf"

def get_font(font_size=42, bold=True):
    font_path = FONT_BOLD_PATH if bold else FONT_REGULAR_PATH
    if os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, font_size)
        except Exception as e:
            print(f"Font load error ({font_path}): {e}")
    else:
        print(f"WARNING: Font file not found at {font_path} — text will render tiny using default font. Add the .ttf file to your repo.")
    return ImageFont.load_default()

def fetch_live_google_news(topic_query):
    formatted_query = topic_query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries and len(feed.entries) > 0:
            selected = random.choice(feed.entries[:10])
            return selected.title
    except Exception as e:
        print(f"Google News RSS Error: {e}")
    return None

def generate_news_with_gemini():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing!")
        return None, "india", None

    # Topics aligned with: Global, India, Economic, Geopolitical, Tech, Stock Market
    topics = [
        ("India breaking news live updates", "india"),
        ("global world breaking news today", "global"),
        ("world geopolitics international relations breaking news", "geopolitics"),
        ("technology AI news breaking launch", "technology"),
        ("stock market Nifty Sensex breaking news", "stock market"),
        ("Indian economy business economic policy news", "economic"),
    ]

    selected_query, category = random.choice(topics)
    print(f"Fetching Live Breaking News for query: '{selected_query}'...")

    live_headline = fetch_live_google_news(selected_query)

    if not live_headline:
        print("Primary query skipped, checking fallback news topics...")
        for query, cat in topics:
            live_headline = fetch_live_google_news(query)
            if live_headline:
                category = cat
                break

    if not live_headline:
        print("Error: Could not fetch real live news RSS feed. Aborting execution.")
        return None, category, None

    print(f"SUCCESS: Fresh Live Headline Fetched -> {live_headline}")

    prompt = (
        f"STRICT INSTRUCTION: Write a high-impact, factual breaking news post based ONLY on this live headline:\n"
        f"HEADLINE: '{live_headline}'\n\n"
        "STRICT FORMATTING RULES:\n"
        "1. Language: Professional Indian English.\n"
        "2. Structure:\n"
        "   - Line 1: 🚨 [CAPS HOOK HEADLINE] with relevant Emoji\n"
        "   - Line 2-3: Core factual news summary\n"
        "   - Line 4: Short engagement question for audience\n"
        "   - Line 5: 4-5 dynamic trending hashtags matching THIS exact news\n"
        "3. ABSOLUTELY DO NOT ADD ANY SYSTEM CODE TAGS AT THE END.\n"
        "4. Total Length: Under 230 characters."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    models_to_try = ['gemini-3.6-flash', 'gemini-3.5-flash-lite', 'gemini-flash-latest']

    for model_name in models_to_try:
        print(f"Attempting content generation using model: {model_name}...")
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = response.text.strip()
                return text, category, live_headline
            except Exception as e:
                print(f"Gemini API ({model_name}) Attempt {attempt+1} Failed: {e}")
                time.sleep(5 * (attempt + 1))

    return None, category, live_headline

def get_dynamic_unique_image_url(news_text, category):
    words = [w.strip("!?:;,'\"") for w in news_text.split() if len(w) > 3 and not w.startswith("#")]
    search_keyword = words[0] if words else category

    if PEXELS_API_KEY:
        try:
            pex_url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(search_keyword)}&per_page=30"
            pex_headers = {"Authorization": PEXELS_API_KEY}
            res = requests.get(pex_url, headers=pex_headers, timeout=5)
            if res.status_code == 200:
                photos = res.json().get('photos', [])
                if photos:
                    selected = random.choice(photos)
                    return selected['src']['large2x']
        except Exception as e:
            print(f"Pexels API Fetch Error: {e}")

    sig_rand = random.randint(100, 99999)
    return f"https://picsum.photos/seed/{sig_rand}/1080/1080"

def create_news_card_overlay(base_img_url, headline_text, category_badge):
    try:
        res = requests.get(base_img_url, timeout=12)
        if res.status_code != 200:
            res = requests.get("https://picsum.photos/1080/1080", timeout=12)

        img = Image.open(BytesIO(res.content)).convert("RGBA").resize((1080, 1080))

        overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        # Top darken strip so logo/badge stay readable on any photo
        draw_ov.rectangle([(0, 0), (1080, 130)], fill=(0, 0, 0, 140))

        # Red Accent Bar
        draw_ov.rectangle([(0, 560), (1080, 570)], fill=(220, 38, 38, 255))
        # Solid dark backdrop for headline block
        draw_ov.rectangle([(0, 570), (1080, 1080)], fill=(15, 23, 42, 245))

        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # Top Category Tag (RED BADGE) - top right
        badge_font = get_font(28, bold=True)
        draw.rounded_rectangle([(740, 35), (1040, 95)], radius=8, fill=(220, 38, 38, 255))
        draw.text((760, 48), category_badge.upper(), fill="white", font=badge_font)

        # Brand Logo Top Left — pasted onto a solid white rounded backdrop
        # so it stays visible regardless of the logo's own colors or the
        # photo behind it (fixes the "logo not visible" issue).
        try:
            if os.path.exists(LOGO_PATH):
                logo = Image.open(LOGO_PATH).convert("RGBA")
                max_w, max_h = 200, 70
                logo_ratio = min(max_w / logo.width, max_h / logo.height)
                new_size = (int(logo.width * logo_ratio), int(logo.height * logo_ratio))
                logo = logo.resize(new_size)

                pad = 14
                box_w, box_h = new_size[0] + pad * 2, new_size[1] + pad * 2
                logo_bg = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
                bg_draw = ImageDraw.Draw(logo_bg)
                bg_draw.rounded_rectangle(
                    [(0, 0), (box_w, box_h)], radius=12, fill=(255, 255, 255, 235)
                )
                img.paste(logo_bg, (35, 30), logo_bg)
                img.paste(logo, (35 + pad, 30 + pad), logo)
            else:
                print(f"WARNING: Logo not found at {LOGO_PATH} — check the file is committed to the repo root.")
        except Exception as e:
            print(f"Logo Overlay Error: {e}")

        # BREAKING strip just above the accent bar
        breaking_font = get_font(26, bold=True)
        draw.rectangle([(0, 520), (260, 560)], fill=(220, 38, 38, 255))
        draw.text((15, 528), "🚨 BREAKING", fill="white", font=breaking_font)

        # Headline Layout
        clean_headline = headline_text.split(" - ")[0]
        title_font = get_font(44, bold=True)
        wrapped_lines = textwrap.wrap(clean_headline, width=30)[:3]

        y_text = 610
        for idx, line in enumerate(wrapped_lines):
            line_color = "#FACC15" if idx == 0 else "#FFFFFF"
            draw.text((40, y_text), line, fill=line_color, font=title_font)
            y_text += 65

        output_path = "final_card.png"
        img.convert("RGB").save(output_path)
        return output_path
    except Exception as e:
        print(f"News Card Overlay Creation Error: {e}")
        return None

def upload_image_to_freehost(image_path):
    try:
        url = "https://freeimage.host/api/1/upload"
        with open(image_path, "rb") as file:
            encoded_string = base64.b64encode(file.read()).decode('utf-8')

        payload = {
            "key": "6d207e02198a847aa98d0a2a901485a5",
            "action": "upload",
            "source": encoded_string,
            "format": "json"
        }
        res = requests.post(url, data=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            direct_url = data.get("image", {}).get("url")
            if direct_url:
                print(f"FreeImage Host Upload SUCCESS: {direct_url}")
                return direct_url
    except Exception as e:
        print(f"FreeImage Host Error: {e}")

    try:
        url = "https://tmpfiles.org/api/v1/upload"
        with open(image_path, "rb") as file:
            files = {"file": file}
            res = requests.post(url, files=files, timeout=20)
            if res.status_code == 200:
                file_url = res.json().get("data", {}).get("url")
                if file_url:
                    direct_url = file_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                    print(f"TmpFiles Upload SUCCESS: {direct_url}")
                    return direct_url
    except Exception as e:
        print(f"TmpFiles Upload Error: {e}")

    return None

def send_direct_to_buffer(post_text, image_url):
    if not BUFFER_ACCESS_TOKEN or not image_url:
        print("Error: BUFFER_ACCESS_TOKEN or Image URL Missing!")
        return

    url = "https://api.buffer.com/graphql"
    headers = {
        "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    acc_res = requests.post(url, json={"query": "query GetAccount { account { organizations { id } } }"}, headers=headers)
    orgs = acc_res.json().get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        print("Error: No Buffer Organization Found!")
        return
    org_id = orgs[0].get("id")

    ch_res = requests.post(
        url,
        json={"query": "query GetChannels($input: ChannelsInput!) { channels(input: $input) { id service } }", "variables": {"input": {"organizationId": org_id}}},
        headers=headers
    )
    channels = ch_res.json().get("data", {}).get("channels", [])

    for ch in channels:
        ch_id = ch.get("id")
        service = ch.get("service")

        extra_metadata = ', metadata: { instagram: { type: post, shouldShareToFeed: true } }' if service.lower() == 'instagram' else ''
        media_asset = f', assets: [{{ image: {{ url: "{image_url}" }} }}]'

        mutation = f"""
        mutation {{
            createPost(input: {{
                channelId: "{ch_id}",
                text: {requests.compat.json.dumps(post_text)},
                schedulingType: automatic,
                mode: shareNow{extra_metadata}{media_asset}
            }}) {{
                ... on PostActionSuccess {{
                    post {{ id status }}
                }}
                ... on MutationError {{
                    message
                }}
            }}
        }}
        """
        post_res = requests.post(url, json={"query": mutation}, headers=headers)
        print(f"Direct Post Result for {service} ({ch_id}): {post_res.text}")

if __name__ == "__main__":
    text, category, headline = generate_news_with_gemini()
    if text and headline:
        base_img = get_dynamic_unique_image_url(text, category)
        card_file = create_news_card_overlay(base_img, headline, category)

        final_image_url = None
        if card_file:
            final_image_url = upload_image_to_freehost(card_file)

        if not final_image_url:
            final_image_url = base_img

        print(f"Final Matching Card Image URL: {final_image_url}")
        print(f"Post Text:\n{text}")
        send_direct_to_buffer(text, final_image_url)
    else:
        print("Skipping execution: Live RSS news fetch or Gemini failed.")
