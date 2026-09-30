import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

# Upstash Redis Credentials from Environment Variables
UPSTASH_URL = os.environ.get("KV_REST_API_URL")
UPSTASH_TOKEN = os.environ.get("KV_REST_API_TOKEN")
FB_ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def cron_handler(path):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return jsonify({"error": "Upstash credentials missing"}), 500

    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    
    # Fetch pending comments from Upstash Redis
    res = requests.get(f"{UPSTASH_URL}/get/pending_comments", headers=headers)
    data = res.json()
    
    raw_value = data.get("result")
    if not raw_value:
        return jsonify({"status": "Success", "posted": 0, "message": "No pending comments found"})

    import json
    try:
        pending_list = json.loads(raw_value)
    except Exception:
        pending_list = []

    if not isinstance(pending_list, list) or len(pending_list) == 0:
        return jsonify({"status": "Success", "posted": 0, "message": "List is empty"})

    import time
    current_time = int(time.time())
    
    remaining_comments = []
    posted_count = 0

    for item in pending_list:
        video_id = item.get("video_id")
        comment_text = item.get("comment")
        schedule_time = item.get("schedule_time", 0)

        # Check if it's time to post
        if current_time >= schedule_time:
            # Post to Facebook Graph API
            fb_url = f"https://graph.facebook.com/v18.0/{video_id}/comments"
            payload = {
                "message": comment_text,
                "access_token": FB_ACCESS_TOKEN
            }
            fb_res = requests.post(fb_url, data=payload)
            
            if fb_res.status_code == 200:
                posted_count += 1
            else:
                # Keep it back in queue if failed, or handle as needed
                remaining_comments.append(item)
        else:
            remaining_comments.append(item)

    # Update Upstash Redis with the remaining comments
    requests.post(
        f"{UPSTASH_URL}/set/pending_comments",
        headers=headers,
        json=remaining_comments
    )

    return jsonify({
        "status": "Success",
        "posted": posted_count,
        "remaining": len(remaining_comments)
    })
