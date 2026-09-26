import os
import time
import json
import requests
from http.server import BaseHTTPRequestHandler

KV_URL = os.environ.get("KV_REST_API_URL")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

def get_kv_data():
    if not KV_URL or not KV_TOKEN:
        return []
    headers = {"Authorization": f"Bearer {KV_TOKEN}"}
    try:
        res = requests.get(f"{KV_URL}/get/pending_comments", headers=headers).json()
        if res.get("result"):
            return json.loads(res["result"])
    except Exception as e:
        print(f"Error reading KV: {e}")
    return []

def set_kv_data(data):
    headers = {"Authorization": f"Bearer {KV_TOKEN}"}
    payload = json.dumps(data)
    try:
        requests.post(f"{KV_URL}/set/pending_comments", headers=headers, data=payload)
    except Exception as e:
        print(f"Error saving to KV: {e}")

def post_fb_comment(video_id, comment_text):
    url = f"https://graph.facebook.com/v18.0/{video_id}/comments"
    payload = {
        'message': comment_text,
        'access_token': PAGE_ACCESS_TOKEN
    }
    try:
        res = requests.post(url, data=payload).json()
        return 'id' in res
    except Exception as e:
        print(f"Error posting comment: {e}")
        return False

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        current_time = int(time.time())
        pending_list = get_kv_data()
        updated_list = []
        posted_count = 0

        for item in pending_list:
            video_id = item.get("video_id")
            schedule_time = item.get("schedule_timestamp")
            comment = item.get("comment")

            # বর্তমান সময় ভিডিওর শিডিউল টাইমের সমান বা পার হয়ে গেলে কমেন্ট করবে
            if current_time >= schedule_time:
                success = post_fb_comment(video_id, comment)
                if success:
                    posted_count += 1
                else:
                    # যদি নেটওয়ার্ক বা ফেসবুক সমস্যার কারণে কমেন্ট না হয়, তবে পরবর্তী চেকের জন্য রেখে দেবে
                    updated_list.append(item)
            else:
                updated_list.append(item)

        # যদি কোনো নতুন কমেন্ট পোস্ট হয়ে থাকে, তবে আপডেট করা ডাটা সেভ করবে
        if posted_count > 0:
            set_kv_data(updated_list)

        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        response_msg = f"Cron run complete. Current Time: {current_time}, Posted: {posted_count}"
        self.wfile.write(response_msg.encode('utf-8'))