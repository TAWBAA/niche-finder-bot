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

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

SEEN_FILE = "seen_niches.json"
SLEEP_SECONDS = 3600  # كل ساعة

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
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
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": message[:4000]},
            timeout=20,
        )
        print("TELEGRAM STATUS:", r.status_code)
        print("TELEGRAM RESPONSE:", r.text[:500])

        data = r.json()
        return data.get("ok", False)

    except Exception as e:
        print("TELEGRAM ERROR:", str(e))
        return False


# =========================
# UTILITIES
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


def safe_get(url, headers=None, timeout=20):
    try:
        r = requests.get(url, headers=headers or HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception:
        return ""
    return ""


def safe_get_json(url, headers=None, timeout=20):
    try:
        r = requests.get(url, headers=headers or HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def extract_text_items_from_html(html, selectors):
    items = []
    if not html:
        return items

    soup = BeautifulSoup(html, "html.parser")

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
# SOURCES
# =========================

def get_reddit_signals():
    results = []

    urls = [
        "https://www.reddit.com/r/Entrepreneur/top.json?t=day&limit=25",
        "https://www.reddit.com/r/smallbusiness/top.json?t=day&limit=25",
        "https://www.reddit.com/r/AmazonFBA/top.json?t=day&limit=25",
        "https://www.reddit.com/r/SideProject/top.json?t=day&limit=25",
    ]

    for url in urls:
        data = safe_get_json(url, headers={"User-Agent": "Mozilla/5.0"})
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


def get_producthunt_signals():
    html = safe_get("https://www.producthunt.com/")
    return extract_text_items_from_html(html, ["a", "h3", "span"])[:40]


def get_google_trends_signals():
    html = safe_get("https://trends.google.com/trending?geo=US&hl=en")
    return extract_text_items_from_html(html, ["a", "span", "div"])[:40]


def get_pinterest_signals():
    html = safe_get("https://www.pinterest.com/")
    return extract_text_items_from_html(html, ["a", "span"])[:40]


def get_amazon_signals():
    html = safe_get("https://www.amazon.com/Best-Sellers/zgbs")
    return extract_text_items_from_html(html, ["a", "span"])[:50]


def get_alibaba_signals():
    html = safe_get("https://www.alibaba.com/")
    return extract_text_items_from_html(html, ["a", "span"])[:50]


def get_aliexpress_signals():
    html = safe_get("https://www.aliexpress.com/")
    return extract_text_items_from_html(html, ["a", "span"])[:50]


def get_temu_signals():
    html = safe_get("https://www.temu.com/")
    return extract_text_items_from_html(html, ["a", "span"])[:50]


def get_1688_signals():
    html = safe_get("https://www.1688.com/")
    return extract_text_items_from_html(html, ["a", "span"])[:50]


def get_wildberries_signals():
    html = safe_get("https://www.wildberries.ru/")
    return extract_text_items_from_html(html, ["a", "span"])[:50]


# =========================
# FALLBACKS
# =========================

def get_fallback_signals():
    return [
        "home organization",
        "kitchen storage",
        "pet accessories",
        "portable cleaning tools",
        "car interior cleaning",
        "self care tools",
        "beauty accessories",
        "fitness at home",
        "travel organizers",
        "desk organization",
        "baby travel accessories",
        "portable workout gear",
        "sleep improvement",
        "anxiety relief tools",
        "eco friendly home products",
        "compact kitchen tools",
        "small space storage",
        "minimalist home decor",
        "ergonomic office tools",
        "portable massage tools",
        "gardening starter kits",
        "smart home accessories",
        "lunch box organization",
        "fridge organizers",
        "makeup storage",
        "shoe storage",
        "laundry organization",
        "bathroom organizers",
        "phone accessories",
        "cable organizers",
    ]


def get_hardcoded_fallback_niches():
    bank = [
        {"niche": "تنظيم المنزل", "subniche": "منظمات الأدراج", "problem": "فوضى التخزين", "audience": "النساء وربات المنزل"},
        {"niche": "العناية بالحيوانات", "subniche": "إكسسوارات الكلاب", "problem": "صعوبة التنقل مع الحيوان", "audience": "أصحاب الكلاب"},
        {"niche": "تنظيف السيارة", "subniche": "مكانس محمولة", "problem": "اتساخ المقصورة", "audience": "أصحاب السيارات"},
        {"niche": "تنظيم المطبخ", "subniche": "علب تخزين الطعام", "problem": "فوضى الثلاجة", "audience": "العائلات"},
        {"niche": "العناية الذاتية", "subniche": "أدوات تدليك", "problem": "الإجهاد اليومي", "audience": "الرجال والنساء"},
        {"niche": "الرياضة المنزلية", "subniche": "معدات صغيرة", "problem": "ضيق المساحة", "audience": "الشباب"},
        {"niche": "السفر", "subniche": "منظمات الحقائب", "problem": "فوضى الأمتعة", "audience": "المسافرون"},
        {"niche": "تنظيم المكتب", "subniche": "منظمات الكابلات", "problem": "تشابك الأسلاك", "audience": "أصحاب المكاتب"},
        {"niche": "العناية بالبشرة", "subniche": "أدوات تنظيف الوجه", "problem": "روتين غير فعال", "audience": "النساء"},
        {"niche": "الطفل والأم", "subniche": "إكسسوارات السفر", "problem": "صعوبة التنقل مع الطفل", "audience": "الأمهات"},
        {"niche": "الحمام", "subniche": "منظمات المستحضرات", "problem": "فوضى المساحة", "audience": "النساء"},
        {"niche": "غرفة النوم", "subniche": "منتجات النوم", "problem": "النوم غير المريح", "audience": "البالغون"},
        {"niche": "تنظيم الأحذية", "subniche": "رفوف موفرة للمساحة", "problem": "تكدس الأحذية", "audience": "العائلات"},
        {"niche": "الحديقة المنزلية", "subniche": "أدوات الزراعة المبتدئة", "problem": "صعوبة البدء", "audience": "المبتدئون"},
        {"niche": "الإنتاجية", "subniche": "أدوات المكتب الذكية", "problem": "ضعف التركيز", "audience": "الطلاب والموظفون"},
        {"niche": "المطبخ الصغير", "subniche": "أدوات متعددة الاستخدام", "problem": "ضيق المساحة", "audience": "سكان الشقق"},
        {"niche": "العناية بالقطط", "subniche": "تنظيف صندوق الرمل", "problem": "الروائح", "audience": "أصحاب القطط"},
        {"niche": "التنظيف السريع", "subniche": "أدوات تنظيف محمولة", "problem": "ضيق الوقت", "audience": "العاملون"},
        {"niche": "ديكور بسيط", "subniche": "ديكور موفر للمساحة", "problem": "شكل غير مرتب", "audience": "سكان الشقق"},
        {"niche": "الصحة النفسية", "subniche": "أدوات تقليل التوتر", "problem": "القلق", "audience": "الشباب"},
    ]
    random.shuffle(bank)
    return bank


# =========================
# AI ORGANIZER
# =========================

def generate_niches_from_signals(signals, existing_signatures):
    prompt = f"""
أنت خبير اكتشاف niches في ecommerce.

لديك إشارات حقيقية مأخوذة من:
Amazon
Alibaba
AliExpress
Temu
1688
Wildberries
Google Trends
Reddit
Pinterest
Product Hunt

هذه الإشارات:
{signals}

هذه التواقيع ممنوعة لأنها استعملت سابقًا:
{existing_signatures}

المطلوب:
- استخرج 10 niches جديدة فقط
- لكل niche أعطني sub-niche
- أعطني المشكلة
- أعطني الجمهور
- لا تكتب روابط
- لا تكتب فقرات
- الجمل قصيرة جدًا
- لا تكرر نفس المعنى بصياغة مختلفة
- ركز على niches صالحة للتجارة الإلكترونية
- ركز على niches قابلة للبيع في السوق العربي أو الجزائري

أعد النتيجة بصيغة JSON فقط:
[
  {{
    "niche": "اسم النيش",
    "subniche": "اسم السوب نيش",
    "problem": "مشكلة قصيرة",
    "audience": "جمهور قصير"
  }}
]

لا تكتب أي شيء خارج JSON.
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
    except Exception:
        return []


# =========================
# SIGNAL COLLECTION
# =========================

def collect_signals():
    signals = []

    sources = [
        get_amazon_signals,
        get_alibaba_signals,
        get_aliexpress_signals,
        get_temu_signals,
        get_1688_signals,
        get_wildberries_signals,
        get_google_trends_signals,
        get_reddit_signals,
        get_pinterest_signals,
        get_producthunt_signals,
    ]

    for fn in sources:
        try:
            data = fn()
            if data:
                signals.extend(data)
        except Exception:
            pass

    cleaned = []
    for s in signals:
        s = normalize_text(s)
        if len(s) < 4:
            continue
        if len(s) > 100:
            continue
        if s not in cleaned:
            cleaned.append(s)

    if len(cleaned) < 20:
        cleaned.extend(get_fallback_signals())

    cleaned = list(dict.fromkeys(cleaned))
    return cleaned[:250]


# =========================
# FORMATTING
# =========================

def format_niche_message(index: int, item: dict) -> str:
    niche = item.get("niche", "غير محدد").strip()
    subniche = item.get("subniche", "غير محدد").strip()
    problem = item.get("problem", "غير محدد").strip()
    audience = item.get("audience", "غير محدد").strip()

    return (
        f"🔥 نيش #{index}\n\n"
        f"النيش: {niche}\n"
        f"السوب نيش: {subniche}\n"
        f"المشكلة: {problem}\n"
        f"الجمهور: {audience}"
    )


# =========================
# MAIN LOOP
# =========================

def niche_loop():
    print("🚀 Niche Finder Pro Started")

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
            if not signature:
                continue

            if signature in existing_signatures:
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
