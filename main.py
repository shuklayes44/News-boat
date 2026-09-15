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

LOGO_PATH = "logo.png"
FONT_BOLD_PATH = "fonts/Roboto-Bold.ttf"
FONT_REGULAR_PATH = "fonts/Roboto-Regular.ttf"

import json

HISTORY_FILE = "posted_history.json"
HISTORY_MAX = 40

def load_recent_headlines():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"History load error: {e}")
    return []

def save_recent_headline(headline):
    history = load_recent_headlines()
    history.append(headline)
    history = history[-HISTORY_MAX:]
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception as e:
        print(f"History save error: {e}")

def is_duplicate_headline(new_headline, history):
    new_words = set(w.lower() for w in new_headline.split() if len(w) > 3)
    if not new_words:
        return False
    for old_headline in history:
        if new_headline.strip().lower() == old_headline.strip().lower():
            return True
        old_words = set(w.lower() for w in old_headline.split() if len(w) > 3)
        if not old_words:
            continue
        overlap = len(new_words & old_words) / len(new_words | old_words)
        if overlap > 0.55:
            return True
    return False

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

def fetch_top_headlines(edition="india"):
    if edition == "world":
        rss_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    else:
        rss_url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries and len(feed.entries) > 0:
            selected = random.choice(feed.entries[:6])
            return selected.title
    except Exception as e:
        print(f"Google News Top Headlines RSS Error: {e}")
    return None

