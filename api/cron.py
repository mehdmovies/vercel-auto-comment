import os
import time
import json
import requests
from http.server import BaseHTTPRequestHandler

KV_URL = os.environ.get("KV_REST_API_URL)
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

def get_kv_data():
    if not KV_URL or not KV_TOKEN:
        return []
    headers = {"Authorization": f"Bearer {KV_TOKEN}"}
    try:
        res = requests.get(f"{KV_URL}/get/pending_comments", headers=headers).json()
        result_data = res.get("result")
        if result_data:
            # যদি ডেটা ইতিমধ্যে স্ট্রিং হয় তবে ডিকোড করবে, নতুবা সরাসরি রিটার্ন করবে
            if isinstance(result_data, str):
                return json.loads(result_data)
            return result_data
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
        print(f"FB Response for {video_id}: {res}")  # ডিবাগ করার জন্য প্রিন্ট যোগ করা হলো
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

            if schedule_time and current_time >= schedule_time:
                success = post_fb_comment(video_id, comment)
                if success:
                    posted_count += 1
                else:
                    updated_list.append(item)
            else:
                updated_list.append(item)

        if posted_count > 0 or len(updated_list) != len(pending_list):
            set_kv_data(updated_list)

        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        response_msg = f"Cron run complete. Current Time: {current_time}, Posted: {posted_count}"
        self.wfile.write(response_msg.encode('utf-8'))
