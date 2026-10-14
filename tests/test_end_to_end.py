import http.server
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import shutil
import socketserver
import tempfile
import threading
from unittest.mock import MagicMock, patch
import pytest

from browser_automator import BrowserAutomator
from gmail_client import GmailClient
from tests.test_browser import HTML_CONFIRM_PAGE, MockNetflixHandler

logger = logging.getLogger(__name__)


def create_sample_netflix_email(confirmation_url: str) -> bytes:
    """Builds a realistic Netflix raw MIME email."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Important: How to update your Netflix household"
    msg["From"] = "Netflix <info@mailer.netflix.com>"
    msg["To"] = "user@example.com"
    msg["Date"] = "Mon, 13 Oct 2026 10:30:00 +0000"

    plain_body = f"""
    Hi,
    A request was made to update your Netflix Household.
    Please confirm:
    Yes, this was me: {confirmation_url}
    """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Update your Netflix Household</title></head>
    <body style="font-family: Arial, sans-serif; background-color: #f2f2f2; padding: 20px;">
      <table align="center" width="600" style="background:#ffffff; padding: 30px; border-radius: 6px;">
        <tr>
          <td>
            <h1 style="color: #e50914; font-size: 26px;">NETFLIX</h1>
            <h2 style="color: #222;">Important: How to update your Netflix household</h2>
            <p style="color: #555; font-size: 15px; line-height: 1.6;">
              Someone requested to update the Netflix Household for your account.
              If this was you, please confirm by clicking the button below.
            </p>
            <div style="text-align: center; margin: 35px 0;">
              <a href="{confirmation_url}"
                 style="background-color: #e50914; color: #ffffff; padding: 14px 28px;
                        text-decoration: none; font-size: 16px; font-weight: bold;
                        border-radius: 4px; display: inline-block;">
                Yes, this was me
              </a>
            </div>
            <p style="color: #888; font-size: 12px;">
              This link is valid for 15 minutes. If you did not make this request, we recommend changing your password.
            </p>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg.as_bytes()


def run_end_to_end_mock_demo(headed: bool = False) -> bool:
    """
    Starts a local mock web server, simulates fetching the Netflix email,
    runs the Playwright browser automation, and verifies that 'Confirm Update' was clicked.
    """
    print("\n" + "=" * 70)
    print("🧪 NETFLIX HOUSEHOLD AUTOMATION - END-TO-END SIMULATED TEST")
    print("=" * 70)

    # 1. Start local mock HTTP server
    server = socketserver.TCPServer(("127.0.0.1", 0), MockNetflixHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    mock_url = f"http://127.0.0.1:{port}/confirm?token=simulated_netflix_token_xyz"

    print(f"\n[Step 1] Started mock Netflix web server at: {mock_url}")

    # 2. Build mock email payload
    raw_email_bytes = create_sample_netflix_email(mock_url)
    print("[Step 2] Created simulated Netflix email with subject:")
    print("         'Important: How to update your Netflix household'")
    print("         and button link 'Yes, this was me' -> mock server URL")

    # 3. Simulate Gmail Client with mock IMAP
    print("\n[Step 3] Simulating Gmail IMAP search and email retrieval...")
    client = GmailClient(
        user_email="simulated.user@gmail.com",
        app_password="mockpassword1234",
    )

    mock_mail = MagicMock()
    # Mock IMAP search returning 1 message ID
    mock_mail.search.return_value = ("OK", [b"101"])
    # Mock IMAP fetch returning raw email bytes
    mock_mail.fetch.return_value = ("OK", [(b"101 (RFC822 {1000})", raw_email_bytes)])
    mock_mail.store.return_value = ("OK", [b"101"])
    client.mail = mock_mail

    emails = client.search_netflix_emails(
        subject_filter="Important: How to update your Netflix household",
        unread_only=True,
    )

    if not emails:
        print("❌ FAILED: No matching emails found in simulation.")
        server.shutdown()
        server.server_close()
        return False

    email_item = emails[0]
    extracted_link = email_item.get("action_link")
    print(f"✅ Email found: ID={email_item['id']}, Subject='{email_item['subject']}'")
    print(f"✅ Extracted link from 'Yes, this was me' button: {extracted_link}")

    if extracted_link != mock_url:
        print(f"❌ Extracted link mismatch: {extracted_link} != {mock_url}")
        server.shutdown()
        server.server_close()
        return False

    # 4. Run Browser Automation
    print(f"\n[Step 4] Launching Playwright Chromium (headed={headed})...")
    screenshots_dir = "screenshots"
    automator = BrowserAutomator(
        headless=not headed,
        screenshots_dir=screenshots_dir,
    )

    result = automator.confirm_netflix_update(extracted_link)
    print(f"[Step 5] Automation finished with status: '{result.get('status')}'")
    print(f"         Result message: {result.get('message')}")

    if result.get("before_screenshot"):
        print(f"📸 Pre-action screenshot:  {result['before_screenshot']}")
    if result.get("after_screenshot"):
        print(f"📸 Post-action screenshot: {result['after_screenshot']}")

    # 5. Mark as read
    client.mark_as_read(email_item["id"])
    print(f"✅ Simulated marking email ID {email_item['id']} as read in Gmail.")

    # Cleanup
    server.shutdown()
    server.server_close()

    success = result.get("success", False)
    if success:
        print("\n" + "=" * 70)
        print("🎉 END-TO-END TEST PASSED! All steps succeeded seamlessly.")
        print("=" * 70 + "\n")
    else:
        print("\n❌ END-TO-END TEST FAILED.\n")

    return success


def test_full_mock_pipeline():
    """Pytest wrapper for the end-to-end mock demo."""
    assert run_end_to_end_mock_demo(headed=False) is True
