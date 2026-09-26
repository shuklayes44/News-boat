import os
import re
import time
import json
import base64
import random
import textwrap
import urllib.parse
import unicodedata
import feedparser
import requests
from datetime import datetime
from google import genai
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
WEBSITE_REPO_TOKEN = os.getenv("WEBSITE_REPO_TOKEN")

LOGO_PATH = "logo.png"
FONT_BOLD_PATH = "fonts/Roboto-Bold.ttf"
FONT_REGULAR_PATH = "fonts/Roboto-Regular.ttf"
WEBSITE_DATA_PATH = "src/data/articles.ts"
# NOTE: verify this against an actual published article URL on the site and
# fix this one line if the real routing pattern is different.
ARTICLE_URL_PATTERN = "https://worldscopex-hub.worldscopex.workers.dev/article/{slug}"

HISTORY_FILE = "posted_history.json"
HISTORY_MAX = 40

CATEGORY_MAP = {
    "india": "india",
    "global": "world",
    "geopolitics": "geopolitics",
    "technology": "technology",
    "stock market": "economy",
    "economic": "economy",
}


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
        print(f"WARNING: Font file not found at {font_path} — text will render tiny using default font.")
    return ImageFont.load_default()


def _clean_rss_summary(html):
    if not html:
        return ""
    text = re.sub("<[^<]+?>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]


def fetch_full_article_text(url, max_chars=4000):
    """Fetch the original publisher's article and extract its main text, so
    Gemini has real facts to work with instead of just a headline."""
    if not url:
        return None
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; WorldScopeXBot/1.0)"}
        res = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        if res.status_code != 200:
            print(f"Full-article fetch bad status ({res.status_code}) for {url}")
            return None
        try:
            import trafilatura
            extracted = trafilatura.extract(res.text, include_comments=False, include_tables=False)
        except Exception as e:
            print(f"trafilatura extraction error: {e}")
            extracted = None
        if not extracted or len(extracted.strip()) < 200:
            print("Full-article extraction too short/empty — will fall back to RSS snippet.")
            return None
        return extracted.strip()[:max_chars]
    except Exception as e:
        print(f"Full-article fetch error for {url}: {e}")
        return None


