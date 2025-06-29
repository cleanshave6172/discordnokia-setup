from flask import Flask, request, jsonify
import discord
import asyncio
import os

app = Flask(__name__)

# Prefix → Channel ID (all values as strings)
PREFIX_CHANNEL_MAP = {
    "abdu": "702388818770133023",
    "essa": "634430242089467904",
    "silver": "829356590452047884",
    "nova": "462623701788262400",
    "test": "466528311351312384",
    "as": "1386286796878385224",
    "king": "1218362669552238702"
}

# Optional: precompute valid channel IDs
VALID_CHANNEL_IDS = set(PREFIX_CHANNEL_MAP.values())

@app.route("/incoming", methods=["POST"])
def incoming():
    try:
        data = request.get_json(force=True)
        from_number = data.get("from_number")
        sms_body = data.get("content", "").strip()

        print(f"Incoming SMS: {sms_body}")

        try:
            target, message = sms_body.split(" ", 1)
        except ValueError:
            return jsonify({"error": "Missing message content"}), 400

        # Check if it's a known prefix
        if target in PREFIX_CHANNEL_MAP:
            channel_id = int(PREFIX_CHANNEL_MAP[target])
        else:
            try:
                # Fallback: treat as raw channel ID
                if target in VALID_CHANNEL_IDS:
                    channel_id = int(target)
                else:
                    return jsonify({"error": "Prefix not found"}), 400
            except ValueError:
                return jsonify({"error": "Invalid channel ID"}), 400

        # Send to Discord
        asyncio.run_coroutine_threadsafe(
            send_to_discord(channel_id, f"[{from_number}] {message}"),
            loop=asyncio.get_event_loop()
        )

        return jsonify({"success": True}), 200

    except Exception as e:
        print(f"Error in /incoming: {e}")
        return jsonify({"error": str(e)}), 500

# Replace this with your actual bot coroutine
async def send_to_discord(channel_id, message):
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(message)
    else:
        print(f"Channel not found: {channel_id}")
