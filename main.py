import os
import time
import json
import random
import requests
from openai import OpenAI

# ==============================
# Variables
# ==============================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

SEEN_FILE = "seen_niches.json"

# ==============================
# Load seen niches
# ==============================

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# ==============================
# Telegram sender
# ==============================

def send_telegram(message):

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    r = requests.post(url, data=payload)
    print("TELEGRAM STATUS:", r.status_code)
    print("TELEGRAM RESPONSE:", r.text)

# ==============================
# AI niche generator
# ==============================

def generate_niches():

    prompt = """
Give me 20 ecommerce niches inspired from:

- Amazon trends
- TikTok viral products
- Reddit communities
- Google trends

Each niche must contain:

niche
subniche
problem
audience

Return JSON only.

Example:

[
{
"niche":"Pet Products",
"subniche":"Interactive Cat Toys",
"problem":"cats get bored indoors",
"audience":"cat owners"
}
]
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
        print("JSON error")
        return []

    return data

# ==============================
# Main loop
# ==============================

def run():

    print("🚀 Niche Finder Pro Started")

    seen = load_seen()

    niches = generate_niches()

    sent = 0

    for i, n in enumerate(niches):

        niche = n["niche"]
        subniche = n["subniche"]
        problem = n["problem"]
        audience = n["audience"]

        key = niche + subniche

        if key in seen:
            continue

        message = f"""
🔥 Niche #{i}

📦 النيش
{niche}

🔎 السوب نيش
{subniche}

⚠️ المشكلة
{problem}

🎯 الجمهور
{audience}

━━━━━━━━━━━━
"""

        send_telegram(message)

        seen.add(key)

        sent += 1

        if sent >= 10:
            break

    save_seen(seen)

    print("✅ Telegram sent count:", sent)


# ==============================
# LOOP
# ==============================

while True:

    try:

        run()

    except Exception as e:

        print("ERROR:", e)

    time.sleep(3600)
