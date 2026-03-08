import os
import json
import time
import re
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


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return []
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_seen(data):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message[:4000]
    })


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
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception:
        return ""
    return ""


def extract_text_items_from_html(html, selectors):
    items = []
    if not html:
        return items
    soup = BeautifulSoup(html, "html.parser")

    for selector in selectors:
        for el in soup.select(selector):
            txt = el.get_text(" ", strip=True)
            if txt and len(txt) > 3 and txt not in items:
                items.append(txt)

    return items


def get_amazon_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://www.amazon.com/Best-Sellers/zgbs", headers=headers)
    return extract_text_items_from_html(html, ["a", "span"])[:40]


def get_alibaba_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://www.alibaba.com/", headers=headers)
    return extract_text_items_from_html(html, ["a", "span"])[:40]


def get_aliexpress_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://www.aliexpress.com/", headers=headers)
    return extract_text_items_from_html(html, ["a", "span"])[:40]


def get_temu_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://www.temu.com/", headers=headers)
    return extract_text_items_from_html(html, ["a", "span"])[:40]


def get_1688_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://www.1688.com/", headers=headers)
    return extract_text_items_from_html(html, ["a", "span"])[:40]


def get_wildberries_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://www.wildberries.ru/", headers=headers)
    return extract_text_items_from_html(html, ["a", "span"])[:40]


def get_google_trends_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://trends.google.com/trends/trendingsearches/daily?geo=US", headers=headers)
    return extract_text_items_from_html(html, ["a", "span"])[:30]


def get_reddit_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://www.reddit.com/r/Entrepreneur/top/?t=day", headers=headers)
    return extract_text_items_from_html(html, ["h3", "a"])[:30]


def get_pinterest_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://www.pinterest.com/", headers=headers)
    return extract_text_items_from_html(html, ["a", "span"])[:30]


def get_producthunt_signals():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = safe_get("https://www.producthunt.com/", headers=headers)
    return extract_text_items_from_html(html, ["a", "span"])[:30]


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
            signals.extend(fn())
        except Exception:
            pass

    # تنظيف أولي
    cleaned = []
    for s in signals:
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) < 4:
            continue
        if len(s) > 120:
            continue
        if s not in cleaned:
            cleaned.append(s)

    return cleaned[:200]


def generate_niches_from_signals(signals, existing_signatures):
    prompt = f"""
أنت خبير اكتشاف niches في ecommerce.

لديك إشارات حقيقية من عدة مصادر:
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

وهذه النيشات/السوب نيشات الممنوعة لأنها استعملت سابقًا:
{existing_signatures}

المطلوب:
- استخرج 10 niches جديدة فقط
- لكل niche أعطني sub-niche
- أعطني المشكلة التي تحلها
- أعطني الجمهور المستهدف
- لا تكتب روابط
- لا تكتب فقرات
- لا تكتب شرحًا طويلًا
- الجمل قصيرة جدًا
- لا تكرر نفس المعنى بصياغة مختلفة
- ركز على niches مناسبة للتجارة الإلكترونية
- ركز على niches قابلة للعمل في السوق العربي أو الجزائري

أعد النتيجة بصيغة JSON فقط بهذا الشكل:
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

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "أنت خبير niches وتعيد JSON صحيح فقط."},
            {"role": "user", "content": prompt}
        ]
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except Exception:
        return []


def format_niche_message(index: int, item: dict) -> str:
    niche = item.get("niche", "غير محدد").strip()
    subniche = item.get("subniche", "غير محدد").strip()
    problem = item.get("problem", "غير محدد").strip()
    audience = item.get("audience", "غير محدد").strip()

    return (
        f"🔥 نيش جديدة #{index}\n\n"
        f"النيش: {niche}\n"
        f"السوب نيش: {subniche}\n"
        f"المشكلة: {problem}\n"
        f"الجمهور: {audience}"
    )


def niche_loop():
    print("🚀 Niche Finder Pro Started")

    while True:
        seen = load_seen()
        existing_signatures = [item["signature"] for item in seen if "signature" in item]

        signals = collect_signals()

        if not signals:
            print("⚠️ لم أتمكن من جمع إشارات كافية من المصادر")
            time.sleep(SLEEP_SECONDS)
            continue

        raw_items = generate_niches_from_signals(signals, existing_signatures)

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

        if new_items:
            send_telegram(f"🚀 تم العثور على {len(new_items)} نيشات جديدة")
            for i, item in enumerate(new_items[:10], start=1):
                send_telegram(format_niche_message(i, item))
            save_seen(seen)
            print(f"✅ Sent {len(new_items)} new niches")
        else:
            print("⚠️ لا توجد نيشات جديدة في هذه الدورة")

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    niche_loop()
