import os
import json
import requests
from http.server import BaseHTTPRequestHandler
import time

KV_URL = os.environ.get("KV_REST_API_URL")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")
SECRET_KEY = os.environ.get("SECRET_KEY", "my_super_secret_key")
FB_ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

def set_kv_data(data):
    headers = {"Authorization": f"Bearer {KV_TOKEN}"}
    payload = json.dumps(data)
    requests.post(f"{KV_URL}/set/pending_comments", headers=headers, data=payload)

def get_kv_data():
    headers = {"Authorization": f"Bearer {KV_TOKEN}"}
    try:
        res = requests.get(f"{KV_URL}/get/pending_comments", headers=headers)
        return res.json().get("result")
    except Exception:
        return None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # এটি cron-job.org বা ব্রাউজার থেকে GET রিকোয়েস্ট আসলে কমেন্ট পোস্ট করার কাজটি করবে
        try:
            if not KV_URL or not KV_TOKEN:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Upstash credentials missing")
                return

            raw_value = get_kv_data()
            if not raw_value:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "Success", "posted": 0, "message": "No pending comments found"}).encode('utf-8'))
                return

            try:
                pending_list = json.loads(raw_value)
            except Exception:
                pending_list = []

            if not isinstance(pending_list, list) or len(pending_list) == 0:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "Success", "posted": 0, "message": "List is empty"}).encode('utf-8'))
                return

            current_time = int(time.time())
            remaining_comments = []
            posted_count = 0

            for item in pending_list:
                video_id = item.get("video_id")
                comment_text = item.get("comment")
                schedule_time = item.get("schedule_timestamp", 0)

                if current_time >= schedule_time:
                    fb_url = f"https://graph.facebook.com/v18.0/{video_id}/comments"
                    payload = {
                        "message": comment_text,
                        "access_token": FB_ACCESS_TOKEN
                    }
                    try:
                        fb_res = requests.post(fb_url, data=payload)
                        if fb_res.status_code == 200:
                            posted_count += 1
                        else:
                            remaining_comments.append(item)
                    except Exception:
                        remaining_comments.append(item)
                else:
                    remaining_comments.append(item)

            set_kv_data(remaining_comments)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response_data = {
                "status": "Success",
                "posted": posted_count,
                "remaining": len(remaining_comments)
            }
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

    def do_POST(self):
        # এটি বাইরে থেকে নতুন কমেন্ট বা ডেটা সেভ করার জন্য POST রিকোয়েস্ট হ্যান্ডেল করবে
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            body = json.loads(post_data.decode('utf-8'))
            req_key = body.get("secret_key")
            comments_data = body.get("comments", [])

            if req_key != SECRET_KEY:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Unauthorized")
                return

            set_kv_data(comments_data)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response_data = {"status": "success", "total_pending": len(comments_data)}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))
