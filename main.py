import os
import json
import discord
import requests
import uuid
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import asyncio
from threading import Thread
import time

# Async event loop setup
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Load env vars
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "").split(",")
PROJECT_ID = os.getenv("TELERIVET_PROJECT_ID")
API_KEY = os.getenv("TELERIVET_API_KEY")
PHONE_ID = os.getenv("TELERIVET_PHONE_ID")
CHANNEL_MAP = json.loads(os.getenv("CHANNEL_MAP", "{}"))  # JSON string of {"prefix": "channel_id"}
NUMBER_MAP = json.loads(os.getenv("NUMBER_MAP", "{}"))    # JSON string of {"+911234567890": "prefix"}

# Discord client setup
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# Flask app
app = Flask(__name__)

# Handle incoming SMS
@app.route("/incoming", methods=["POST"])
def incoming():
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        print("Incoming SMS Data:", data)

        phone = data.get("from_number") or data.get("from")
        content = data.get("content") or data.get("message")

        if not phone or not content:
            return jsonify({"error": "Missing fields"}), 400

        if phone not in ALLOWED_NUMBERS:
            return jsonify({"error": "Unauthorized number"}), 403

        prefix = NUMBER_MAP.get(phone)
        if not prefix:
            return jsonify({"error": "Prefix not found"}), 400

        channel_id = CHANNEL_MAP.get(prefix)
        if not channel_id:
            return jsonify({"error": "Channel not mapped"}), 400

        channel = client.get_channel(int(channel_id))
        if not channel:
            return jsonify({"error": "Channel not found"}), 404

        asyncio.run_coroutine_threadsafe(channel.send(f"[{phone}]\n{content}"), loop)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("❌ Flask exception:", e)
        return jsonify({"error": str(e)}), 500

# SMSSync fetch endpoint
@app.route("/fetch", methods=["POST", "PUT"])
def fetch():
    try:
        # Pull from queue or however you're implementing outbound
        # For now, dummy message:
        return jsonify([{
            "to": "+911234567890",
            "message": "This is a test reply from Discord.",
            "uuid": str(uuid.uuid4())
        }]), 200
    except Exception as e:
        print("❌ Fetch error:", e)
        return jsonify([]), 200  # Return empty list on error

# Discord background task
@client.event
async def on_ready():
    print(f"✅ Discord bot logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Find matching prefix
    for prefix, channel_id in CHANNEL_MAP.items():
        if message.channel.id == int(channel_id):
            # Find matching number
            for number, num_prefix in NUMBER_MAP.items():
                if num_prefix == prefix:
                    send_sms(number, f"[{message.author.name}] {message.content}")
                    break

def send_sms(to_number, message):
    try:
        print(f"➡️ Sending SMS to {to_number}: {message}")
        url = f"https://api.telerivet.com/v1/projects/{PROJECT_ID}/messages/send"
        headers = {"Content-Type": "application/json"}
        payload = {
            "to_number": to_number,
            "content": message,
            "phone_id": PHONE_ID
        }
        response = requests.post(url, headers=headers, auth=(API_KEY, ""), json=payload)
        print("Telerivet response:", response.text)
    except Exception as e:
        print("❌ Error sending SMS:", e)

# Start Flask server in separate thread
def run_flask():
    app.run(host="0.0.0.0", port=5000)

flask_thread = Thread(target=run_flask)
flask_thread.start()

# Start Discord bot
client.run(BOT_TOKEN)