def generate_news_with_gemini(custom_headline=None, custom_category=None):
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing!")
        return None, "india", None, None

    topics = [
        ("India breaking news live updates", "india"),
        ("global world breaking news today", "global"),
        ("world geopolitics international relations breaking news", "geopolitics"),
        ("technology AI news breaking launch", "technology"),
        ("stock market Nifty Sensex breaking news", "stock market"),
        ("Indian economy business economic policy news", "economic"),
    ]

    def fetch_one_headline():
        use_top_headlines = random.random() < 0.7
        if use_top_headlines:
            edition = random.choice(["india", "world"])
            cat = "india" if edition == "india" else "global"
            print(f"Fetching Google News TOP HEADLINES ({edition} edition)...")
            headline = fetch_top_headlines(edition)
        else:
            selected_query, cat = random.choice(topics)
            print(f"Fetching Live Breaking News for query: '{selected_query}'...")
            headline = fetch_live_google_news(selected_query)

        if not headline:
            print("Primary query skipped, checking fallback news topics...")
            headline = fetch_top_headlines("india")
            cat = "india"
            if not headline:
                for query, c in topics:
                    headline = fetch_live_google_news(query)
                    if headline:
                        cat = c
                        break
        return headline, cat

    client = genai.Client(api_key=GEMINI_API_KEY)
    # gemini-3.6-flash's free tier has a very low daily cap (20/day), which
    # our posting frequency blows through fast — put the less-constrained
    # models first so most runs succeed without wasting time on 429 retries.
    models_to_try = ['gemini-3.5-flash-lite', 'gemini-flash-latest', 'gemini-3.6-flash']

    HEADLINE_ATTEMPTS = 1 if custom_headline else 3

    for headline_attempt in range(HEADLINE_ATTEMPTS):
        if custom_headline:
            live_headline = custom_headline
            category = custom_category if custom_category else "technology"
            print(f"Using CUSTOM headline (manual trigger): '{live_headline}' [category: {category}]")
            skip_allowed = False
        else:
            live_headline, category = fetch_one_headline()
            if not live_headline:
                print("Error: Could not fetch real live news RSS feed. Aborting execution.")
                return None, category, None, None
            print(f"SUCCESS: Fresh Live Headline Fetched -> {live_headline}")

            recent_history = load_recent_headlines()
            is_last_attempt = headline_attempt >= HEADLINE_ATTEMPTS - 1
            if is_duplicate_headline(live_headline, recent_history) and not is_last_attempt:
                print(f"DUPLICATE: '{live_headline}' looks like something posted recently — trying a different headline.")
                continue

            skip_allowed = headline_attempt < HEADLINE_ATTEMPTS - 1

        skip_instruction = (
            "\n0. IMPORTANCE FILTER: This bot only posts genuinely significant, "
            "high-quality news for a serious global/India news brand — major "
            "politics, economy, markets, geopolitics, technology, or business "
            "stories. If this headline is trivial, low-quality, celebrity "
            "gossip, clickbait, a listicle, an ad/PR piece, or too minor/local "
            "to matter to a broad audience, respond with EXACTLY the single "
            "word SKIP and nothing else — no explanation.\n"
            if skip_allowed else ""
        )

        prompt = (
            f"STRICT INSTRUCTION: Write a high-impact, factual breaking news post based ONLY on this live headline:\n"
            f"HEADLINE: '{live_headline}'\n"
            f"{skip_instruction}\n"
            "STRICT FORMATTING RULES:\n"
            "1. Language: Professional English for a global audience, with special emphasis "
            "on relevance to Indian readers — where the headline supports it, note the "
            "impact on India (markets, policy, jobs, prices) without inventing anything not "
            "in the headline.\n"
            "2. Structure:\n"
            "   - Line 1: An attention-grabbing opener with an emoji. Vary the style each "
            "time — sometimes a bold CAPS hook ('🚨 MARKETS CRASH!'), sometimes a short "
            "question ('🤔 Is this the end of...?'), sometimes a striking stat "
            "('📉 ₹8 lakh crore wiped out in a day'). Do not use the exact same opening "
            "phrase every time.\n"
            "   - Line 2-3: Core factual summary. Where the headline supports it, include "
            "ONE specific, concrete number or statistic (e.g. exact figures, percentages, "
            "amounts) rather than vague words like 'a lot' or 'significant'.\n"
            "   - Line 4: One short sentence of 'why this matters' — connect the news to a "
            "real, tangible impact on an ordinary reader's life (money, jobs, prices, "
            "safety, daily routine) wherever the headline reasonably supports it. If it "
            "genuinely doesn't apply, give one line of background context instead so a "
            "reader unfamiliar with the story understands its significance.\n"
            "   - Line 5: Short engagement question for the audience.\n"
            "   - Line 6: 4-5 dynamic trending hashtags matching THIS exact news.\n"
            "   - Line 7: A line starting exactly with 'IMG_QUERY:' followed by a short "
            "1-4 word English stock-photo search phrase describing the single most "
            "visually common, easy-to-find subject of this news (e.g. 'stock market', "
            "'smartphone', 'parliament building', 'cricket stadium', 'world map'). "
            "Keep it SIMPLE and generic — prefer a widely-photographed everyday subject "
            "over a specific/unusual combination of ideas, since it must match a stock "
            "photo library search. CRITICAL: if this news is specifically about India "
            "(an Indian state, city, election, institution, or company), you MUST include "
            "the word 'Indian' or 'India' in the phrase (e.g. 'Indian election voting', "
            "'Indian parliament', 'Indian stock market') — otherwise a generic word like "
            "'vote' or 'flag' can pull an unrelated country's imagery (e.g. a US flag on "
            "an Indian state election story), which looks like a factual error. Never "
            "name a country in the query that isn't the one this story is actually "
            "about.\n"
            "3. ACCURACY IS CRITICAL: only use facts present in the headline itself. Never "
            "invent, guess, or embellish numbers, causes, or details not given.\n"
            "4. ABSOLUTELY DO NOT ADD ANY SYSTEM CODE TAGS AT THE END.\n"
            "5. Total Length of the post itself, INCLUDING the hashtags line (excluding "
            "only the IMG_QUERY line): aim for around 265 characters, and never exceed "
            "270. This is close to a hard platform limit of 280 — count carefully."
        )

        skipped_this_headline = False

        for model_name in models_to_try:
            print(f"Attempting content generation using model: {model_name}...")
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    raw_text = response.text.strip()

                    if skip_allowed and raw_text.strip().upper() == "SKIP":
                        print(f"Gemini judged headline too low-quality/trivial, skipping: '{live_headline}'")
                        skipped_this_headline = True
                        break

                    image_query = None
                    post_lines = []
                    for line in raw_text.splitlines():
                        if line.strip().upper().startswith("IMG_QUERY:"):
                            image_query = line.split(":", 1)[1].strip()
                        else:
                            post_lines.append(line)

                    text = "\n".join(post_lines).strip()

                    MAX_LEN = 280
                    if len(text) > MAX_LEN:
                        print(f"WARNING: Generated post was {len(text)} chars — trimming to fit X's 280 limit.")
                        lines = text.split("\n")
                        hashtag_line = ""
                        if lines and lines[-1].strip().startswith("#"):
                            hashtag_line = lines.pop()
                        body = "\n".join(lines).strip()
                        budget = MAX_LEN - (len(hashtag_line) + 1 if hashtag_line else 0)
                        if len(body) > budget:
                            body = body[:max(budget - 1, 0)].rstrip() + "…"
                        text = (body + ("\n" + hashtag_line if hashtag_line else "")).strip()
                        if len(text) > MAX_LEN:
                            text = text[:MAX_LEN-1].rstrip() + "…"

                    if not custom_headline:
                        save_recent_headline(live_headline)
                    return text, category, live_headline, image_query
                except Exception as e:
                    print(f"Gemini API ({model_name}) Attempt {attempt+1} Failed: {e}")
                    time.sleep(5 * (attempt + 1))
            if skipped_this_headline:
                break

        if skipped_this_headline:
            continue
        else:
            break

    return None, category, live_headline, None


