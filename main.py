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

        # Your logic here, for example:
        prefix = content.split()[0].lower()
        message = " ".join(content.split()[1:])
        channel_id = NUMBER_MAP.get(prefix)

        if not channel_id:
            return jsonify({"error": f"prefix '{prefix}' not found"}), 400

        # send to Discord here

        return jsonify({"success": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
