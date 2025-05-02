# encode_service.py

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from threading import Thread
import os
from auto_encoder import encode_file, determine_encodes  # reuse your existing functions

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# WebSocket clients stored here
clients = []

@app.route("/encode", methods=["POST"])
def start_encoding():
    files = request.json.get("files", [])
    if not files:
        return jsonify({"error": "No files provided"}), 400

    thread = Thread(target=encode_batch, args=(files,))
    thread.start()
    return jsonify({"status": "Encoding started"}), 202


def encode_batch(file_paths):
    for path in file_paths:
        filename = os.path.basename(path)
        resolutions = determine_encodes(path)

        def status_callback(fname, res, status):
            socketio.emit("progress", {
                "filename": fname,
                "resolution": res,
                "status": status
            })

        encode_file(path, resolutions, status_callback)

@app.route("/health", methods=["GET"])
def health():
    return "Encode service is running", 200

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001)
