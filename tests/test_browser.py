import http.server
import os
import shutil
import socketserver
import tempfile
import threading
from typing import Generator
import pytest

from browser_automator import BrowserAutomator

HTML_CONFIRM_PAGE = """<!DOCTYPE html>
<html>
<head>
  <title>Netflix - Update Netflix Household</title>
  <style>
    body {
      background-color: #141414;
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      margin: 0;
    }
    .card {
      background: #000;
      padding: 40px;
      border-radius: 8px;
      max-width: 480px;
      text-align: center;
      box-shadow: 0 4px 20px rgba(0,0,0,0.8);
    }
    .logo {
      color: #e50914;
      font-size: 28px;
      font-weight: bold;
      margin-bottom: 24px;
      letter-spacing: 2px;
    }
    h1 { font-size: 24px; margin-bottom: 16px; }
    p { color: #aaa; line-height: 1.5; margin-bottom: 28px; }
    .btn-black {
      background-color: #000;
      color: #fff;
      border: 2px solid #555;
      padding: 14px 28px;
      font-size: 16px;
      font-weight: 600;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .btn-black:hover {
      border-color: #fff;
      background-color: #222;
    }
    .success-msg {
      display: none;
      color: #46d369;
      font-size: 18px;
      font-weight: bold;
      margin-top: 20px;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">NETFLIX</div>
    <h1>Update Netflix Household</h1>
    <p>A Netflix Household is a collection of the devices connected to the internet at the main place you watch Netflix.</p>
    <button id="confirm-btn" class="btn-black" data-uia="confirm-update-btn">Confirm Update</button>
    <div id="status" class="success-msg">Your Netflix Household has been updated.</div>
  </div>
  <script>
    document.getElementById('confirm-btn').addEventListener('click', function() {
      this.style.display = 'none';
      document.getElementById('status').style.display = 'block';
    });
  </script>
</body>
</html>
"""

HTML_EXPIRED_PAGE = """<!DOCTYPE html>
<html>
<head><title>Netflix - Link Expired</title></head>
<body style="background:#141414;color:#fff;text-align:center;padding:50px;">
  <h1>This link has expired</h1>
  <p>To update your Netflix Household, request a new link from your TV.</p>
</body>
</html>
"""

HTML_ALREADY_UPDATED_PAGE = """<!DOCTYPE html>
<html>
<head><title>Netflix - Household Updated</title></head>
<body style="background:#141414;color:#fff;text-align:center;padding:50px;">
  <h1>Your Netflix Household has been updated</h1>
  <p>You can now continue watching Netflix on this device.</p>
</body>
</html>
"""


class MockNetflixHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if "/confirm" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_CONFIRM_PAGE.encode("utf-8"))
        elif "/expired" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_EXPIRED_PAGE.encode("utf-8"))
        elif "/already-updated" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_ALREADY_UPDATED_PAGE.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress standard logging during tests
        pass


@pytest.fixture(scope="module")
def mock_server():
    server = socketserver.TCPServer(("127.0.0.1", 0), MockNetflixHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def temp_screenshots_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_browser_clicks_confirm_update(mock_server, temp_screenshots_dir):
    automator = BrowserAutomator(
        headless=True,
        screenshots_dir=temp_screenshots_dir,
        timeout_ms=10000,
    )
    url = f"{mock_server}/confirm?nftoken=test_token_123"
    result = automator.confirm_netflix_update(url)

    assert result["success"] is True
    assert result["status"] == "confirmed"
    assert "Successfully clicked 'Confirm Update'" in result["message"]
    assert result["before_screenshot"] is not None
    assert os.path.exists(result["before_screenshot"])
    assert result["after_screenshot"] is not None
    assert os.path.exists(result["after_screenshot"])
    assert "Your Netflix Household has been updated." in result.get("page_feedback", "")


def test_browser_handles_expired_link(mock_server, temp_screenshots_dir):
    automator = BrowserAutomator(
        headless=True,
        screenshots_dir=temp_screenshots_dir,
        timeout_ms=10000,
    )
    url = f"{mock_server}/expired"
    result = automator.confirm_netflix_update(url)

    assert result["success"] is False
    assert result["status"] == "expired"
    assert "expired" in result["message"].lower()


def test_browser_handles_already_updated(mock_server, temp_screenshots_dir):
    automator = BrowserAutomator(
        headless=True,
        screenshots_dir=temp_screenshots_dir,
        timeout_ms=10000,
    )
    url = f"{mock_server}/already-updated"
    result = automator.confirm_netflix_update(url)

    assert result["success"] is True
    assert result["status"] == "already_updated"
