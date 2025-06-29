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

# Set up asyncio loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "").split(",")
PROJECT_ID = os.getenv("TELERIVET_PROJECT_ID")
API_KEY = os.getenv("TELERIVET_API_KEY")
PHONE_ID = os.getenv("TELERIVET_PHONE_ID")
TARGET_PHONE_NUMBER = os.getenv("TARGET_PHONE_NUMBER")

# Validate critical env vars
required_envs = {
    "BOT_TOKEN": BOT_TOKEN,
    "PROJECT_ID": PROJECT_ID,
    "API_KEY": API_KEY,
    "PHONE_ID": PHONE_ID,
    "TARGET_PHONE_NUMBER": TARGET_PHONE_NUMBER,
}
missing = [k for k, v in required_envs.items() if not v]
if missing:
    raise RuntimeError(f"❌ Missing required environment variables: {', '.join(missing)}")

# Load number map safely
try:
    NUMBER_MAP = json.loads(os.getenv("NUMBER_MAP", "{}"))
except Exception as e:
    print(f"❌ Invalid NUMBER_MAP: {e}")
    NUMBER_MAP = {}

# Flask app setup
app = Flask(__name__)

# Discord setup
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
client = discord.Client(intents=intents)
discord_ready = asyncio.Event()

@client.event
async def on_ready():
    print(f"✅ Discord bot logged in as {client.user}")
    discord_ready.set()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        content = f"[DM] {message.author.name}: {message.content}"
    else:
        content = f"[#{message.channel.name}] {message.author.name}: {message.content}"

    if TARGET_PHONE_NUMBER:
        print(f"📥 Sending SMS to {TARGET_PHONE_NUMBER}: {content}")
        send_sms_via_telerivet(TARGET_PHONE_NUMBER, content)
    else:
        print("❌ TARGET_PHONE_NUMBER not set.")

# Telerivet SMS sender
def send_sms_via_telerivet(to_number, message):
    url = f"https://api.telerivet.com/v1/projects/{PROJECT_ID}/messages/send"
    payload = {
        "to": to_number,
        "content": message,
        "phone_id": PHONE_ID
    }
    headers = {
        'Content-Type': 'application/json'
    }

    max_retries = 3
    retry_delay = 5
    timeout = 30

    for attempt in range(max_retries):
        try:
            response = requests.post(url, auth=(API_KEY, ""), json=payload, headers=headers, timeout=timeout)
            if response.status_code == 200:
                print("📤 SMS sent successfully!")
                return
            else:
                print(f"❌ Telerivet error {response.status_code}: {response.text}")
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout on attempt {attempt + 1}. Retrying in {retry_delay}s...")
        except requests.exceptions.RequestException as e:
            print(f"❌ Request exception: {e}")
        time.sleep(retry_delay)
    print("❌ Failed to send SMS after retries.")

# Incoming webhook route
@app.route("/incoming", methods=["POST"])
def incoming():
    try:
        print("Request Headers:", request.headers)
        print("Raw Data:", request.data)

        data = request.get_json(force=True) or request.form.to_dict()
        if not data:
            print("❌ No data received or malformed request")
            return "Invalid content", 415

        print("📩 Incoming SMS data:", data)

        from_number = data.get("from_number") or data.get("from")
        content = data.get("content") or data.get("message")

        if not content or " " not in content:
            print(f"❌ Invalid format or missing content: {content}")
            return "Invalid format. Use: target message", 400

        target, msg = content.split(" ", 1)
        target = target.lstrip("@")
        resolved = NUMBER_MAP.get(target, target)

        print(f"📤 Resolving target: {resolved} => {msg}")
        asyncio.run_coroutine_threadsafe(send_to_discord(resolved, msg), client.loop)

        return "Message accepted", 200

    except KeyError as e:
        print(f"❌ Missing expected key: {e}")
        return "Bad request", 400
    except Exception as e:
        print(f"❌ Exception in /incoming: {e}")
        print(traceback.format_exc())
        return "Internal server error", 500

# Async function to forward message to Discord
async def send_to_discord(resolved, msg):
    await discord_ready.wait()
    try:
        if resolved.isdigit():
            channel = client.get_channel(int(resolved))
            if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                await channel.send(msg)
                print(f"📤 Sent to channel #{channel.name} (ID: {resolved})")
                return
            try:
                user = await client.fetch_user(int(resolved))
                await user.send(msg)
                print(f"📤 Sent DM to user {user.name} (ID: {resolved})")
                return
            except discord.NotFound:
                print(f"❌ User ID {resolved} not found")
        else:
            for guild in client.guilds:
                channel = discord.utils.get(guild.channels, name=resolved)
                if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                    await channel.send(msg)
                    print(f"📤 Sent to channel #{channel.name} (by name)")
                    return
        print(f"❌ Could not resolve: {resolved}")
    except Exception as e:
        print(f"❌ Error sending to Discord: {e}")
        print(traceback.format_exc())

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    print("❌ Flask exception:", traceback.format_exc())
    return jsonify({"error": "Internal Server Error"}), 500

# Start Flask in separate thread
def start_flask():
    port = int(os.getenv("PORT", 5000))
    try:
        app.run(host="0.0.0.0", port=port, use_reloader=False)
    except Exception as e:
        print(f"❌ Failed to start Flask: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    Thread(target=start_flask).start()
    try:
        client.run(BOT_TOKEN)
    except Exception as e:
        print(f"❌ Failed to run Discord client: {e}")
        print(traceback.format_exc())
