import os
import time
import json
import requests
from openai import OpenAI

# =============================
# ENV VARIABLES
# =============================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

SEEN_FILE = "seen_niches.json"


# =============================
# LOAD SEEN NICHES
# =============================

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


# =============================
# TELEGRAM
# =============================

def send_telegram(message):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    r = requests.post(url, data=payload)

    print("TELEGRAM STATUS:", r.status_code)


# =============================
# AI NICHE GENERATION
# =============================

def generate_niches():

    prompt = """
Generate 20 ecommerce niches inspired by:

Amazon trends
TikTok viral products
Reddit communities
Google trends

Return JSON only.

Format:

[
{
"niche":"",
"subniche":"",
"problem":"",
"audience":"",
"algeria_success":"",
"algeria_audience":""
}
]

Rules:

- algeria_success = percentage probability niche works in Algeria
- algeria_audience = percentage size of audience in Algeria
- percentages between 50 and 95
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    text = response.choices[0].message.content

    try:
        data = json.loads(text)
    except:
        print("JSON ERROR")
        return []

    return data


# =============================
# RUN
# =============================

def run():

    print("🚀 Niche Finder Started")

    seen = load_seen()

    niches = generate_niches()

    sent = 0

    for i, n in enumerate(niches):

        niche = n["niche"]
        subniche = n["subniche"]
        problem = n["problem"]
        audience = n["audience"]
        algeria_success = n["algeria_success"]
        algeria_audience = n["algeria_audience"]

        key = niche + subniche

        if key in seen:
            continue

        message = f"""
🔥 Niche #{i+1}

📦 النيش
{niche}

🔎 السوب نيش
{subniche}

⚠️ المشكلة
{problem}

🎯 الجمهور
{audience}

🇩🇿 نسبة نجاح النيش في الجزائر
{algeria_success}%

👥 نسبة وجود الجمهور في الجزائر
{algeria_audience}%

━━━━━━━━━━━━
"""

        send_telegram(message)

        seen.add(key)

        sent += 1

        if sent >= 10:
            break

    save_seen(seen)

    print("Sent:", sent)


# =============================
# LOOP
# =============================

while True:

    try:
        run()

    except Exception as e:
        print("ERROR:", e)

    time.sleep(3600)
