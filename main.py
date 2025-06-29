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
import traceback

# Set up async loop for Discord bot
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Load env vars
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "").split(",")
NUMBER_MAP = json.loads(os.getenv("NUMBER_MAP", "{}"))  # {"abdu": "1234", "essa": "5678"}

intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running", 200

@app.route("/incoming", methods=["POST"])
def incoming_sms():
    if not request.is_json:
        return jsonify({"error": "Invalid Content-Type. Expected application/json"}), 415

    data = request.get_json()

    try:
        from_number = data.get("from_number", "").strip()
        content = data.get("content", "").strip()

        if from_number not in ALLOWED_NUMBERS:
            return jsonify({"error": "unauthorized number"}), 403

        if not content:
            return jsonify({"error": "empty content"}), 400

        prefix = content.split()[0].lower()
        message = " ".join(content.split()[1:])

        channel_id = NUMBER_MAP.get(prefix)

        if not channel_id:
            return jsonify({"error": f"prefix '{prefix}' not found"}), 400

        async def send_message():
            channel = client.get_channel(int(channel_id))
            if channel:
                await channel.send(message)
                print(f"[DISCORD] Sent to {channel_id}: {message}")
            else:
                print(f"[ERROR] Channel {channel_id} not found.")

        loop.create_task(send_message())
        return jsonify({"success": True}), 200

    except Exception as e:
        print("Exception in /incoming route:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Discord bot startup
@client.event
async def on_ready():
    print(f"Logged in as {client.user}!")

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)

# Start both Flask and Discord
if __name__ == "__main__":
    Thread(target=run_flask).start()
    loop.run_until_complete(client.start(BOT_TOKEN))
