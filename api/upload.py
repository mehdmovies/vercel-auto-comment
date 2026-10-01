import os
import json
import requests
from http.server import BaseHTTPRequestHandler

KV_URL = os.environ.get("KV_REST_API_URL")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")
SECRET_KEY = os.environ.get("SECRET_KEY", "my_super_secret_key")

def set_kv_data(data):
    headers = {"Authorization": f"Bearer {KV_TOKEN}"}
    payload = json.dumps(data)
    requests.post(f"{KV_URL}/set/pending_comments", headers=headers, data=payload)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
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