CATEGORY_FALLBACK_IMAGES = {
    "india": ["indian flag", "india map", "new delhi city"],
    "global": ["world map", "globe earth", "international flags"],
    "geopolitics": ["world map", "united nations", "world leaders meeting"],
    "technology": ["technology computer", "artificial intelligence", "smartphone technology"],
    "stock market": ["stock market chart", "stock exchange", "business finance"],
    "economic": ["indian economy", "business finance city", "money currency"],
}

def _search_pexels(keyword):
    try:
        pex_url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(keyword)}&per_page=30"
        pex_headers = {"Authorization": PEXELS_API_KEY}
        res = requests.get(pex_url, headers=pex_headers, timeout=5)
        if res.status_code == 200:
            photos = res.json().get('photos', [])
            if photos:
                selected = random.choice(photos)
                return selected['src']['large2x']
    except Exception as e:
        print(f"Pexels API Fetch Error ({keyword}): {e}")
    return None

def get_dynamic_unique_image_url(news_text, category, image_query=None):
    candidates = []
    if image_query:
        query_lower = image_query.lower()
        if category == "india" and "india" not in query_lower and "indian" not in query_lower:
            candidates.append(f"Indian {image_query}")
        candidates.append(image_query)
        words = image_query.split()
        if len(words) > 2:
            candidates.append(" ".join(words[:2]))

    candidates.extend(CATEGORY_FALLBACK_IMAGES.get(category, ["news update"]))

    if PEXELS_API_KEY:
        for keyword in candidates:
            print(f"Trying Pexels search: '{keyword}'...")
            result = _search_pexels(keyword)
            if result:
                print(f"Pexels match found for: '{keyword}'")
                return result
        print("No Pexels match found for any candidate keyword — using random fallback image.")

    sig_rand = random.randint(100, 99999)
    return f"https://picsum.photos/seed/{sig_rand}/1080/1080"

def _recolor_logo_white(logo):
    logo = logo.convert("RGBA")
    r, g, b, a = logo.split()
    white = Image.new("L", logo.size, 255)
    return Image.merge("RGBA", (white, white, white, a))

CARD_LAYOUTS = ["bottom", "top", "bottom_accent"]
ACCENT_LINE_COLORS = [(30, 58, 95), (91, 33, 33), (27, 67, 50), (55, 55, 60)]

