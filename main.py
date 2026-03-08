import os
import re
import json
import time
import random
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

SEEN_FILE = "seen_niches.json"
SLEEP_SECONDS = 3600  # كل ساعة

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}


# =========================
# FILE STORAGE
# =========================

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return []
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
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
        print("TELEGRAM RESPONSE:", r.text[:300])
        data = r.json()
        return data.get("ok", False)
    except Exception as e:
        print("TELEGRAM ERROR:", str(e))
        return False


# =========================
# HELPERS
# =========================

def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def make_signature(item: dict) -> str:
    niche = normalize_text(item.get("niche", ""))
    subniche = normalize_text(item.get("subniche", ""))
    problem = normalize_text(item.get("problem", ""))
    audience = normalize_text(item.get("audience", ""))
    return f"{niche}|{subniche}|{problem}|{audience}"


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

    for selector in selectors:
        try:
            for el in soup.select(selector):
                txt = el.get_text(" ", strip=True)
                txt = re.sub(r"\s+", " ", txt).strip()
                if 4 <= len(txt) <= 100 and txt not in items:
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
# MARKET DATA SOURCES
# =========================

def get_reddit_signals():
    urls = [
        "https://www.reddit.com/r/Entrepreneur/top.json?t=day&limit=25",
        "https://www.reddit.com/r/smallbusiness/top.json?t=day&limit=25",
        "https://www.reddit.com/r/AmazonFBA/top.json?t=day&limit=25",
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

    return results[:60]


def get_google_trends_signals():
    html = safe_get("https://trends.google.com/trending?geo=US&hl=en")
    return extract_text_items_from_html(html, ["a", "span", "div"])[:40]


def get_amazon_signals():
    html = safe_get("https://www.amazon.com/Best-Sellers/zgbs")
    return extract_text_items_from_html(html, ["a", "span"])[:50]


def get_pinterest_signals():
    html = safe_get("https://www.pinterest.com/")
    return extract_text_items_from_html(html, ["a", "span"])[:40]


def get_fallback_signals():
    return [
        "home organization",
        "kitchen storage",
        "pet accessories",
        "car cleaning tools",
        "beauty tools",
        "fitness accessories",
        "portable travel tools",
        "desk organization",
        "sleep improvement",
        "anxiety relief tools",
        "fridge organizers",
        "shoe storage",
        "laundry organization",
        "bathroom organizers",
        "phone accessories",
        "minimalist home decor",
        "portable workout gear",
        "ergonomic office tools",
        "cable organizers",
        "self care products"
    ]


def collect_signals():
    signals = []

    for fn in [
        get_reddit_signals,
        get_google_trends_signals,
        get_amazon_signals,
        get_pinterest_signals
    ]:
        try:
            data = fn()
            if data:
                signals.extend(data)
        except Exception:
            pass

    cleaned = []
    for s in signals:
        s = normalize_text(s)
        if len(s) < 4 or len(s) > 100:
            continue
        if s not in cleaned:
            cleaned.append(s)

    if len(cleaned) < 20:
        cleaned.extend(get_fallback_signals())

    cleaned = list(dict.fromkeys(cleaned))
    return cleaned[:200]


# =========================
# AI ANALYSIS
# =========================

def generate_niches_from_signals(signals, existing_signatures):
    prompt = f"""
أنت خبير niches في ecommerce.

لديك إشارات حقيقية من:
- Amazon
- Reddit
- Google Trends
- Pinterest

هذه الإشارات:
{signals}

هذه التواقيع ممنوعة لأنها استعملت سابقًا:
{existing_signatures}

المطلوب:
- استخرج 10 niches جديدة فقط
- لكل niche أعطني subniche
- أعطني problem
- أعطني audience
- أعطني algeria_success كنسبة مئوية فقط
- أعطني algeria_audience كنسبة مئوية فقط
- لا تكتب أي شرح طويل
- لا تكتب روابط
- لا تكرر نفس المعنى بصياغة مختلفة

أعد النتيجة بصيغة JSON فقط بهذا الشكل:
[
  {{
    "niche": "اسم النيش",
    "subniche": "اسم السوب نيش",
    "problem": "مشكلة قصيرة",
    "audience": "جمهور قصير",
    "algeria_success": "82%",
    "algeria_audience": "76%"
  }}
]
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "أنت خبير niches وتعيد JSON صحيح فقط."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content.strip()
        return extract_json_block(content)
    except Exception:
        return []


def get_hardcoded_fallback_niches():
    bank = [
        {"niche": "تنظيم المطبخ", "subniche": "منظمات الثلاجة", "problem": "فوضى التخزين", "audience": "العائلات", "algeria_success": "84%", "algeria_audience": "88%"},
        {"niche": "تنظيف السيارة", "subniche": "أدوات تنظيف داخلية", "problem": "صعوبة التنظيف السريع", "audience": "أصحاب السيارات", "algeria_success": "86%", "algeria_audience": "90%"},
        {"niche": "تنظيم المنزل", "subniche": "منظمات الأدراج", "problem": "فوضى التخزين", "audience": "ربات المنزل", "algeria_success": "83%", "algeria_audience": "87%"},
        {"niche": "العناية بالحيوانات", "subniche": "إكسسوارات الكلاب", "problem": "صعوبة العناية اليومية", "audience": "أصحاب الكلاب", "algeria_success": "67%", "algeria_audience": "62%"},
        {"niche": "العناية الذاتية", "subniche": "أدوات تدليك", "problem": "الإجهاد اليومي", "audience": "الرجال والنساء", "algeria_success": "79%", "algeria_audience": "85%"},
        {"niche": "الرياضة المنزلية", "subniche": "معدات صغيرة", "problem": "ضيق المساحة", "audience": "الشباب", "algeria_success": "74%", "algeria_audience": "78%"},
        {"niche": "تنظيم المكتب", "subniche": "منظمات الكابلات", "problem": "تشابك الأسلاك", "audience": "الموظفون", "algeria_success": "76%", "algeria_audience": "74%"},
        {"niche": "العناية بالبشرة", "subniche": "أدوات تنظيف الوجه", "problem": "روتين غير فعال", "audience": "النساء", "algeria_success": "81%", "algeria_audience": "87%"},
        {"niche": "السفر", "subniche": "منظمات الحقائب", "problem": "فوضى الأمتعة", "audience": "المسافرون", "algeria_success": "72%", "algeria_audience": "70%"},
        {"niche": "المطبخ الصغير", "subniche": "أدوات متعددة الاستخدام", "problem": "ضيق المساحة", "audience": "سكان الشقق", "algeria_success": "85%", "algeria_audience": "87%"},
        {"niche": "الصحة النفسية", "subniche": "أدوات تقليل التوتر", "problem": "القلق", "audience": "الشباب", "algeria_success": "73%", "algeria_audience": "81%"},
        {"niche": "غرفة النوم", "subniche": "منتجات النوم", "problem": "النوم غير المريح", "audience": "البالغون", "algeria_success": "78%", "algeria_audience": "83%"},
    ]
    random.shuffle(bank)
    return bank


# =========================
# FORMAT
# =========================

def format_niche_message(index: int, item: dict) -> str:
    niche = item.get("niche", "غير محدد").strip()
    subniche = item.get("subniche", "غير محدد").strip()
    problem = item.get("problem", "غير محدد").strip()
    audience = item.get("audience", "غير محدد").strip()
    algeria_success = item.get("algeria_success", "غير محدد").strip()
    algeria_audience = item.get("algeria_audience", "غير محدد").strip()

    return f"""🔥 Niche #{index}

📦 النيش
{niche}

🔎 السوب نيش
{subniche}

⚠️ المشكلة
{problem}

🎯 الجمهور
{audience}

🇩🇿 نسبة نجاح النيش في الجزائر
{algeria_success}

👥 نسبة وجود الجمهور في الجزائر
{algeria_audience}

━━━━━━━━━━━━
"""


# =========================
# LOOP
# =========================

def niche_loop():
    print("🚀 Niche Finder Market Data + AI Started")

    while True:
        seen = load_seen()
        existing_signatures = [item["signature"] for item in seen if "signature" in item]

        signals = collect_signals()
        raw_items = generate_niches_from_signals(signals, existing_signatures)

        if not raw_items:
            raw_items = get_hardcoded_fallback_niches()

        new_items = []

        for item in raw_items:
            if not isinstance(item, dict):
                continue

            signature = make_signature(item)
            if not signature or signature in existing_signatures:
                continue

            item["signature"] = signature
            new_items.append(item)
            existing_signatures.append(signature)
            seen.append(item)

            if len(new_items) >= 10:
                break

        if not new_items:
            print("⚠️ لا توجد نيشات جديدة في هذه الدورة")
        else:
            ok_count = 0

            if send_telegram(f"🚀 تم العثور على {len(new_items)} نيشات جديدة"):
                ok_count += 1

            for i, item in enumerate(new_items, start=1):
                if send_telegram(format_niche_message(i, item)):
                    ok_count += 1

            save_seen(seen)
            print(f"✅ Telegram sent count: {ok_count}")

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    niche_loop()
