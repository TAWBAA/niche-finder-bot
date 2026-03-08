import os
import re
import json
import time
import random
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
    text = text.strip().lower()
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

    for old in existing_items:
        old_niche = old.get("niche", "")
        old_sub = old.get("subniche", "")
        old_micro = old.get("microniche", "")
        old_combo = f"{old_niche} | {old_sub} | {old_micro}"

        # تطابق حرفي
        if normalize_text(current_combo) == normalize_text(old_combo):
            return True

        # تشابه عالٍ
        if text_similarity(current_combo, old_combo) >= 0.86:
            return True

        # تشابه niche + subniche
        current_ns = f"{current_niche} | {current_sub}"
        old_ns = f"{old_niche} | {old_sub}"
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
        "self care products",
    ]


def collect_signals():
    signals = []

    for fn in [
        get_reddit_signals,
        get_google_trends_signals,
        get_amazon_signals,
        get_pinterest_signals,
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

هذه التواقيع القديمة المستعملة:
{existing_signatures}

المطلوب:
- استخرج 15 niches جديدة فقط
- لكل niche أعطني:
  1) niche
  2) subniche
  3) microniche
  4) problem
  5) audience
  6) algeria_success كنسبة مئوية فقط
  7) algeria_audience كنسبة مئوية فقط
- microniche يجب أن يكون دقيقًا جدًا وليس عامًا
- لا تكرر نفس المعنى بصياغة مختلفة
- لا تكتب روابط
- لا تكتب شرحًا طويلًا
- النيشات يجب أن تكون مناسبة للإيكومرس
- النيشات يجب أن تكون قابلة للبيع في الجزائر

أعد النتيجة بصيغة JSON فقط بهذا الشكل:
[
  {{
    "niche": "اسم النيش",
    "subniche": "اسم السوب نيش",
    "microniche": "اسم المايكرو نيش",
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
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content.strip()
        return extract_json_block(content)
    except Exception as e:
        print("AI ERROR:", str(e))
        return []


def get_hardcoded_fallback_niches():
    bank = [
        {
            "niche": "العناية بالقطط",
            "subniche": "تنظيف صندوق الرمل",
            "microniche": "portable cat litter cleaner",
            "problem": "صعوبة تنظيف صندوق الرمل بسرعة",
            "audience": "مالكو القطط",
            "algeria_success": "71%",
            "algeria_audience": "64%",
        },
        {
            "niche": "تنظيف السيارة",
            "subniche": "تنظيف المقصورة",
            "microniche": "mini handheld car vacuum",
            "problem": "اتساخ السيارة من الداخل",
            "audience": "أصحاب السيارات",
            "algeria_success": "86%",
            "algeria_audience": "90%",
        },
        {
            "niche": "تنظيم المطبخ",
            "subniche": "تخزين الثلاجة",
            "microniche": "stackable fridge organizer bins",
            "problem": "فوضى الثلاجة",
            "audience": "العائلات",
            "algeria_success": "84%",
            "algeria_audience": "88%",
        },
        {
            "niche": "تنظيم المنزل",
            "subniche": "منظمات الأدراج",
            "microniche": "adjustable drawer divider set",
            "problem": "فوضى الأدراج",
            "audience": "ربات المنزل",
            "algeria_success": "83%",
            "algeria_audience": "87%",
        },
        {
            "niche": "العناية بالحيوانات",
            "subniche": "إكسسوارات الكلاب",
            "microniche": "portable dog water bottle",
            "problem": "صعوبة سقي الكلب خارج البيت",
            "audience": "أصحاب الكلاب",
            "algeria_success": "68%",
            "algeria_audience": "62%",
        },
        {
            "niche": "العناية الذاتية",
            "subniche": "الاسترخاء المنزلي",
            "microniche": "portable neck massager",
            "problem": "التوتر وآلام الرقبة",
            "audience": "الرجال والنساء",
            "algeria_success": "79%",
            "algeria_audience": "85%",
        },
        {
            "niche": "الرياضة المنزلية",
            "subniche": "معدات صغيرة",
            "microniche": "door resistance band anchor set",
            "problem": "ضيق المساحة للتمرين",
            "audience": "الشباب",
            "algeria_success": "74%",
            "algeria_audience": "78%",
        },
        {
            "niche": "تنظيم المكتب",
            "subniche": "إدارة الأسلاك",
            "microniche": "magnetic desk cable clip holder",
            "problem": "تشابك الكابلات",
            "audience": "الموظفون والطلاب",
            "algeria_success": "76%",
            "algeria_audience": "74%",
        },
        {
            "niche": "العناية بالبشرة",
            "subniche": "تنظيف الوجه",
            "microniche": "silicone facial cleansing brush",
            "problem": "تنظيف غير فعال للبشرة",
            "audience": "النساء",
            "algeria_success": "81%",
            "algeria_audience": "87%",
        },
        {
            "niche": "السفر",
            "subniche": "تنظيم الحقائب",
            "microniche": "compression packing cubes set",
            "problem": "فوضى الأمتعة",
            "audience": "المسافرون",
            "algeria_success": "72%",
            "algeria_audience": "70%",
        },
        {
            "niche": "المطبخ الصغير",
            "subniche": "أدوات متعددة الاستخدام",
            "microniche": "over sink foldable drying rack",
            "problem": "قلة المساحة في المطبخ",
            "audience": "سكان الشقق",
            "algeria_success": "85%",
            "algeria_audience": "87%",
        },
        {
            "niche": "الصحة النفسية",
            "subniche": "تقليل التوتر",
            "microniche": "guided breathing relaxation device",
            "problem": "القلق والتوتر",
            "audience": "الشباب",
            "algeria_success": "73%",
            "algeria_audience": "81%",
        },
    ]
    random.shuffle(bank)
    return bank


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

━━━━━━━━━━━━
"""


# =========================
# MAIN LOOP
# =========================

def niche_loop():
    print("🚀 Niche Finder Market Data + AI + Micro Started")

    while True:
        seen = load_seen()
        existing_signatures = [item.get("signature", "") for item in seen if isinstance(item, dict)]

        signals = collect_signals()
        print("SIGNALS COUNT:", len(signals))
        print("SIGNALS SAMPLE:", signals[:10])

        raw_items = generate_niches_from_signals(signals, existing_signatures)

        if not raw_items:
            raw_items = get_hardcoded_fallback_niches()

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
