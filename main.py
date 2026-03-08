import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

SEEN_FILE = "seen_niches.json"
SLEEP_SECONDS = 3600
TARGET_NICHES_PER_CYCLE = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}


# =========================
# STORAGE
# =========================

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return []

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        cleaned = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    cleaned.append(item)
        return cleaned
    except Exception:
        return []


def save_seen(data):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# TELEGRAM
# =========================

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": message[:4000]},
            timeout=20
        )
        print("TELEGRAM STATUS:", r.status_code)
        print("TELEGRAM RESPONSE:", r.text[:250])
        data = r.json()
        return data.get("ok", False)
    except Exception as e:
        print("TELEGRAM ERROR:", str(e))
        return False


# =========================
# HELPERS
# =========================

def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\-]", "", text)
    return text


def text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def make_signature(item: dict) -> str:
    niche = normalize_text(item.get("niche", ""))
    subniche = normalize_text(item.get("subniche", ""))
    microniche = normalize_text(item.get("microniche", ""))
    problem = normalize_text(item.get("problem", ""))
    audience = normalize_text(item.get("audience", ""))
    return f"{niche}|{subniche}|{microniche}|{problem}|{audience}"


def is_duplicate_or_too_similar(item: dict, existing_items: list) -> bool:
    current_niche = item.get("niche", "")
    current_sub = item.get("subniche", "")
    current_micro = item.get("microniche", "")

    current_combo = f"{current_niche} | {current_sub} | {current_micro}"
    current_ns = f"{current_niche} | {current_sub}"

    for old in existing_items:
        if not isinstance(old, dict):
            continue

        old_niche = old.get("niche", "")
        old_sub = old.get("subniche", "")
        old_micro = old.get("microniche", "")

        old_combo = f"{old_niche} | {old_sub} | {old_micro}"
        old_ns = f"{old_niche} | {old_sub}"

        if normalize_text(current_combo) == normalize_text(old_combo):
            return True

        if text_similarity(current_combo, old_combo) >= 0.86:
            return True

        if text_similarity(current_ns, old_ns) >= 0.90:
            return True

    return False


