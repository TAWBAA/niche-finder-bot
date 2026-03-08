import os
import json
import time
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
SLEEP_SECONDS = 3600


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return []
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []


def save_seen(data):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text[:4000]})
    except:
        pass


def collect_signals():
    fallback = [
        "home organization",
        "kitchen gadgets",
        "pet accessories",
        "car cleaning tools",
        "beauty tools",
        "fitness accessories",
        "smart home gadgets",
        "portable travel tools",
        "eco friendly products",
        "self care products",
        "baby travel accessories",
        "desk organization tools",
        "minimalist home decor",
        "ergonomic office tools",
        "portable workout gear",
        "sleep improvement products",
        "anxiety relief tools",
        "gardening starter kits",
        "digital detox tools",
        "productivity gadgets"
    ]

    return fallback


def generate_niches(signals):

    prompt = f"""
استخرج 10 niches جديدة للتجارة الالكترونية من هذه الاشارات:

{signals}

اريد:
niche
subniche
problem
audience

اكتب JSON فقط
"""

    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "انت خبير niches"},
            {"role": "user", "content": prompt}
        ]
    )

    try:
        return json.loads(r.choices[0].message.content)
    except:
        return []


def format_msg(n):

    return f"""
🔥 niche

niche: {n.get("niche")}
subniche: {n.get("subniche")}
problem: {n.get("problem")}
audience: {n.get("audience")}
"""


def niche_loop():

    print("🚀 Niche Finder Pro Started")

    while True:

        signals = collect_signals()

        niches = generate_niches(signals)

        if niches:

            send_telegram(f"🔥 {len(niches)} niches جديدة")

            for n in niches[:10]:
                send_telegram(format_msg(n))

        else:

            print("⚠️ لا توجد نيشات")

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    niche_loop()
