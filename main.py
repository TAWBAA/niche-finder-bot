import os
import re
import json
import time
import random
import hashlib
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

SEEN_FILE = "seen_niches.json"
CHECK_INTERVAL_SECONDS = 3600   # كل ساعة
NICHES_PER_CYCLE = 3

# 80% Physical / 20% Digital
PHYSICAL_NICHES = [
    "pet accessories",
    "cat toys",
    "dog grooming tools",
    "kitchen gadgets",
    "kitchen storage",
    "food containers",
    "car accessories",
    "car cleaning tools",
    "car organizers",
    "beauty tools",
    "skin care devices",
    "hair styling tools",
    "home organization",
    "drawer organizers",
    "closet storage",
    "fitness equipment",
    "home workout tools",
    "resistance bands",
    "baby products",
    "baby safety products",
    "baby feeding tools",
    "camping gear",
    "travel accessories",
    "outdoor gadgets",
    "phone accessories",
    "charging gadgets",
    "desk gadgets",
    "fridge organizers",
    "portable cleaning tools",
    "travel comfort products"
]

DIGITAL_NICHES = [
    "productivity apps",
    "ai tools",
    "online courses",
    "digital planners",
    "notion templates",
    "study apps",
    "automation tools"
]


# =========================
# FILES
# =========================

def ensure_seen_file():
    if not os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump({"hashes": []}, f, ensure_ascii=False, indent=2)


def load_seen():
    ensure_seen_file()
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {"hashes": []}
            data = json.loads(content)
            if not isinstance(data, dict):
                return {"hashes": []}
            data.setdefault("hashes", [])
            return data
    except Exception:
        return {"hashes": []}


def save_seen(data):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def niche_hash(item: dict) -> str:
    key = f"{item.get('niche','')}|{item.get('sub_niche','')}|{item.get('problem','')}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


# =========================
# TELEGRAM
# =========================

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message[:4000]
    }

    try:
        response = requests.post(url, data=payload, timeout=30)
        print("TELEGRAM RESPONSE:", response.text)
    except Exception as e:
        print("TELEGRAM ERROR:", e)


# =========================
# NICHE PICKING
# =========================

def pick_base_niche():
    if random.random() < 0.8:
        return random.choice(PHYSICAL_NICHES), "physical"
    return random.choice(DIGITAL_NICHES), "digital"


def pick_niche_mix(count=3):
    picked = []
    used = set()

    while len(picked) < count:
        base_niche, niche_type = pick_base_niche()
        if base_niche in used:
            continue
        used.add(base_niche)
        picked.append({"base_niche": base_niche, "type": niche_type})

    return picked


# =========================
# AI GENERATION
# =========================

