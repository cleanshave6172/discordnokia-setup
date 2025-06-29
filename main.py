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

# Setup async loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Load env vars
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "").split(",")
PROJECT_ID = os.getenv("TELERIVET_PROJECT_ID")
API_KEY = os.getenv("TELERIVET_API_KEY")

# Initialize Flask and Discord bot
app = Flask(__name__)
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# Number to Discord channel map
NUMBER_MAP = {
    "+911234567890": 123456789012345678,  # example number mapped to channel ID
}

# Discord → SMS reply map
context_map = {}

@app.route("/incoming", methods=["POST"])
def incoming_sms():
    try:
        data = request.get_json() or request.form.to_dict()
        print("Received data:", data)

        from_number = data.get("from", "").strip()
        content = data.get("content", "").strip()
        context = data.get("context")  # now optional

        if from_number not in ALLOWED_NUMBERS:
            return jsonify({"error": "unauthorized"}), 403

        # Map number to Discord channel
        channel_id = NUMBER_MAP.get(from_number)
        if not channel_id:
            return jsonify({"error": "unknown number"}), 400

        # Send message to Discord
        async def send_message():
            channel = client.get_channel(channel_id)
            if not channel:
                print("Invalid channel ID")
                return
            msg = await channel.send(f"📩 SMS from {from_number}:\n{content}")
            if context is not None:
                context_map[str(msg.id)] = from_number  # track for replies

        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(send_message()))
        return jsonify({"success": True}), 200

    except Exception as e:
        print("Error in /incoming:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/fetch", methods=["POST", "PUT"])
def fetch_sms():
    messages_to_send = []

    for msg_id, number in context_map.items():
        messages_to_send.append({
            "to": number,
            "message": f"Reply to Discord msg ID {msg_id}"
        })

    # Clear after sending
    context_map.clear()
    return jsonify(messages_to_send)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if str(message.channel.id) in context_map:
        to_number = context_map[str(message.channel.id)]
    else:
        # fallback based on prefix
        to_number = next((k for k, v in NUMBER_MAP.items() if v == message.channel.id), None)

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
        print("Sent SMS:", response.status_code, response.text)
    except Exception as e:
        print("Error sending SMS:", e)

def run_flask():
    app.run(host="0.0.0.0", port=5000)

# Run Flask and Discord bot
if __name__ == "__main__":
    Thread(target=run_flask).start()
    client.run(BOT_TOKEN)
