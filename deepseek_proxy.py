"""
DeepSeek API 重试代理 - 增强 Claude Code 使用 DeepSeek 的稳定性

用法：
  1. 启动代理:  python deepseek_proxy.py
  2. 设置环境变量:
       set ANTHROPIC_BASE_URL=http://localhost:8765
       set ANTHROPIC_AUTH_TOKEN=你的key
     （或直接在 settings.json 中修改 ANTHROPIC_BASE_URL）

功能：
  - 自动重试 429（限流）、5xx（服务端错误）、网络超时
  - 指数退避 + 随机抖动，避免雪崩
  - 请求/响应日志，方便排查
  - 保持与 Anthropic API 完全兼容
"""

import json
import time
import random
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen, HTTPError
from urllib.parse import urlparse
import ssl

# ============ 配置 ============
TARGET_BASE = "https://api.deepseek.com/anthropic"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8765
MAX_RETRIES = 3
TIMEOUT_SEC = 120  # 单次请求超时
# =============================

logging.basicConfig(
    level=logging.INFO,
    format="[DeepSeekProxy] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)

# 全局请求计数器
request_counter = 0
counter_lock = threading.Lock()


class ProxyHandler(BaseHTTPRequestHandler):
    """将收到的 Anthropic API 请求转发到 DeepSeek，并实现重试逻辑"""

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        global request_counter

        path = self.path
        body_bytes = None
        if method == "POST":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b""

        # 转发到 DeepSeek
        target_url = f"{TARGET_BASE}{path}"

        with counter_lock:
            request_counter += 1
            req_id = request_counter

        logging.info(f"[#{req_id}] {method} {path}")

        # 重试循环
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logging.info(f"[#{req_id}] 第 {attempt} 次重试，等待 {wait:.1f}s...")
                    time.sleep(wait)

                headers = {}
                for key, value in self.headers.items():
                    if key.lower() not in ("host", "content-length", "transfer-encoding"):
                        headers[key] = value

                req = Request(target_url, data=body_bytes, headers=headers, method=method)
                # 跳过 SSL 验证（如有必要可去掉）
                ctx = ssl.create_default_context()
                resp = urlopen(req, timeout=TIMEOUT_SEC, context=ctx)

                # 成功
                resp_body = resp.read()
                resp_headers = dict(resp.headers)

                self.send_response(resp.status)
                for h, v in resp_headers.items():
                    if h.lower() not in ("transfer-encoding", "content-encoding", "content-length"):
                        self.send_header(h, v)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)

                if attempt > 1:
                    logging.info(f"[#{req_id}] ✅ 重试成功")
                else:
                    logging.info(f"[#{req_id}] ✅ {resp.status}")
                return

            except HTTPError as e:
                status = e.code
                err_body = e.read().decode("utf-8", errors="replace")[:500]
                last_error = f"HTTP {status}: {err_body}"

                if status in (429, 500, 502, 503, 504):
                    logging.warning(f"[#{req_id}] ⚠️  {last_error}")
                    if attempt < MAX_RETRIES:
                        continue
                else:
                    # 4xx 非限流错误直接透传，不重试
                    logging.warning(f"[#{req_id}] ❌ {last_error}")
                    self._send_error(e.code, err_body)
                    return

            except Exception as e:
                last_error = str(e)
                logging.warning(f"[#{req_id}] ⚠️  {last_error}")
                if attempt < MAX_RETRIES:
                    continue

        # 所有重试都失败
        logging.error(f"[#{req_id}] ❌ 所有重试失败: {last_error}")
        self._send_error(502, json.dumps({
            "type": "error",
            "error": {"type": "proxy_error", "message": f"所有重试失败: {last_error}"}
        }))

    def _send_error(self, status, body):
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, format, *args):
        pass  # 用自己的 logging，不输出到 stderr


def run_proxy():
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler)
    logging.info(f"🚀 DeepSeek 重试代理已启动")
    logging.info(f"   监听: http://{LISTEN_HOST}:{LISTEN_PORT}")
    logging.info(f"   转发到: {TARGET_BASE}")
    logging.info(f"   最大重试: {MAX_RETRIES} 次")
    logging.info(f"   超时: {TIMEOUT_SEC}s")
    logging.info(f"")
    logging.info(f"   在 settings.json 中设置:")
    logging.info(f"   \"ANTHROPIC_BASE_URL\": \"http://{LISTEN_HOST}:{LISTEN_PORT}\"")
    logging.info(f"")
    server.serve_forever()


if __name__ == "__main__":
    run_proxy()
