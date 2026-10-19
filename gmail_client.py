import email
import imaplib
import logging
import re
from typing import Dict, List, Optional, Tuple

from email_parser import (
    decode_mime_header,
    extract_email_body,
    extract_netflix_confirmation_link,
)

logger = logging.getLogger(__name__)


class GmailClient:
    """Handles IMAP connection to Gmail, searching for Netflix emails and extracting links."""

    def __init__(
        self,
        user_email: str,
        app_password: str,
        imap_server: str = "imap.gmail.com",
        imap_port: int = 993,
    ):
        self.user_email = user_email.strip()
        # Remove any whitespace from the 16-character app password
        self.app_password = app_password.replace(" ", "").strip()
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.mail: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> None:
        """Connects and authenticates to Gmail via IMAP over SSL."""
        if not self.user_email or not self.app_password:
            raise ValueError(
                "GMAIL_EMAIL and GMAIL_APP_PASSWORD must be configured. "
                "Please set them in your .env file or pass them as CLI options."
            )

        logger.info(f"Connecting to {self.imap_server}:{self.imap_port} as {self.user_email}...")
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.mail.login(self.user_email, self.app_password)
            logger.info("Successfully authenticated with Gmail IMAP.")
        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            if "AUTHENTICATIONFAILED" in error_msg or "Invalid credentials" in error_msg:
                raise RuntimeError(
                    f"Gmail authentication failed for {self.user_email}.\n"
                    "Tip: Gmail requires a dedicated 16-character 'App Password', not your standard Google password.\n"
                    "1. Go to https://myaccount.google.com/apppasswords\n"
                    "2. Ensure 2-Step Verification is enabled on your Google account\n"
                    "3. Generate an App Password and set it in your .env file as GMAIL_APP_PASSWORD"
                ) from e
            raise RuntimeError(f"Failed to connect to Gmail: {error_msg}") from e

    def disconnect(self) -> None:
        """Closes mailbox and logs out."""
        if self.mail:
            try:
                self.mail.close()
            except Exception:
                pass
            try:
                self.mail.logout()
            except Exception:
                pass
            self.mail = None
            logger.info("Disconnected from Gmail.")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def search_netflix_emails(
        self,
        subject_filter: str = "Important: How to update your Netflix household",
        unread_only: bool = True,
        max_results: int = 10,
    ) -> List[Dict]:
        """
        Searches inbox for emails matching the subject filter.
        Returns a list of parsed email metadata and extracted action links.
        """
        if not self.mail:
            raise RuntimeError("Not connected to Gmail IMAP. Call connect() first.")

        self.mail.select("INBOX")

        # Target "Netflix" in subject directly on IMAP server
        if unread_only:
            search_criteria = ["UNSEEN", "SUBJECT", "Netflix"]
        else:
            search_criteria = ["SUBJECT", "Netflix"]

        status, response = self.mail.search(None, *search_criteria)
        if status != "OK" or not response or not response[0]:
            logger.info("No matching Netflix emails found in inbox.")
            return []

        message_ids = response[0].split()
        # Sort latest first
        message_ids.reverse()
        message_ids = message_ids[:max_results]

        matching_emails = []
        normalized_filter = subject_filter.lower().strip()

        for msg_id in message_ids:
            try:
                # Use BODY.PEEK[] instead of RFC822!
                # In the IMAP protocol, RFC822 or BODY[] implicitly marks the message as read (\Seen).
                # BODY.PEEK[] fetches the message WITHOUT setting the \Seen flag.
                res_code, msg_data = self.mail.fetch(msg_id, "(BODY.PEEK[])")
                if res_code != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw_email_bytes = msg_data[0][1]
                msg = email.message_from_bytes(raw_email_bytes)

                subject = decode_mime_header(msg.get("Subject", ""))
                from_addr = decode_mime_header(msg.get("From", ""))
                date_str = decode_mime_header(msg.get("Date", ""))

                # Check subject match (flexible: exact or contains "how to update your netflix household")
                norm_subject = subject.lower().strip()
                is_match = (
                    normalized_filter in norm_subject
                    or "how to update your netflix household" in norm_subject
                    or ("update" in norm_subject and "netflix household" in norm_subject)
                )

                if not is_match:
                    continue

                logger.info(f"Found matching email ID {msg_id.decode()}: '{subject}' from {from_addr}")

                html_body, text_body = extract_email_body(msg)
                action_link = extract_netflix_confirmation_link(html_body, text_body)

                matching_emails.append({
                    "id": msg_id.decode(),
                    "subject": subject,
                    "from": from_addr,
                    "date": date_str,
                    "action_link": action_link,
                    "html_body": html_body,
                    "text_body": text_body,
                })
            except Exception as e:
                logger.error(f"Error processing email ID {msg_id}: {e}")

        return matching_emails

    def mark_as_read(self, msg_id: str) -> None:
        """Marks a message as read in Gmail."""
        if not self.mail:
            return
        try:
            self.mail.store(msg_id.encode(), "+FLAGS", "\\Seen")
            logger.info(f"Marked email ID {msg_id} as read.")
        except Exception as e:
            logger.warning(f"Could not mark email ID {msg_id} as read: {e}")
