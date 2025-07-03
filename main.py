import os
from flask import Flask, request, jsonify

# ✅ Flask App Init
app = Flask(__name__)

# ✅ Root Route
@app.route("/")
def home():
    return "✅ ProfitPilot FX Auto-Trader Backend is Live"

# ✅ Health Check Route
@app.route("/health")
def health():
    return jsonify({"status": "OK", "message": "Running"}), 200

# ✅ Add Your Webhooks / License Logic Here
@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.json
    print("📩 Webhook received:", data)
    # TODO: Validate, process NowPayments webhook here
    return jsonify({"status": "received"}), 200

# ✅ Render-Compatible Port Binding
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