def create_news_card_overlay(base_img_url, headline_text, category_badge):
    try:
        res = requests.get(base_img_url, timeout=12)
        if res.status_code != 200:
            res = requests.get("https://picsum.photos/1080/1080", timeout=12)

        img = Image.open(BytesIO(res.content)).convert("RGBA").resize((1080, 1080))

        layout = random.choice(CARD_LAYOUTS)
        print(f"Using card layout: {layout}")

        clean_headline = headline_text.split(" - ")[0]
        title_font = get_font(34, bold=True)
        wrapped_lines = textwrap.wrap(clean_headline, width=42)[:2]
        src_font = get_font(20, bold=False)

        logo_img = None
        if os.path.exists(LOGO_PATH):
            try:
                logo = Image.open(LOGO_PATH).convert("RGBA")
                logo_w = 190
                ratio = logo_w / logo.width
                logo = logo.resize((logo_w, int(logo.height * ratio)))
                logo_img = _recolor_logo_white(logo)
            except Exception as e:
                print(f"Logo Overlay Error: {e}")
        else:
            print(f"WARNING: Logo not found at {LOGO_PATH} — check the file is committed to the repo root.")

        if layout == "top":
            bar_h = 260
            overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            for i in range(bar_h):
                alpha = int(235 * (1 - i / bar_h))
                odraw.line([(0, i), (1080, i)], fill=(8, 10, 16, alpha))
            odraw.rectangle([(0, 0), (1080, 30)], fill=(8, 10, 16, 245))
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

            y_text = 30
            if logo_img:
                img.paste(logo_img, (40, y_text), logo_img)
                y_text += logo_img.height + 18
            for line in wrapped_lines:
                draw.text((40, y_text), line, fill="#FFFFFF", font=title_font)
                y_text += 44
            draw.text((40, y_text + 6), f"WorldScopeX · {category_badge.title()}", fill="#9CA3AF", font=src_font)

        else:
            bar_h = 260
            overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            for i in range(bar_h):
                alpha = int(235 * (i / bar_h))
                odraw.line([(0, 1080 - bar_h + i), (1080, 1080 - bar_h + i)], fill=(8, 10, 16, alpha))
            odraw.rectangle([(0, 1080 - 50), (1080, 1080)], fill=(8, 10, 16, 245))
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

            if layout == "bottom_accent":
                accent = random.choice(ACCENT_LINE_COLORS)
                draw.rectangle([(0, 0), (1080, 6)], fill=accent)

            if logo_img:
                img.paste(logo_img, (40, 1080 - bar_h - logo_img.height - 18), logo_img)

            y_text = 1080 - bar_h + 30
            for line in wrapped_lines:
                draw.text((40, y_text), line, fill="#FFFFFF", font=title_font)
                y_text += 44
            draw.text((40, y_text + 6), f"WorldScopeX · {category_badge.title()}", fill="#9CA3AF", font=src_font)

        output_path = "final_card.png"
        img.convert("RGB").save(output_path)
        return output_path
    except Exception as e:
        print(f"News Card Overlay Creation Error: {e}")
        return None

def _verify_image_url(url):
    try:
        res = requests.get(url, timeout=10, stream=True)
        content_type = res.headers.get("Content-Type", "")
        if res.status_code == 200 and content_type.startswith("image/"):
            return True
        print(f"Image URL verification failed for {url} (status={res.status_code}, content-type={content_type})")
    except Exception as e:
        print(f"Image URL verification error for {url}: {e}")
    return False

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
            if direct_url and _verify_image_url(direct_url):
                print(f"FreeImage Host Upload SUCCESS (verified): {direct_url}")
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
                    if _verify_image_url(direct_url):
                        print(f"TmpFiles Upload SUCCESS (verified): {direct_url}")
                        return direct_url
    except Exception as e:
        print(f"TmpFiles Upload Error: {e}")

    try:
        url = "https://catbox.moe/user/api.php"
        with open(image_path, "rb") as file:
            files = {"fileToUpload": file}
            data = {"reqtype": "fileupload"}
            res = requests.post(url, files=files, data=data, timeout=20)
            if res.status_code == 200 and res.text.strip().startswith("http"):
                direct_url = res.text.strip()
                if _verify_image_url(direct_url):
                    print(f"Catbox Upload SUCCESS (verified): {direct_url}")
                    return direct_url
    except Exception as e:
        print(f"Catbox Upload Error: {e}")

    print("All image hosts failed verification — will fall back to the raw photo URL instead of the branded card.")
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
    custom_headline = os.getenv("CUSTOM_HEADLINE", "").strip() or None
    custom_category = os.getenv("CUSTOM_CATEGORY", "").strip() or None

    text, category, headline, image_query = generate_news_with_gemini(custom_headline, custom_category)
    if text and headline:
        print(f"Image search query from Gemini: {image_query}")
        base_img = get_dynamic_unique_image_url(text, category, image_query)
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
