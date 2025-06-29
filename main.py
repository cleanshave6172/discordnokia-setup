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

# Set up the asyncio event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "").split(",")
PROJECT_ID = os.getenv("TELERIVET_PROJECT_ID")
API_KEY = os.getenv("TELERIVET_API_KEY")
TELERIVET_URL = f"https://api.telerivet.com/v1/projects/{PROJECT_ID}/messages/send"

# Set up Flask app and Discord client
app = Flask(__name__)
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# Prefix mapping and active message tracking
prefix_map = {}
active_messages = {}

@app.route('/incoming', methods=['POST'])
def incoming_sms():
    data = request.form if request.form else request.get_json()
    number = data.get("from_number")
    content = data.get("content")

    if number not in ALLOWED_NUMBERS:
        return jsonify({"error": "unauthorized"}), 403

    if content and ":" in content:
        prefix, msg = content.split(":", 1)
        prefix = prefix.strip().lower()
        msg = msg.strip()

        channel_id = prefix_map.get(prefix)
        if channel_id:
            future = asyncio.run_coroutine_threadsafe(send_to_discord(channel_id, msg), loop)
            message = future.result()
            active_messages[number] = (prefix, message.id)
            return jsonify({"status": "sent"}), 200
        else:
            return jsonify({"error": "unknown prefix"}), 400
    else:
        # Reply to last used channel
        if number in active_messages:
            prefix, last_message_id = active_messages[number]
            channel_id = prefix_map.get(prefix)
            if channel_id:
                reply = f"Reply from {number}: {content}"
                future = asyncio.run_coroutine_threadsafe(send_to_discord(channel_id, reply), loop)
                future.result()
                return jsonify({"status": "sent"}), 200
        return jsonify({"error": "no context"}), 400

async def send_to_discord(channel_id, content):
    channel = client.get_channel(int(channel_id))
    if channel:
        return await channel.send(content)
    return None

def send_sms(number, message):
    payload = {
        "to_number": number,
        "content": message
    }
    response = requests.post(TELERIVET_URL, auth=(API_KEY, ''), json=payload)
    return response.status_code == 200

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user or not message.guild:
        return

    for prefix, channel_id in prefix_map.items():
        if int(channel_id) == message.channel.id:
            for number in ALLOWED_NUMBERS:
                send_sms(number, f"{prefix}: {message.content}")
            break

# Run Discord bot in separate thread
def run_discord_bot():
    client.run(BOT_TOKEN)

discord_thread = Thread(target=run_discord_bot)
discord_thread.start()

# Run Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
