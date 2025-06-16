import os
import json
import discord
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import asyncio
from threading import Thread
from collections import deque

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Load env vars
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "").split(",")

# Safe-load mapping for target names or IDs
try:
    NUMBER_MAP = json.loads(os.getenv("NUMBER_MAP", "{}"))
except Exception as e:
    print(f"❌ Invalid NUMBER_MAP: {e}")
    NUMBER_MAP = {}

# Target phone for SMS delivery (Nokia)
TARGET_PHONE_NUMBER = os.getenv("TARGET_PHONE_NUMBER")

# Flask app
app = Flask(__name__)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
client = discord.Client(intents=intents)
discord_ready = asyncio.Event()

# Outgoing message queue for SMSSync
outgoing_sms_queue = deque()

# Discord events
@client.event
async def on_ready():
    print(f"✅ Discord bot logged in as {client.user}")
    discord_ready.set()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Compose message
    if isinstance(message.channel, discord.DMChannel):
        content = f"[DM] {message.author.name}: {message.content}"
    else:
        content = f"[#{message.channel.name}] {message.author.name}: {message.content}"

    if TARGET_PHONE_NUMBER:
        print(f"📥 Queuing SMS to {TARGET_PHONE_NUMBER}: {content}")
        outgoing_sms_queue.append({
            "to": TARGET_PHONE_NUMBER,
            "message": content
        })
    else:
        print("❌ TARGET_PHONE_NUMBER not set.")

# Incoming webhook from SMSSync (POST only)
@app.route("/incoming", methods=["POST"])
def incoming():
    print("Headers:", request.headers)
    print("Body:", request.form)
    return receive_sms()

def receive_sms():
    data = request.form
    from_number = data.get("from")
    content = data.get("message")

    if not from_number or not content:
        return ("Missing required fields", 400)

    if from_number not in ALLOWED_NUMBERS:
        return ("Forbidden", 403)

    if " " not in content:
        return ("Invalid format. Use: target message", 400)

    target, msg = content.split(" ", 1)
    target = target.lstrip("@")
    resolved = NUMBER_MAP.get(target, target)

    asyncio.run_coroutine_threadsafe(send_to_discord(resolved, msg), client.loop)

    return ("Message accepted", 200)

# SMSSync fetches messages to send to Nokia
@app.route("/fetch", methods=["GET", "POST"])
def fetch_messages():
    if not outgoing_sms_queue:
        return jsonify({"payload": {"success": True, "task": []}})

    messages = list(outgoing_sms_queue)
    outgoing_sms_queue.clear()

    print(f"📤 Serving {len(messages)} SMS messages to SMSSync.")
    return jsonify({"payload": {"success": True, "task": messages}})

# Send message to Discord from SMS
async def send_to_discord(resolved, msg):
    await discord_ready.wait()
    try:
        if resolved.isdigit():
            channel = client.get_channel(int(resolved))
            if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                await channel.send(msg)
                print(f"📤 Sent to channel #{channel.name} (ID: {resolved})")
                return

            user = await client.fetch_user(int(resolved))
            await user.send(msg)
            print(f"📤 Sent DM to user {user.name} (ID: {resolved})")
            return
        else:
            for guild in client.guilds:
                channel = discord.utils.get(guild.channels, name=resolved)
                if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                    await channel.send(msg)
                    print(f"📤 Sent to channel #{channel.name} (by name)")
                    return

        print(f"❌ Could not find channel or user: {resolved}")

    except Exception as e:
        print(f"❌ Error sending to Discord: {e}")

# Start Flask in thread
def start_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    Thread(target=start_flask).start()
    client.run(BOT_TOKEN)
