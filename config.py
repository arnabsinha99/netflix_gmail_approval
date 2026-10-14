import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()

@dataclass
class Config:
    gmail_email: str = os.getenv("GMAIL_EMAIL", "")
    gmail_app_password: str = os.getenv("GMAIL_APP_PASSWORD", "")
    imap_server: str = os.getenv("IMAP_SERVER", "imap.gmail.com")
    imap_port: int = int(os.getenv("IMAP_PORT", "993"))
    
    # Netflix specific settings
    email_subject: str = os.getenv("EMAIL_SUBJECT", "Important: How to update your Netflix household")
    email_button_text: str = os.getenv("EMAIL_BUTTON_TEXT", "Yes, this was me")
    confirm_button_text: str = os.getenv("CONFIRM_BUTTON_TEXT", "Confirm Update")
    
    # Automation behavior
    headless: bool = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
    mark_as_read: bool = os.getenv("MARK_AS_READ", "true").lower() in ("true", "1", "yes")
    poll_interval: int = int(os.getenv("POLL_INTERVAL", "15"))  # seconds between checks in watch mode
    # File locations & retention
    screenshots_dir: str = os.getenv("SCREENSHOTS_DIR", "screenshots")
    logs_dir: str = os.getenv("LOGS_DIR", "logs")
    purge_days: int = int(os.getenv("PURGE_DAYS", "7"))

config = Config()
