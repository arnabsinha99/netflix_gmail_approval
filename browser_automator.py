import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class BrowserAutomator:
    """Automates browser interactions with the Netflix Household confirmation page."""

    def __init__(
        self,
        headless: bool = True,
        screenshots_dir: str = "screenshots",
        timeout_ms: int = 30000,
    ):
        self.headless = headless
        self.screenshots_dir = screenshots_dir
        self.timeout_ms = timeout_ms
        os.makedirs(self.screenshots_dir, exist_ok=True)

    def confirm_netflix_update(self, confirmation_url: str) -> Dict[str, Any]:
        """
        Navigates to the confirmation URL and clicks the black 'Confirm Update' button.
        Saves before/after screenshots and returns an outcome dictionary.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        before_screenshot = os.path.join(
            self.screenshots_dir, f"before_confirm_{timestamp}.png"
        )
        after_screenshot = os.path.join(
            self.screenshots_dir, f"after_confirm_{timestamp}.png"
        )

        logger.info(f"Launching Playwright Chromium (headless={self.headless})...")
        logger.info(f"Target URL: {confirmation_url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            try:
                # 1. Navigate to target URL
                logger.info(f"Navigating to {confirmation_url}...")
                page.goto(
                    confirmation_url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    # Network idle timeout is non-fatal if DOM is ready
                    pass

                page_title = page.title()
                logger.info(f"Page loaded: '{page_title}' ({page.url})")

                # Take pre-action screenshot
                page.screenshot(path=before_screenshot, full_page=True)
                logger.info(f"Pre-action screenshot saved: {before_screenshot}")

                # 2. Check for immediate expiration or already-updated messages
                page_body_text = page.locator("body").inner_text()
                lower_body = page_body_text.lower()

                if "already updated" in lower_body or "household has been updated" in lower_body:
                    logger.info("Page indicates Netflix household is already updated.")
                    browser.close()
                    return {
                        "success": True,
                        "status": "already_updated",
                        "message": "Netflix Household was already confirmed/updated.",
                        "before_screenshot": before_screenshot,
                        "after_screenshot": None,
                        "url": page.url,
                    }

                if "link has expired" in lower_body or "link is no longer valid" in lower_body:
                    logger.warning("The Netflix confirmation link has expired.")
                    browser.close()
                    return {
                        "success": False,
                        "status": "expired",
                        "message": "The Netflix confirmation link has expired (links expire in ~15 mins).",
                        "before_screenshot": before_screenshot,
                        "after_screenshot": None,
                        "url": page.url,
                    }

                # Check if redirected to login page (occurs when token is expired or consumed)
                if "/login" in page.url.lower():
                    logger.warning("Redirected to Netflix login page. The verification token has expired or is invalid.")
                    browser.close()
                    return {
                        "success": False,
                        "status": "expired_or_login_required",
                        "message": (
                            "Redirected to Netflix login page. This occurs when the verification token "
                            "is expired (tokens expire after 15 minutes) or has already been used. "
                            "Please trigger a new email request from your TV."
                        ),
                        "before_screenshot": before_screenshot,
                        "after_screenshot": None,
                        "url": page.url,
                    }

                # 3. Locate the "Confirm Update" button
                # Priority selectors covering Netflix's various page structures
                candidate_locators = [
                    # Button with text 'Confirm Update'
                    page.get_by_role("button", name=re.compile(r"confirm\s+update", re.IGNORECASE)),
                    # Link styled as button
                    page.get_by_role("link", name=re.compile(r"confirm\s+update", re.IGNORECASE)),
                    # Text-based locators
                    page.locator("button:has-text('Confirm Update')"),
                    page.locator("a:has-text('Confirm Update')"),
                    page.locator("[role='button']:has-text('Confirm Update')"),
                    # Netflix UIA / data attributes
                    page.locator("[data-uia='confirm-update-btn']"),
                    page.locator("[data-uia*='confirm-update']"),
                    page.locator("[data-uia*='set-primary-location']"),
                    # Specific styling: black button
                    page.locator("button.btn-black"),
                    page.locator("button.btn-primary:has-text('Confirm')"),
                    # Fallback general confirm
                    page.get_by_role("button", name=re.compile(r"confirm", re.IGNORECASE)),
                    page.locator("button:has-text('Confirm')"),
                ]

                target_btn = None
                matched_description = ""
                for loc in candidate_locators:
                    try:
                        if loc.count() > 0:
                            first_match = loc.first
                            if first_match.is_visible():
                                target_btn = first_match
                                matched_description = str(loc)
                                break
                    except Exception:
                        continue

                if not target_btn:
                    logger.error("Could not find 'Confirm Update' button on the landing page.")
                    browser.close()
                    return {
                        "success": False,
                        "status": "button_not_found",
                        "message": "Could not find 'Confirm Update' button on the page.",
                        "before_screenshot": before_screenshot,
                        "after_screenshot": None,
                        "url": page.url,
                    }

                logger.info(f"Found 'Confirm Update' button ({matched_description}). Clicking...")
                target_btn.scroll_into_view_if_needed()
                target_btn.click(timeout=10000)

                # Wait for post-click response or network idle
                page.wait_for_timeout(3000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass

                # Post-action screenshot
                page.screenshot(path=after_screenshot, full_page=True)
                logger.info(f"Post-action screenshot saved: {after_screenshot}")

                post_body = page.locator("body").inner_text()
                browser.close()

                return {
                    "success": True,
                    "status": "confirmed",
                    "message": "Successfully clicked 'Confirm Update' on Netflix site!",
                    "before_screenshot": before_screenshot,
                    "after_screenshot": after_screenshot,
                    "final_url": page.url,
                    "page_feedback": post_body[:300].strip(),
                }

            except PlaywrightTimeoutError as te:
                logger.error(f"Timeout occurred during browser automation: {te}")
                try:
                    page.screenshot(path=before_screenshot, full_page=True)
                except Exception:
                    pass
                browser.close()
                return {
                    "success": False,
                    "status": "timeout",
                    "message": f"Timeout waiting for page or element: {te}",
                    "before_screenshot": before_screenshot if os.path.exists(before_screenshot) else None,
                    "after_screenshot": None,
                }
            except Exception as e:
                logger.error(f"Unexpected error during browser automation: {e}")
                browser.close()
                return {
                    "success": False,
                    "status": "error",
                    "message": f"Browser error: {e}",
                    "before_screenshot": before_screenshot if os.path.exists(before_screenshot) else None,
                    "after_screenshot": None,
                }
