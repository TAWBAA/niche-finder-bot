import os
import json
import time
import requests
from dotenv import load_dotenv
from openai import OpenAI

# تحميل متغيرات البيئة
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

SEEN_FILE = "seen_niches.json"
STATE_FILE = "state.json"


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return []
    with open(SEEN_FILE, "r") as f:
        return json.load(f)


def save_seen(data):
    with open(SEEN_FILE, "w") as f:
        json.dump(data, f)


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"running": True}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message
    })


def generate_niche(existing):

    prompt = f"""
اعطني niche جديدة في التجارة الالكترونية.
لا تكرر هذه النيشات:

{existing}

اعطني niche واحدة فقط.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()


def niche_loop():

    print("🚀 Niche Finder Started")

    while True:

        seen = load_seen()

        niche = generate_niche(seen)

        if niche not in seen:

            send_telegram(f"🔥 نيش جديدة مكتشفة:\n\n{niche}")

            seen.append(niche)

            save_seen(seen)

        time.sleep(600)


if __name__ == "__main__":
    niche_loop()
