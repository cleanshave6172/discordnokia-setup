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

# Setup
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "").split(",")
PROJECT_ID = os.getenv("TELERIVET_PROJECT_ID")
API_KEY = os.getenv("TELERIVET_API_KEY")
DISCORD_CHANNEL_PREFIXES = json.loads(os.getenv("CHANNEL_PREFIXES", "{}"))

# Discord Client
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# Flask App
app = Flask(__name__)
app.config["DEBUG"] = True  # Show detailed errors in logs

# Discord Ready
@client.event
async def on_ready():
    print(f"✅ Discord bot logged in as {client.user}")

# Discord Message Listener
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    for prefix, number in DISCORD_CHANNEL_PREFIXES.items():
        if message.channel.name.startswith(prefix):
            if number in ALLOWED_NUMBERS:
                send_sms(number, f"{message.author.name}: {message.content}")
                print(f"✅ Sent to {number}: {message.content}")
            break

# SMS sending
def send_sms(phone_number, message):
    if not PROJECT_ID or not API_KEY:
        print("❌ Telerivet config missing.")
        return

    url = f"https://api.telerivet.com/v1/projects/{PROJECT_ID}/messages/send"
    headers = {"Content-Type": "application/json"}
    payload = {
        "content": message,
        "to_number": phone_number
    }

    response = requests.post(url, auth=(API_KEY, ''), headers=headers, json=payload)
    print(f"📤 SMS sent status: {response.status_code}, body: {response.text}")

# Webhook: SMS → Discord
@app.route('/incoming', methods=['POST'])
def incoming():
    try:
        data = request.form.to_dict() or request.get_json(silent=True) or {}
        print("📥 Incoming data:", data)

        phone = data.get("from_number")
        message = data.get("content")

        if phone not in ALLOWED_NUMBERS:
            return "Unauthorized", 403

        # Find correct channel
        matched_prefix = None
        for prefix, number in DISCORD_CHANNEL_PREFIXES.items():
            if number == phone:
                matched_prefix = prefix
                break

        if not matched_prefix:
            return "No channel match", 404

        channel = discord.utils.get(client.get_all_channels(), name=f"{matched_prefix}")
        if channel:
            loop.create_task(channel.send(f"📲 SMS from {phone}: {message}"))
            return "OK", 200
        else:
            print("❌ Channel not found for prefix", matched_prefix)
            return "Channel not found", 404

    except Exception as e:
        print("❌ Exception in /incoming:", e)
        return "Internal Server Error", 500

# Optional: for SMSSync /fetch
@app.route('/fetch', methods=['GET', 'POST', 'PUT'])
def fetch_sms():
    try:
        return jsonify([]), 200  # SMSSync needs empty list if no message
    except Exception as e:
        print("❌ Exception in /fetch:", e)
        return "Internal Server Error", 500

# Prevent 500 on "/"
@app.route("/")
def home():
    return "✅ Discord SMS bridge is running", 200

# Flask in thread
def run_flask():
    app.run(host="0.0.0.0", port=5000)

# Start Flask server in thread
flask_thread = Thread(target=run_flask)
flask_thread.start()

# Run Discord bot
client.run(BOT_TOKEN)