def safe_get(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception:
        return ""
    return ""


def safe_get_json(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def extract_text_items_from_html(html, selectors):
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = []

    bad_words = [
        "sign in", "privacy", "terms", "cookie", "cookies", "help", "download",
        "open app", "log in", "login", "account", "about", "careers", "policy",
        "home home", "for business", "tiktok for business", "facebook", "meta",
        "trending now", "send feedback", "query_stats"
    ]

    for selector in selectors:
        try:
            for el in soup.select(selector):
                txt = el.get_text(" ", strip=True)
                txt = re.sub(r"\s+", " ", txt).strip()

                if not (4 <= len(txt) <= 100):
                    continue

                low = normalize_text(txt)
                if any(b in low for b in bad_words):
                    continue

                if txt not in items:
                    items.append(txt)
        except Exception:
            continue

    return items


def extract_json_block(text: str):
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return []

    return []


# =========================
# MARKET SOURCES
# =========================

def get_reddit_signals():
    urls = [
        "https://www.reddit.com/r/Entrepreneur/top.json?t=day&limit=20",
        "https://www.reddit.com/r/smallbusiness/top.json?t=day&limit=20",
        "https://www.reddit.com/r/AmazonFBA/top.json?t=day&limit=20",
    ]

    results = []

    for url in urls:
        data = safe_get_json(url)
        if not data:
            continue

        try:
            posts = data["data"]["children"]
            for p in posts:
                title = p["data"].get("title", "").strip()
                if 4 <= len(title) <= 120 and title not in results:
                    results.append(title)
        except Exception:
            continue

    return results[:50]


def get_google_trends_signals():
    html = safe_get("https://trends.google.com/trending?geo=US&hl=en")
    return extract_text_items_from_html(html, ["a", "span", "div"])[:30]


def get_amazon_signals():
    html = safe_get("https://www.amazon.com/Best-Sellers/zgbs")
    return extract_text_items_from_html(html, ["a", "span"])[:40]


def get_pinterest_signals():
    html = safe_get("https://www.pinterest.com/")
    return extract_text_items_from_html(html, ["a", "span"])[:30]


def get_tiktok_signals():
    html = safe_get("https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en")
    return extract_text_items_from_html(html, ["a", "span", "h1", "h2", "h3"])[:35]


def get_meta_ads_signals():
    html = safe_get("https://www.facebook.com/ads/library/")
    return extract_text_items_from_html(html, ["a", "span", "div"])[:25]


def get_fallback_signals():
    return [
        "kitchen storage",
        "fridge organizers",
        "car cleaning tools",
        "pet accessories",
        "desk organization",
        "portable workout gear",
        "anxiety relief tools",
        "smart home accessories",
        "bathroom organizers",
        "shoe storage",
        "self care products",
        "makeup storage",
        "cable organizers",
        "small space storage",
        "portable travel tools",
        "home gardening tools",
        "cat cleaning tools",
        "dog hydration accessories",
        "sleep improvement gadgets",
        "ergonomic office tools",
        "portable cleaning gadgets",
        "space saving home tools"
    ]


def collect_signals():
    signals = []

    sources = [
        ("reddit", get_reddit_signals),
        ("google_trends", get_google_trends_signals),
        ("amazon", get_amazon_signals),
        ("pinterest", get_pinterest_signals),
        ("tiktok_creative_center", get_tiktok_signals),
        ("meta_ads_library", get_meta_ads_signals),
    ]

    for name, fn in sources:
        try:
            data = fn()
            print(f"SOURCE {name}: {len(data)}")
            if data:
                signals.extend(data)
        except Exception as e:
            print(f"SOURCE ERROR {name}: {e}")

    cleaned = []
    for s in signals:
        s = normalize_text(s)
        if len(s) < 4 or len(s) > 100:
            continue
        if s not in cleaned:
            cleaned.append(s)

    if len(cleaned) < 25:
        cleaned.extend(get_fallback_signals())

    cleaned = list(dict.fromkeys(cleaned))
    return cleaned[:140]


# =========================
# AI ANALYSIS
# =========================

def generate_niches_from_signals(signals, existing_signatures):
    prompt = f"""
أنت محلل سوق إيكومرس قوي جدًا.

لديك إشارات حقيقية من:
- Amazon
- Reddit
- Google Trends
- Pinterest
- TikTok Creative Center
- Meta Ads Library

هذه الإشارات:
{signals}

هذه التواقيع القديمة المستعملة:
{existing_signatures}

المطلوب:
- أعطني فقط 6 niches قوية جدًا
- لا تعطيني niches عامة وضعيفة
- ركز على niches فيها مشكلة واضحة وفرصة بيع
- لكل niche أعطني:
  1) niche
  2) subniche
  3) microniche
  4) problem
  5) audience
  6) algeria_success
  7) algeria_audience
  8) signal_strength

شروط:
- microniche يجب أن يكون دقيقًا جدًا
- signal_strength يكون أحد هذه فقط:
  "منخفضة" أو "متوسطة" أو "مرتفعة"
- algeria_success يكون نسبة مئوية فقط
- algeria_audience يكون نسبة مئوية فقط
- لا تكتب منتجات
- لا تكتب روابط
- لا تكتب شرحًا طويلًا
- لا تكرر نفس المعنى بصياغة مختلفة
- اجعلها مناسبة للبيع في الجزائر

أعد النتيجة بصيغة JSON فقط:
[
  {{
    "niche": "اسم النيش",
    "subniche": "اسم السوب نيش",
    "microniche": "اسم المايكرو نيش",
    "problem": "مشكلة قصيرة",
    "audience": "جمهور قصير",
    "algeria_success": "82%",
    "algeria_audience": "76%",
    "signal_strength": "مرتفعة"
  }}
]
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "أنت خبير niches وتعيد JSON صحيح فقط."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
        )
        content = response.choices[0].message.content.strip()
        return extract_json_block(content)
    except Exception as e:
        print("AI ERROR:", str(e))
        return []


def get_hardcoded_fallback_niches():
    return [
        {
            "niche": "العناية بالقطط",
            "subniche": "تنظيف صندوق الرمل",
            "microniche": "portable cat litter cleaner niche",
            "problem": "تنظيف صندوق الرمل متعب ويأخذ وقت",
            "audience": "مالكو القطط داخل الشقق",
            "algeria_success": "74%",
            "algeria_audience": "63%",
            "signal_strength": "مرتفعة",
        },
        {
            "niche": "تنظيف السيارة",
            "subniche": "تنظيف المقصورة",
            "microniche": "mini handheld car vacuum niche",
            "problem": "تنظيف السيارة الداخلي متعب ويأخذ وقت",
            "audience": "أصحاب السيارات",
            "algeria_success": "86%",
            "algeria_audience": "90%",
            "signal_strength": "مرتفعة",
        },
        {
            "niche": "تنظيم المطبخ",
            "subniche": "تخزين الثلاجة",
            "microniche": "stackable fridge organizer niche",
            "problem": "فوضى الثلاجة وضياع المساحة",
            "audience": "العائلات",
            "algeria_success": "84%",
            "algeria_audience": "88%",
            "signal_strength": "مرتفعة",
        },
        {
            "niche": "العناية بالحيوانات",
            "subniche": "إكسسوارات الكلاب",
            "microniche": "portable dog water bottle niche",
            "problem": "صعوبة سقي الكلب خارج المنزل",
            "audience": "أصحاب الكلاب",
            "algeria_success": "68%",
            "algeria_audience": "62%",
            "signal_strength": "متوسطة",
        },
        {
            "niche": "العناية الذاتية",
            "subniche": "أدوات الاسترخاء",
            "microniche": "portable neck massager niche",
            "problem": "التوتر وآلام الرقبة اليومية",
            "audience": "الرجال والنساء",
            "algeria_success": "79%",
            "algeria_audience": "85%",
            "signal_strength": "متوسطة",
        },
        {
            "niche": "تنظيم المكتب",
            "subniche": "إدارة الأسلاك",
            "microniche": "magnetic cable clip niche",
            "problem": "تشابك الكابلات فوق المكتب",
            "audience": "الموظفون والطلاب",
            "algeria_success": "76%",
            "algeria_audience": "74%",
            "signal_strength": "متوسطة",
        },
    ]


# =========================
# MESSAGE FORMAT
# =========================

def format_niche_message(index: int, item: dict) -> str:
    niche = item.get("niche", "غير محدد").strip()
    subniche = item.get("subniche", "غير محدد").strip()
    microniche = item.get("microniche", "غير محدد").strip()
    problem = item.get("problem", "غير محدد").strip()
    audience = item.get("audience", "غير محدد").strip()
    algeria_success = item.get("algeria_success", "غير محدد").strip()
    algeria_audience = item.get("algeria_audience", "غير محدد").strip()
    signal_strength = item.get("signal_strength", "غير محدد").strip()

    return f"""🔥 Niche #{index}

📦 النيش
{niche}

🔎 السوب نيش
{subniche}

🧩 المايكرو نيش
{microniche}

⚠️ المشكلة
{problem}

🎯 الجمهور
{audience}

🇩🇿 نسبة نجاح النيش في الجزائر
{algeria_success}

👥 نسبة وجود الجمهور في الجزائر
{algeria_audience}

📊 قوة الإشارة السوقية
{signal_strength}

━━━━━━━━━━━━
"""


# =========================
# MAIN LOOP
# =========================

def niche_loop():
    print("🚀 Niche Finder Strong 3 + TikTok + Meta Started")

    while True:
        seen = load_seen()

        existing_signatures = [
            item.get("signature", "")
            for item in seen
            if isinstance(item, dict)
        ]

        signals = collect_signals()
        print("SIGNALS COUNT:", len(signals))
        print("SIGNALS SAMPLE:", signals[:10])

        raw_items = generate_niches_from_signals(signals, existing_signatures)

        if not raw_items:
            raw_items = get_hardcoded_fallback_niches()

        strength_order = {"مرتفعة": 3, "متوسطة": 2, "منخفضة": 1}
        raw_items = sorted(
            raw_items,
            key=lambda x: strength_order.get(x.get("signal_strength", "منخفضة"), 1),
            reverse=True
        )

        new_items = []

        for item in raw_items:
            if not isinstance(item, dict):
                continue

            signature = make_signature(item)
            if not signature:
                continue

            if is_duplicate_or_too_similar(item, seen):
                continue

            item["signature"] = signature
            new_items.append(item)
            seen.append(item)

            if len(new_items) >= TARGET_NICHES_PER_CYCLE:
                break

        if not new_items:
            print("⚠️ لا توجد niches قوية جديدة في هذه الدورة")
        else:
            ok_count = 0

            if send_telegram(f"🚀 تم العثور على {len(new_items)} niches قوية جديدة"):
                ok_count += 1

            for i, item in enumerate(new_items, start=1):
                if send_telegram(format_niche_message(i, item)):
                    ok_count += 1

            save_seen(seen)
            print(f"✅ Telegram sent count: {ok_count}")

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    niche_loop()
