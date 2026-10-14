import email
import email.message
from email.header import decode_header
import html
import re
from typing import Optional, Tuple
from bs4 import BeautifulSoup


def decode_mime_header(header_value: Optional[str]) -> str:
    """Decodes MIME encoded-word strings (e.g. =?UTF-8?B?...?=) into unicode."""
    if not header_value:
        return ""
    try:
        fragments = decode_header(header_value)
        decoded_parts = []
        for fragment, encoding in fragments:
            if isinstance(fragment, bytes):
                decoded_parts.append(fragment.decode(encoding or "utf-8", errors="replace"))
            else:
                decoded_parts.append(str(fragment))
        return "".join(decoded_parts)
    except Exception:
        return str(header_value)


def extract_email_body(msg: email.message.Message) -> Tuple[str, str]:
    """
    Extracts (html_content, text_content) from an email.message.Message.
    Handles multipart emails, character sets, and base64/quoted-printable payloads.
    """
    html_parts = []
    text_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                continue

            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                continue

            charset = part.get_content_charset() or "utf-8"
            try:
                decoded_text = payload.decode(charset, errors="replace")
            except Exception:
                decoded_text = payload.decode("utf-8", errors="replace")

            if content_type == "text/html":
                html_parts.append(decoded_text)
            elif content_type == "text/plain":
                text_parts.append(decoded_text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded_text = payload.decode(charset, errors="replace")
            except Exception:
                decoded_text = payload.decode("utf-8", errors="replace")

            if msg.get_content_type() == "text/html":
                html_parts.append(decoded_text)
            else:
                text_parts.append(decoded_text)

    return "\n".join(html_parts), "\n".join(text_parts)


def extract_netflix_confirmation_link(
    html_content: str,
    text_content: str = "",
    target_button_text: str = "Yes, this was me",
) -> Optional[str]:
    """
    Locates the confirmation URL from Netflix email body.
    Searches for button/link with text 'Yes, this was me' (case-insensitive),
    with fallbacks for aria labels, titles, and Netflix URL patterns.
    """
    # Normalize regex pattern for "Yes, this was me"
    pattern = re.compile(
        r"yes[\s,]+this\s+was\s+me",
        re.IGNORECASE,
    )

    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")

        # Strategy 1: Check text content of anchor tags
        for a_tag in soup.find_all("a", href=True):
            text = a_tag.get_text(separator=" ", strip=True)
            if pattern.search(text):
                return clean_url(a_tag["href"])

        # Strategy 2: Check aria-label, title, or alt attributes
        for a_tag in soup.find_all("a", href=True):
            for attr in ("aria-label", "title"):
                val = a_tag.get(attr, "")
                if val and pattern.search(val):
                    return clean_url(a_tag["href"])

            # Check image alt inside anchor
            for img in a_tag.find_all("img", alt=True):
                if pattern.search(img["alt"]):
                    return clean_url(a_tag["href"])

        # Strategy 3: Check buttons inside or wrapping links
        for btn in soup.find_all(["button", "div", "td", "span"]):
            text = btn.get_text(separator=" ", strip=True)
            if pattern.search(text):
                # Search parent or children for an <a> tag
                parent_a = btn.find_parent("a", href=True)
                if parent_a:
                    return clean_url(parent_a["href"])
                child_a = btn.find("a", href=True)
                if child_a:
                    return clean_url(child_a["href"])

        # Strategy 4: Fallback - any Netflix verification link
        for a_tag in soup.find_all("a", href=True):
            href = clean_url(a_tag["href"])
            if "netflix.com" in href.lower() and any(
                k in href.lower()
                for k in ["update", "household", "primary-location", "nftoken", "verify"]
            ):
                return href

    # Strategy 5: Plain text fallback
    if text_content:
        lines = text_content.splitlines()
        for i, line in enumerate(lines):
            if pattern.search(line):
                # Look around surrounding lines for a URL
                context_window = " ".join(lines[max(0, i - 2) : min(len(lines), i + 4)])
                urls = re.findall(r"https?://[^\s<>\"']+", context_window)
                for u in urls:
                    if "netflix.com" in u.lower():
                        return clean_url(u)

        # Fallback regex in full plain text
        all_urls = re.findall(r"https?://[^\s<>\"']+", text_content)
        for u in all_urls:
            if "netflix.com" in u.lower() and any(
                k in u.lower()
                for k in ["update", "household", "primary-location", "nftoken"]
            ):
                return clean_url(u)

    return None


def clean_url(url: str) -> str:
    """Cleans up unescaped entities and extra whitespaces from extracted URL."""
    cleaned = html.unescape(url.strip())
    # Remove surrounding quotes or angles if present
    cleaned = cleaned.strip("<>\"' ")
    return cleaned