def fetch_live_google_news(topic_query):
    formatted_query = topic_query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={formatted_query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries and len(feed.entries) > 0:
            selected = random.choice(feed.entries[:10])
            summary = _clean_rss_summary(selected.get("summary", ""))
            link = selected.get("link", "")
            return selected.title, summary, link
    except Exception as e:
        print(f"Google News RSS Error: {e}")
    return None, None, None


def fetch_top_headlines(edition="india"):
    if edition == "world":
        rss_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    else:
        rss_url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries and len(feed.entries) > 0:
            selected = random.choice(feed.entries[:6])
            summary = _clean_rss_summary(selected.get("summary", ""))
            link = selected.get("link", "")
            return selected.title, summary, link
    except Exception as e:
        print(f"Google News Top Headlines RSS Error: {e}")
    return None, None, None


def generate_news_with_gemini(custom_headline=None, custom_category=None):
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY Missing!")
        return None, "india", None, None, None

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
            headline, summary, link = fetch_top_headlines(edition)
        else:
            selected_query, cat = random.choice(topics)
            print(f"Fetching Live Breaking News for query: '{selected_query}'...")
            headline, summary, link = fetch_live_google_news(selected_query)

        if not headline:
            print("Primary query skipped, checking fallback news topics...")
            headline, summary, link = fetch_top_headlines("india")
            cat = "india"
            if not headline:
                for query, c in topics:
                    headline, summary, link = fetch_live_google_news(query)
                    if headline:
                        cat = c
                        break
        return headline, cat, summary, link

    client = genai.Client(api_key=GEMINI_API_KEY)
    models_to_try = ['gemini-3.5-flash-lite', 'gemini-flash-latest', 'gemini-3.6-flash']

    HEADLINE_ATTEMPTS = 1 if custom_headline else 3

    for headline_attempt in range(HEADLINE_ATTEMPTS):
        rss_summary, rss_link = "", ""
        if custom_headline:
            live_headline = custom_headline
            category = custom_category if custom_category else "technology"
            print(f"Using CUSTOM headline (manual trigger): '{live_headline}' [category: {category}]")
            skip_allowed = False
        else:
            live_headline, category, rss_summary, rss_link = fetch_one_headline()
            if not live_headline:
                print("Error: Could not fetch real live news RSS feed. Aborting execution.")
                return None, category, None, None, None
            print(f"SUCCESS: Fresh Live Headline Fetched -> {live_headline}")

            recent_history = load_recent_headlines()
            is_last_attempt = headline_attempt >= HEADLINE_ATTEMPTS - 1
            if is_duplicate_headline(live_headline, recent_history) and not is_last_attempt:
                print(f"DUPLICATE: '{live_headline}' looks like something posted recently — trying a different headline.")
                continue

            skip_allowed = headline_attempt < HEADLINE_ATTEMPTS - 1

        full_article_text = None
        if not custom_headline and rss_link:
            print("Attempting to fetch full original article for factual context...")
            full_article_text = fetch_full_article_text(rss_link)

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

        if full_article_text:
            context_line = (
                "\nFULL ARTICLE CONTEXT (this is the actual source article — use it "
                "extensively for real facts, figures, dates and specifics in both the "
                "social post and the website article):\n"
                f"'''{full_article_text}'''\n"
            )
        elif rss_summary:
            context_line = f"\nCONTEXT SNIPPET (brief, from the news feed): '{rss_summary}'\n"
        else:
            context_line = "\nCONTEXT SNIPPET: none available — rely only on the headline.\n"

        prompt = (
            f"STRICT INSTRUCTION: Write a high-impact, factual breaking news post based ONLY on this live headline:\n"
            f"HEADLINE: '{live_headline}'\n"
            f"{context_line}"
            f"{skip_instruction}\n"
            "STRICT FORMATTING RULES:\n"
            "1. Language: Professional English for a global audience, with special emphasis "
            "on relevance to Indian readers — where the headline supports it, note the "
            "impact on India (markets, policy, jobs, prices) without inventing anything not "
            "in the headline or context snippet.\n"
            "2. Structure of the SOCIAL POST (this part only, lines 1-6):\n"
            "   - Line 1: An attention-grabbing opener with an emoji. Vary the style each "
            "time — sometimes a bold CAPS hook ('🚨 MARKETS CRASH!'), sometimes a short "
            "question ('🤔 Is this the end of...?'), sometimes a striking stat "
            "('📉 ₹8 lakh crore wiped out in a day'). Do not use the exact same opening "
            "phrase every time.\n"
            "   - Line 2-3: Core factual summary. Where the headline/context supports it, "
            "include ONE specific, concrete number or statistic rather than vague words "
            "like 'a lot' or 'significant'.\n"
            "   - Line 4: One short sentence of 'why this matters' — connect the news to a "
            "real, tangible impact on an ordinary reader's life (money, jobs, prices, "
            "safety, daily routine) wherever the headline reasonably supports it. If it "
            "genuinely doesn't apply, give one line of background context instead.\n"
            "   - Line 5: Short engagement question for the audience.\n"
            "   - Line 6: A line starting exactly with 'IMG_QUERY:' followed by a short "
            "1-4 word English stock-photo search phrase describing the single most "
            "visually common, easy-to-find subject of this news. Keep it SIMPLE and "
            "generic. CRITICAL: if this news is specifically about India, you MUST "
            "include the word 'Indian' or 'India' in the phrase — otherwise a generic "
            "word can pull an unrelated country's imagery. Never name a country in the "
            "query that isn't the one this story is actually about.\n"
            "3. Then add TWO MORE lines for the WEBSITE ARTICLE version:\n"
            "   - A line starting exactly with 'DEK:' followed by one factual one-sentence "
            "subheading (max 20 words) summarizing the news, using only facts from the "
            "headline/context snippet above.\n"
            "   - A line starting exactly with 'BODY:' followed by 3 to 4 short news-style "
            "paragraphs, each on its own line, written in a professional wire-service style "
            "(like Reuters/Bloomberg/BBC). Use ONLY facts present in the headline and "
            "context snippet given above — do NOT invent any numbers, quotes, names, dates, "
            "or details that are not present in that information. If the given information "
            "is limited, keep the paragraphs general/contextual (background, why it matters, "
            "what to watch next) rather than fabricating specifics.\n"
            "4. ACCURACY IS CRITICAL across both the post and the article: only use facts "
            "present in the headline or context snippet. Never invent, guess, or embellish.\n"
            "5. ABSOLUTELY DO NOT ADD ANY SYSTEM CODE TAGS. Do NOT include any hashtags "
            "anywhere.\n"
            "6. EMOJI LIMIT: Use EXACTLY ONE emoji in the entire post, only in Line 1. No "
            "emoji anywhere else, including the website article.\n"
            "7. Total Length of the SOCIAL POST part only (lines 1-5, excluding IMG_QUERY/"
            "DEK/BODY): aim for around 180 characters, and never exceed 220 — this post "
            "will also have a 'Read more' link appended later, so leave margin under X's "
            "280 limit. Emoji count as roughly DOUBLE weight on X/Twitter's real character "
            "limit."
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
                    dek = None
                    body_paragraphs = []
                    in_body = False
                    post_lines = []

                    for line in raw_text.splitlines():
                        stripped = line.strip()
                        upper = stripped.upper()
                        if upper.startswith("IMG_QUERY:"):
                            image_query = stripped.split(":", 1)[1].strip()
                            in_body = False
                        elif upper.startswith("DEK:"):
                            dek = stripped.split(":", 1)[1].strip()
                            in_body = False
                        elif upper.startswith("BODY:"):
                            in_body = True
                            first = stripped.split(":", 1)[1].strip()
                            if first:
                                body_paragraphs.append(first)
                        elif stripped.startswith("#"):
                            continue
                        elif in_body:
                            if stripped:
                                body_paragraphs.append(stripped)
                        else:
                            post_lines.append(line)

                    text = "\n".join(post_lines).strip()

                    def x_weighted_length(s):
                        return sum(2 if ord(ch) > 0x2FF else 1 for ch in s)

                    MAX_LEN = 220
                    if x_weighted_length(text) > MAX_LEN:
                        print(f"WARNING: Generated post was {x_weighted_length(text)} X-weighted chars — trimming.")
                        while x_weighted_length(text) + 2 > MAX_LEN and len(text) > 0:
                            text = text[:-1]
                        text = text.rstrip() + "…"

                    website_content = None
                    if dek and body_paragraphs:
                        website_content = {"dek": dek, "paragraphs": body_paragraphs}

                    if not custom_headline:
                        save_recent_headline(live_headline)
                    return text, category, live_headline, image_query, website_content
                except Exception as e:
                    print(f"Gemini API ({model_name}) Attempt {attempt+1} Failed: {e}")
                    time.sleep(5 * (attempt + 1))
            if skipped_this_headline:
                break

        if skipped_this_headline:
            continue
        else:
            break

    return None, category, live_headline, None, None


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
        text_lower = (news_text or "").lower()
        mentions_india = "india" in text_lower or "indian" in text_lower
        if category == "india" and mentions_india and "india" not in query_lower and "indian" not in query_lower:
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
            print(f"WARNING: Logo not found at {LOGO_PATH}.")

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
            draw.text((40, y_text + 6), f"WorldScopeX · {category_badge.title()} · worldscopex-hub.workers.dev", fill="#9CA3AF", font=src_font)

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
            draw.text((40, y_text + 6), f"WorldScopeX · {category_badge.title()} · worldscopex-hub.workers.dev", fill="#9CA3AF", font=src_font)

        output_path = "final_card.png"
        img.convert("RGB").save(output_path)
        return output_path
    except Exception as e:
        print(f"News Card Overlay Creation Error: {e}")
        return None


def commit_card_to_github(image_path):
    """Commit the generated card image straight into this repo and return its
    public raw.githubusercontent.com URL, avoiding any third-party image host."""
    try:
        import subprocess
        repo = os.getenv("GITHUB_REPOSITORY")
        if not repo:
            print("GITHUB_REPOSITORY env var missing — not running inside GitHub Actions?")
            return None

        os.makedirs("cards", exist_ok=True)
        filename = f"cards/card_{int(time.time())}_{random.randint(1000, 9999)}.png"
        os.replace(image_path, filename)

        subprocess.run(["git", "config", "user.name", "news-bot"], check=True)
        subprocess.run(["git", "config", "user.email", "news-bot@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", filename], check=True)
        subprocess.run(["git", "commit", "-m", f"Add card image {filename} [skip ci]"], check=True)
        subprocess.run(["git", "push"], check=True)

        branch = os.getenv("GITHUB_REF_NAME", "main")
        raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{filename}"
        print(f"Card committed to GitHub — raw URL: {raw_url}")
        return raw_url
    except Exception as e:
        print(f"GitHub commit/push error: {e}")
        return None


def _slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80].strip("-") or "news-update"


def build_website_article(website_content, headline, category, image_url, rss_link):
    site_category = CATEGORY_MAP.get(category, "world")
    slug = f"{_slugify(headline)}-{int(time.time())}"

    paragraphs = website_content["paragraphs"] if website_content else [headline]
    body = [{"type": "paragraph", "text": p} for p in paragraphs]

    word_count = sum(len(p.split()) for p in paragraphs)
    reading_minutes = max(1, round(word_count / 200))

    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    source_note = {
        "label": "Google News aggregation",
        "detail": headline,
    }
    if rss_link:
        source_note["url"] = rss_link

    dek = (website_content["dek"] if website_content else headline)[:200]

    article = {
        "slug": slug,
        "category": site_category,
        "headline": headline,
        "dek": dek,
        "author": {"name": "WorldScopeX Desk", "role": "Editorial Desk"},
        "verificationStatus": "verified",
        "publishedAt": now_iso,
        "readingMinutes": reading_minutes,
        "heroImage": image_url,
        "imageAlt": headline,
        "imageCredit": "Photo via Pexels",
        "tags": [site_category],
        "featured": False,
        "trending": False,
        "body": body,
        "sources": [source_note],
        "relatedStories": [],
    }
    return article, slug


def _website_repo_full_name():
    news_repo = os.getenv("GITHUB_REPOSITORY", "")
    if "/" in news_repo:
        owner = news_repo.split("/")[0]
        return f"{owner}/worldscopex-hub"
    return None


def publish_article_to_website(article):
    if not WEBSITE_REPO_TOKEN:
        print("WEBSITE_REPO_TOKEN not set — skipping website publish (social post still goes out).")
        return False

    repo = _website_repo_full_name()
    if not repo:
        print("Could not determine website repo name — skipping website publish.")
        return False

    headers = {
        "Authorization": f"token {WEBSITE_REPO_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    api_url = f"https://api.github.com/repos/{repo}/contents/{WEBSITE_DATA_PATH}"

    try:
        res = requests.get(api_url, headers=headers, timeout=15)
        if res.status_code != 200:
            print(f"Website publish: could not fetch articles.ts ({res.status_code}): {res.text[:200]}")
            return False

        data = res.json()
        sha = data["sha"]
        content = base64.b64decode(data["content"]).decode("utf-8")

        marker = "const articleRecords: Article[] = ["
        idx = content.find(marker)
        if idx == -1:
            print("Website publish: could not find 'articleRecords' array in articles.ts")
            return False

        insert_pos = idx + len(marker)
        rest = content[insert_pos:].lstrip()
        needs_comma = not rest.startswith("]")

        article_json = json.dumps(article, indent=2, ensure_ascii=False)
        new_content = (
            content[:insert_pos]
            + "\n  " + article_json + ("," if needs_comma else "")
            + "\n" + content[insert_pos:]
        )

        encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
        payload = {
            "message": f"Add article: {article['headline'][:60]}",
            "content": encoded,
            "sha": sha,
        }
        put_res = requests.put(api_url, headers=headers, json=payload, timeout=20)
        if put_res.status_code in (200, 201):
            print(f"Website article published: {article['slug']}")
            return True
        else:
            print(f"Website publish failed ({put_res.status_code}): {put_res.text[:300]}")
            return False
    except Exception as e:
        print(f"Website publish error: {e}")
        return False


def shorten_url(long_url):
    try:
        res = requests.get(
            "https://tinyurl.com/api-create.php",
            params={"url": long_url},
            timeout=10,
        )
        if res.status_code == 200 and res.text.strip().startswith("http"):
            return res.text.strip()
    except Exception as e:
        print(f"URL shorten error: {e}")
    return long_url


def send_direct_to_buffer(post_text, image_url=None):
    if not BUFFER_ACCESS_TOKEN:
        print("Error: BUFFER_ACCESS_TOKEN Missing!")
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
        media_asset = f', assets: [{{ image: {{ url: "{image_url}" }} }}]' if image_url else ''

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

    text, category, headline, image_query, website_content = generate_news_with_gemini(custom_headline, custom_category)

    if text and headline:
        print(f"Image search query from Gemini: {image_query}")
        base_img = get_dynamic_unique_image_url(text, category, image_query)
        card_file = create_news_card_overlay(base_img, headline, category)

        final_image_url = None
        if card_file:
            final_image_url = commit_card_to_github(card_file)
        if not final_image_url:
            final_image_url = base_img

        print(f"Final Card Image URL: {final_image_url}")

        # Website publish is ADDITIVE and non-blocking: any failure here is
        # caught and logged, and can NEVER stop or affect social posting below.
        website_url = None
        try:
            if website_content:
                article, slug = build_website_article(website_content, headline, category, final_image_url, None)
                if publish_article_to_website(article):
                    website_url = ARTICLE_URL_PATTERN.format(slug=slug)
            else:
                print("No website content generated for this headline — skipping website publish.")
        except Exception as e:
            print(f"Website publish step failed (social posting is unaffected): {e}")

        final_post_text = text
        if website_url:
            short_url = shorten_url(website_url)
            final_post_text = f"{text}\n\nRead more: {short_url}"

        print(f"Post Text:\n{final_post_text}")
        # Posting the link only (no attached image) so platforms auto-unfurl
        # a preview card from the website page instead.
        send_direct_to_buffer(final_post_text, image_url=final_image_url)
    else:
        print("Skipping execution: Live RSS news fetch or Gemini failed.")
