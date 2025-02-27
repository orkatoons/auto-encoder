from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

decision = {"approved_crop": None}
preview_data = {}  # Global storage for previews


@app.route('/send_previews', methods=['POST'])
def receive_previews():
    """Receive previews from encoding script and store them."""
    global preview_data  # Use the global variable
    preview_data = request.json.get("previews", {})
    print("✅ Received previews:", preview_data)
    return jsonify({"message": "Previews received."})


@app.route('/get_previews', methods=['GET'])
def get_previews():
    """Send previews to Discord bot if available."""
    global preview_data
    if preview_data:
        return jsonify(preview_data)
    return jsonify({})


@app.route('/approve', methods=['POST'])
def approve_crop():
    """Receive crop approval from Discord bot and reset preview data."""
    global preview_data
    data = request.json
    approved_crop = data.get("crop")
    print("✅ Received approval for:", approved_crop)
    if approved_crop:
        decision["approved_crop"] = approved_crop
        preview_data = {}  # Reset preview data after approval
        return jsonify({"message": "Approval received.", "crop": approved_crop})
    return jsonify({"error": "Invalid request"}), 400


@app.route('/get_approval', methods=['GET'])
def get_approval():
    """Return the approved crop and then reset it."""
    if decision["approved_crop"]:
        approved = decision["approved_crop"]
        # Reset the approved crop after it is fetched
        decision["approved_crop"] = None
        return jsonify({"approved_crop": approved})
    return jsonify({"approved_crop": None})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
