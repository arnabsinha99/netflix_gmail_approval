import argparse
from datetime import datetime
import logging
import os
import sys
import time
from typing import Optional, Tuple

from browser_automator import BrowserAutomator
from config import config
from gmail_client import GmailClient
from purge_old_files import purge_old_files

logger = logging.getLogger("netflix_automation")


def configure_logging(logs_dir: str = config.logs_dir) -> str:
    """Configures dual logging: stdout + timestamped run log file."""
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(logs_dir, f"run_{timestamp}.log")

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    # 1. Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. File handler for this specific execution
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return log_file_path


def process_once(
    email_address: str,
    app_password: str,
    subject_filter: str,
    headless: bool,
    dry_run: bool = False,
    unread_only: bool = True,
    mark_as_read: bool = True,
) -> bool:
    """Performs a single check of Gmail, finds matching email, and confirms Netflix update."""
    client = GmailClient(
        user_email=email_address,
        app_password=app_password,
        imap_server=config.imap_server,
        imap_port=config.imap_port,
    )

    try:
        client.connect()
    except Exception as e:
        logger.error(f"\n❌ Connection failed: {e}")
        return False

    try:
        logger.info(f"Searching for emails with subject: '{subject_filter}' (unread_only={unread_only})...")
        emails = client.search_netflix_emails(
            subject_filter=subject_filter,
            unread_only=unread_only,
        )

        if not emails:
            logger.info("ℹ️ No matching emails found in inbox.")
            return False

        logger.info(f"✅ Found {len(emails)} matching email(s). Processing the most recent one...")
        target_email = emails[0]
        logger.info(f"Subject: {target_email['subject']}")
        logger.info(f"Date:    {target_email['date']}")
        logger.info(f"From:    {target_email['from']}")

        action_link = target_email.get("action_link")
        if not action_link:
            logger.error("❌ Could not extract 'Yes, this was me' link from the email body.")
            return False

        logger.info(f"🔗 Extracted Confirmation Link: {action_link}")

        if dry_run:
            logger.info("🧪 [DRY RUN] Skipping browser interaction and button click.")
            return True

        automator = BrowserAutomator(
            headless=headless,
            screenshots_dir=config.screenshots_dir,
        )
        result = automator.confirm_netflix_update(action_link)

        if result.get("success"):
            logger.info("🎉 SUCCESS! " + result.get("message", ""))
            if result.get("before_screenshot"):
                logger.info(f"📸 Before screenshot: {result['before_screenshot']}")
            if result.get("after_screenshot"):
                logger.info(f"📸 After screenshot:  {result['after_screenshot']}")

            if mark_as_read:
                client.mark_as_read(target_email["id"])
            return True
        else:
            logger.error("❌ FAILED: " + result.get("message", ""))
            if result.get("before_screenshot"):
                logger.info(f"📸 Screenshot before failure: {result['before_screenshot']}")
            return False

    finally:
        client.disconnect()


def watch_inbox(
    email_address: str,
    app_password: str,
    subject_filter: str,
    headless: bool,
    poll_interval: int,
    mark_as_read: bool,
) -> None:
    """Continuously monitors Gmail inbox until a matching Netflix email is detected and processed."""
    logger.info(
        f"👀 Watching Gmail ({email_address}) for '{subject_filter}' every {poll_interval}s. "
        "Press Ctrl+C to stop."
    )
    iteration = 1
    while True:
        try:
            logger.info(f"--- [Check #{iteration}] Checking inbox... ---")
            success = process_once(
                email_address=email_address,
                app_password=app_password,
                subject_filter=subject_filter,
                headless=headless,
                dry_run=False,
                unread_only=True,
                mark_as_read=mark_as_read,
            )
            if success:
                logger.info("✅ Finished processing household update. Exiting watch mode.")
                break

            time.sleep(poll_interval)
            iteration += 1
        except KeyboardInterrupt:
            logger.info("\n🛑 Watch mode stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error during poll check: {e}")
            time.sleep(poll_interval)


def run_mock_test(headed: bool = False) -> bool:
    """Executes a complete self-contained local test with a simulated email and mock Netflix server."""
    from tests.test_end_to_end import run_end_to_end_mock_demo
    return run_end_to_end_mock_demo(headed=headed)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automate Netflix Household confirmation from Gmail.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--email",
        default=config.gmail_email,
        help="Your Gmail address (default: from .env GMAIL_EMAIL)",
    )
    parser.add_argument(
        "--password",
        default=config.gmail_app_password,
        help="Google 16-character App Password (default: from .env GMAIL_APP_PASSWORD)",
    )
    parser.add_argument(
        "--subject",
        default=config.email_subject,
        help="Email subject to look for",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously poll inbox until email arrives",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=config.poll_interval,
        help="Polling interval in seconds for --watch mode",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser with visible UI (headed mode)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Find email and extract link without opening browser or clicking Confirm",
    )
    parser.add_argument(
        "--all-emails",
        action="store_true",
        help="Search all emails instead of only unread (UNSEEN) emails",
    )
    parser.add_argument(
        "--test-mock",
        action="store_true",
        help="Run self-contained end-to-end demonstration test with simulated email and mock page",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Directly test the browser automator on a specific URL without checking Gmail",
    )
    parser.add_argument(
        "--purge-days",
        type=int,
        default=config.purge_days,
        help="Age threshold in days to purge old screenshots and log files (default: 7)",
    )
    parser.add_argument(
        "--no-purge",
        action="store_true",
        help="Disable automatic purge of old screenshots and logs",
    )

    args = parser.parse_args()

    # Configure timestamped log file for this execution
    log_file = configure_logging(logs_dir=config.logs_dir)
    logger.info(f"Execution started. Session log: {log_file}")

    # Automatically purge screenshots & logs older than retention period (default 7 days)
    if not args.no_purge:
        try:
            purge_old_files(days=args.purge_days)
        except Exception as e:
            logger.warning(f"Auto-purge failed: {e}")

    # If --test-mock requested
    if args.test_mock:
        logger.info("🚀 Running self-contained mock end-to-end integration test...")
        success = run_mock_test(headed=args.headed)
        sys.exit(0 if success else 1)

    # If direct URL provided
    if args.url:
        logger.info(f"🌐 Direct URL mode: Confirming update at {args.url}")
        automator = BrowserAutomator(
            headless=not args.headed,
            screenshots_dir=config.screenshots_dir,
        )
        res = automator.confirm_netflix_update(args.url)
        logger.info(f"Result: {res}")
        sys.exit(0 if res.get("success") else 1)

    # Validate Gmail credentials
    email_address = args.email
    password = args.password

    if not email_address or not password:
        logger.error(
            "\n"
            "❌ Missing Gmail credentials!\n"
            "Please create a .env file or pass --email and --password.\n"
            "Example .env:\n"
            "  GMAIL_EMAIL=your.email@gmail.com\n"
            "  GMAIL_APP_PASSWORD=abcd efgh ijkl mnop\n\n"
            "To run a simulated test right now without Gmail credentials, run:\n"
            "  python main.py --test-mock\n"
        )
        sys.exit(1)

    headless = not args.headed if args.headed else config.headless

    if args.watch:
        watch_inbox(
            email_address=email_address,
            app_password=password,
            subject_filter=args.subject,
            headless=headless,
            poll_interval=args.interval,
            mark_as_read=config.mark_as_read,
        )
    else:
        success = process_once(
            email_address=email_address,
            app_password=password,
            subject_filter=args.subject,
            headless=headless,
            dry_run=args.dry_run,
            unread_only=not args.all_emails,
            mark_as_read=config.mark_as_read,
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
