import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pytest

from email_parser import (
    clean_url,
    decode_mime_header,
    extract_email_body,
    extract_netflix_confirmation_link,
)


def test_decode_mime_header():
    # Test plain string
    assert decode_mime_header("Important: Update Household") == "Important: Update Household"
    # Test UTF-8 encoded MIME header
    encoded = "=?UTF-8?B?SW1wb3J0YW50OiBIb3cgdG8gdXBkYXRlIHlvdXIgTmV0ZmxpeCBob3VzZWhvbGQ=?="
    assert decode_mime_header(encoded) == "Important: How to update your Netflix household"
    # Test None / empty
    assert decode_mime_header(None) == ""
    assert decode_mime_header("") == ""


def test_clean_url():
    raw = '  <https://www.netflix.com/confirm?token=123&amp;source=email>  '
    assert clean_url(raw) == "https://www.netflix.com/confirm?token=123&source=email"


def test_extract_email_body_multipart():
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Important: How to update your Netflix household"
    msg["From"] = "info@mailer.netflix.com"

    text_part = MIMEText("Hello, please click Yes, this was me: https://www.netflix.com/verify", "plain")
    html_part = MIMEText(
        '<html><body><a href="https://www.netflix.com/confirm-update?token=xyz">Yes, this was me</a></body></html>',
        "html",
    )
    msg.attach(text_part)
    msg.attach(html_part)

    html_body, text_body = extract_email_body(msg)
    assert "https://www.netflix.com/confirm-update" in html_body
    assert "https://www.netflix.com/verify" in text_body


def test_extract_netflix_link_standard():
    html_content = """
    <html>
      <body>
        <h2>Manage your Netflix Household</h2>
        <p>A request was made to update your household.</p>
        <div style="margin: 20px 0;">
          <a href="https://www.netflix.com/account/update-primary-location?nftoken=abc123xyz"
             style="background-color: #E50914; color: #fff; padding: 12px 24px; text-decoration: none;">
            Yes, this was me
          </a>
        </div>
      </body>
    </html>
    """
    link = extract_netflix_confirmation_link(html_content)
    assert link == "https://www.netflix.com/account/update-primary-location?nftoken=abc123xyz"


def test_extract_netflix_link_case_variations():
    # Capitalized / Title case
    html_content = """
    <div>
      <a href="https://www.netflix.com/verify?token=title_case">
        Yes, This Was Me
      </a>
    </div>
    """
    assert extract_netflix_confirmation_link(html_content) == "https://www.netflix.com/verify?token=title_case"

    # All caps
    html_content_caps = """
    <div>
      <a href="https://www.netflix.com/verify?token=all_caps">
        YES, THIS WAS ME
      </a>
    </div>
    """
    assert extract_netflix_confirmation_link(html_content_caps) == "https://www.netflix.com/verify?token=all_caps"


def test_extract_netflix_link_nested_markup():
    # Nested span inside anchor tag
    html_content = """
    <table>
      <tr>
        <td align="center" bgcolor="#e50914">
          <a href="https://www.netflix.com/account/update-household?token=nested_span" target="_blank">
            <span style="font-weight: bold; color: white;">Yes, this was me</span>
          </a>
        </td>
      </tr>
    </table>
    """
    link = extract_netflix_confirmation_link(html_content)
    assert link == "https://www.netflix.com/account/update-household?token=nested_span"


def test_extract_netflix_link_aria_label():
    html_content = """
    <a href="https://www.netflix.com/update?token=aria_test" aria-label="Yes, this was me">
      <img src="https://assets.netflix.com/button.png" alt="Confirm" />
    </a>
    """
    assert extract_netflix_confirmation_link(html_content) == "https://www.netflix.com/update?token=aria_test"


def test_extract_netflix_link_fallback_url_pattern():
    # If text is slightly different (e.g. translated or updated by Netflix)
    html_content = """
    <div>
      <a href="https://www.netflix.com/account/update-primary-location?nftoken=token_pattern">
        Confirm TV Location
      </a>
    </div>
    """
    link = extract_netflix_confirmation_link(html_content)
    assert link == "https://www.netflix.com/account/update-primary-location?nftoken=token_pattern"


def test_extract_netflix_link_plain_text():
    text_content = """
    Hi John,
    We received a request to update your Netflix household.
    Click below to confirm:
    Yes, this was me
    https://www.netflix.com/account/update-primary-location?nftoken=plain_text_token

    If you did not make this request, ignore this message.
    """
    link = extract_netflix_confirmation_link("", text_content=text_content)
    assert link == "https://www.netflix.com/account/update-primary-location?nftoken=plain_text_token"
