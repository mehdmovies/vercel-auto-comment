import os
import requests
import json
import time
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
    try:
        res = requests.get(f"{UPSTASH_URL}/get/pending_comments", headers=headers)
        data = res.json()
    except Exception as e:
        return jsonify({"error": f"Failed to connect to Upstash: {str(e)}"}), 500
    
    raw_value = data.get("result")
    if not raw_value:
        return jsonify({"status": "Success", "posted": 0, "message": "No pending comments found"})

    try:
        pending_list = json.loads(raw_value)
    except Exception:
        pending_list = []

    if not isinstance(pending_list, list) or len(pending_list) == 0:
        return jsonify({"status": "Success", "posted": 0, "message": "List is empty"})

    current_time = int(time.time())
    
    remaining_comments = []
    posted_count = 0

    for item in pending_list:
        video_id = item.get("video_id")
        comment_text = item.get("comment")
        # upload.py এর সাথে মিলিয়ে 'schedule_timestamp' ব্যবহার করা হয়েছে
        schedule_time = item.get("schedule_timestamp", 0)

        # Check if it's time to post
        if current_time >= schedule_time:
            # Post to Facebook Graph API
            fb_url = f"https://graph.facebook.com/v18.0/{video_id}/comments"
            payload = {
                "message": comment_text,
                "access_token": FB_ACCESS_TOKEN
            }
            try:
                fb_res = requests.post(fb_url, data=payload)
                fb_data = fb_res.json()
            except Exception:
                fb_res = None

            if fb_res and fb_res.status_code == 200:
                posted_count += 1
            else:
                # যদি পোস্ট করতে ফেইল করে, তবে কিউ-তে আবার রেখে দেবো
                remaining_comments.append(item)
        else:
            # সময় না হলে এটি কিউ-তেই থাকবে পরবর্তী চেক করার জন্য
            remaining_comments.append(item)

    # Update Upstash Redis with the remaining comments
    try:
        requests.post(
            f"{UPSTASH_URL}/set/pending_comments",
            headers=headers,
            json=remaining_comments
        )
    except Exception as e:
        print(f"Error updating Upstash: {e}")

    return jsonify({
        "status": "Success",
        "posted": posted_count,
        "remaining": len(remaining_comments)
    })