def generate_niches():
    niche_inputs = pick_niche_mix(NICHES_PER_CYCLE)

    prompt = f"""
أنت خبير Product Research و Niche Research للسوق الجزائري.

المطلوب:
بناء {NICHES_PER_CYCLE} niches قوية فقط.

قواعد مهمة جدًا:
- 80% تقريبًا من النيشات يجب أن تكون Physical products
- 20% تقريبًا يمكن أن تكون Digital niches
- لا تعطيني niches عامة وضعيفة
- ركز على niches قابلة للبيع أو قابلة للتحول إلى منتجات رابحة
- السوق الأساسي: الجزائر
- أعد فقط JSON
- لا تكتب أي شيء خارج JSON

الـ base niches المختارة لهذه الدورة:
{json.dumps(niche_inputs, ensure_ascii=False, indent=2)}

أعد JSON بهذا الشكل بالضبط:
[
  {{
    "niche": "اسم النيش",
    "sub_niche": "اسم السوب نيش",
    "problem": "المشكلة الرئيسية",
    "audience": "الجمهور",
    "success_rate_algeria": "78%",
    "audience_presence_algeria": "72%",
    "market_signal_strength": "مرتفعة",
    "type": "physical"
  }},
  {{
    "niche": "اسم النيش",
    "sub_niche": "اسم السوب نيش",
    "problem": "المشكلة الرئيسية",
    "audience": "الجمهور",
    "success_rate_algeria": "65%",
    "audience_presence_algeria": "58%",
    "market_signal_strength": "متوسطة",
    "type": "digital"
  }}
]

قواعد إضافية:
- success_rate_algeria يجب أن تكون نسبة بين 55% و 90%
- audience_presence_algeria يجب أن تكون نسبة بين 45% و 90%
- market_signal_strength فقط أحد هذه القيم:
  مرتفعة
  متوسطة
  منخفضة
- type فقط:
  physical
  digital
- لا تكرر niches
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "أنت خبير niche research وتعيد JSON فقط."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=1200
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except Exception:
        print("RAW AI OUTPUT:")
        print(content)
        return []


# =========================
# CLEANING / FILTERING
# =========================

def is_valid_percentage(text: str) -> bool:
    return bool(re.match(r"^\d{1,3}%$", str(text).strip()))


def valid_signal(value: str) -> bool:
    return value in ["مرتفعة", "متوسطة", "منخفضة"]


def clean_and_filter(items):
    cleaned = []

    for item in items:
        if not isinstance(item, dict):
            continue

        niche = str(item.get("niche", "")).strip()
        sub_niche = str(item.get("sub_niche", "")).strip()
        problem = str(item.get("problem", "")).strip()
        audience = str(item.get("audience", "")).strip()
        success = str(item.get("success_rate_algeria", "")).strip()
        presence = str(item.get("audience_presence_algeria", "")).strip()
        signal = str(item.get("market_signal_strength", "")).strip()
        niche_type = str(item.get("type", "")).strip().lower()

        if not niche or not sub_niche or not problem or not audience:
            continue

        if niche_type not in ["physical", "digital"]:
            continue

        if not is_valid_percentage(success):
            continue

        if not is_valid_percentage(presence):
            continue

        if not valid_signal(signal):
            continue

        cleaned.append({
            "niche": niche,
            "sub_niche": sub_niche,
            "problem": problem,
            "audience": audience,
            "success_rate_algeria": success,
            "audience_presence_algeria": presence,
            "market_signal_strength": signal,
            "type": niche_type
        })

    return cleaned[:NICHES_PER_CYCLE]


def remove_duplicates(items, seen_hashes):
    final_items = []

    for item in items:
        h = niche_hash(item)
        if h in seen_hashes:
            continue
        item["_hash"] = h
        final_items.append(item)

    return final_items


# =========================
# FORMAT
# =========================

def format_niche_message(index: int, item: dict) -> str:
    icon = "📦" if item["type"] == "physical" else "💻"

    return f"""🔥 Niche #{index}

{icon} النيش
{item['niche']}

🔎 السوب نيش
{item['sub_niche']}

⚠️ المشكلة
{item['problem']}

🎯 الجمهور
{item['audience']}

🇩🇿 نسبة نجاح النيش في الجزائر
{item['success_rate_algeria']}

👥 نسبة وجود الجمهور في الجزائر
{item['audience_presence_algeria']}

📊 قوة الإشارة السوقية
{item['market_signal_strength']}

━━━━━━━━━━━━
"""


# =========================
# MAIN LOOP
# =========================

def main():
    print("Niche Finder Bot Started")

    while True:
        try:
            seen = load_seen()
            seen_hashes = seen.get("hashes", [])

            items = generate_niches()
            items = clean_and_filter(items)
            items = remove_duplicates(items, seen_hashes)

            if not items:
                print("No new valid niches found in this cycle")
            else:
                intro = f"🚀 تم العثور على {len(items)} niches قوية جديدة"
                send_telegram(intro)

                for i, item in enumerate(items, start=1):
                    message = format_niche_message(i, item)
                    send_telegram(message)
                    seen_hashes.append(item["_hash"])

                seen["hashes"] = seen_hashes[-500:]
                save_seen(seen)

        except Exception as e:
            print("MAIN LOOP ERROR:", e)

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
