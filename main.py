import os
import json
import discord
import requests
import uuid
import traceback
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import asyncio
from threading import Thread
import time

# Set up async loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "").split(",")
PROJECT_ID = os.getenv("TELERIVET_PROJECT_ID")
API_KEY = os.getenv("TELERIVET_API_KEY")

# Flask app and Discord bot
app = Flask(__name__)
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# Number-to-channel mapping
NUMBER_MAP = {
    "+911234567890": 123456789012345678,  # Replace with actual values
}

# Context tracking map
context_map = {}

@app.route("/incoming", methods=["POST"])
def incoming_sms():
    try:
        # Parse incoming JSON or form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        print("📥 Incoming data:", data)

        from_number = data.get("from") or data.get("phone_number") or ""
        content = data.get("content") or data.get("message") or ""
        context = data.get("context", None)

        from_number = from_number.strip()
        content = content.strip()

        if not from_number or not content:
            return jsonify({"error": "Missing 'from' or 'content'"}), 400

        if from_number not in ALLOWED_NUMBERS:
            return jsonify({"error": "unauthorized"}), 403

        channel_id = NUMBER_MAP.get(from_number)
        if not channel_id:
            return jsonify({"error": "unknown number"}), 400

        async def send_to_discord():
            channel = client.get_channel(channel_id)
            if channel:
                msg = await channel.send(f"📩 SMS from {from_number}:\n{content}")
                if context:
                    context_map[str(msg.id)] = from_number
            else:
                print("❌ Channel not found for ID:", channel_id)

        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(send_to_discord()))
        return jsonify({"success": True}), 200

    except Exception as e:
        print("❗ Exception in /incoming")
        traceback.print_exc()
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

@app.route("/fetch", methods=["POST", "PUT"])
def fetch_sms():
    messages_to_send = []

    for msg_id, number in context_map.items():
        messages_to_send.append({
            "to": number,
            "message": f"Reply to Discord msg ID {msg_id}"
        })

    context_map.clear()
    return jsonify(messages_to_send)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    to_number = None
    if str(message.channel.id) in context_map:
        to_number = context_map[str(message.channel.id)]
    else:
        # Fallback to NUMBER_MAP
        for number, chan_id in NUMBER_MAP.items():
            if chan_id == message.channel.id:
                to_number = number
                break

    if not to_number:
        return

    payload = {
        "to_number": to_number,
        "content": f"{message.author.name}: {message.content}"
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {API_KEY}"
    }

    try:
        response = requests.post(
            f"https://api.telerivet.com/v1/projects/{PROJECT_ID}/messages/send",
            headers=headers,
            data=json.dumps(payload)
        )
        print("📤 Sent SMS:", response.status_code, response.text)
    except Exception as e:
        print("❗ Error sending SMS:", e)

def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    client.run(BOT_TOKEN)
