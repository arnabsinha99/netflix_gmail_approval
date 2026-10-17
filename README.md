# Netflix Household Automation for Gmail

An automated Python script that connects to your Gmail, locates incoming Netflix household verification emails (**"Important: How to update your Netflix household"**), extracts the action link behind **"Yes, this was me"**, and opens the verification landing page via Playwright to click the black **"Confirm Update"** button.

---

## 🚀 Features

- **Gmail IMAP Connection**: Secure SSL connection using Google App Passwords (no cumbersome GCP OAuth project needed).
- **Intelligent Email Parsing**: Robust multipart MIME parser that handles HTML and plain-text emails, variations in whitespace, capitalization, and nested elements for `"Yes, this was me"`.
- **Headless & Headed Browser Automation**: Uses Playwright Chromium to navigate to Netflix's confirmation page, locate the black `"Confirm Update"` button, and trigger the update.
- **Visual Evidence**: Takes automatic pre-action and post-action screenshots saved to `screenshots/`.
- **Modes of Execution**:
  - **Single Run (`--once`)**: Check immediately for unread emails and process.
  - **Watch Mode (`--watch`)**: Continually polls Gmail (e.g. every 15s) waiting for the email to arrive after you request it from your TV.
  - **Visual Headed Mode (`--headed`)**: Watch the browser window open and click the button in real-time.
  - **Dry Run (`--dry-run`)**: Extract and display the confirmation link without clicking the button.
  - **Built-in Mock Integration Test (`--test-mock`)**: 100% offline self-test with simulated email and mock Netflix landing page.

---

## 🛠️ Environment Setup

### 1. Clone the Repository
```bash
git clone https://github.com/arnabsinha99/netflix_gmail_approval.git
cd netflix_gmail_approval
```

### 2. Create and Activate a Virtual Environment
Using Python `venv` (recommended):
```bash
python3 -m venv .venv
source .venv/bin/activate
```
*(On Windows: `.venv\Scripts\activate`)*

Or using Conda:
```bash
conda create -n netflix-auto python=3.13 -y
conda activate netflix-auto
```

### 3. Install Dependencies & Browser
Install Python packages and the required Playwright Chromium browser:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```ini
# Your Gmail account
GMAIL_EMAIL=your.email@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop

# Subject to filter
EMAIL_SUBJECT=Important: How to update your Netflix household

# Browser settings (true for background, false for visible window)
HEADLESS=true

# Operational Settings
MARK_AS_READ=true
POLL_INTERVAL=15
SCREENSHOTS_DIR=screenshots
LOGS_DIR=logs
PURGE_DAYS=7
```

---

## 🔑 Setting Up Gmail Access (Google App Password)

Gmail requires a 16-character **App Password** for automated scripts:

1. Go to your **Google Account Security** settings: [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Ensure **2-Step Verification** is turned **ON**.
3. Visit the **App Passwords** page: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Enter an app name (e.g., `Netflix Automation`) and click **Create**.
5. Copy the generated 16-character code (e.g., `abcd efgh ijkl mnop`) into `GMAIL_APP_PASSWORD` in your `.env` file.

---

## 🖥️ Usage

### 1. Run Built-in Test (No credentials required)
Verify that everything is working properly with the self-contained mock pipeline:
```bash
python main.py --test-mock
```

To watch the browser click the button during the test:
```bash
python main.py --test-mock --headed
```

### 2. Single Check (Live Gmail)
Check your Gmail inbox once for any unread Netflix update emails:
```bash
python main.py
```

### 3. Watch Mode (Recommended Workflow)
Start the script in watch mode **before** requesting the email on your TV:
```bash
python main.py --watch
```
Then, on your TV:
1. Select **Manage Netflix Household** > **Update Netflix Household** > **Send Email**.
2. The script will detect the email the moment it lands in Gmail, extract the link, and click **"Confirm Update"** immediately (before the 15-minute token expires).

### 4. Watch Mode with Visible Browser Window
```bash
python main.py --watch --headed
```

### 5. Dry Run
Find the email and print the extracted link without clicking the button:
```bash
python main.py --dry-run
```

---

## ⏰ Setting Up a Cron Job (Run Every 2 Minutes)

You can set up a system cron job to run the script automatically in the background every 2 minutes.

Because cron triggers every 2 minutes, the script runs **only once** per trigger (default behavior when executed without `--watch`). It checks the inbox in ~1 second, confirms any pending Netflix email, marks it as read, and immediately exits.

### 1. Timestamped Logs

The code **automatically creates a new timestamped log file** in `logs/` on every execution (e.g., `logs/run_20261013_203000.log`). You do **not** need cron to append to a single monolithic log file.

### 2. Add the Cron Entry

Open your crontab:
```bash
crontab -e
```

Add the following line (using your absolute paths):

```cron
*/2 * * * * cd /Users/arnab.s/Desktop/gmail_automation && /Users/arnab.s/miniconda3/bin/python3 main.py >/dev/null 2>&1
```

> [!NOTE]
> * `*/2 * * * *` specifies execution every 2 minutes.
> * `cd /Users/arnab.s/Desktop/gmail_automation` ensures the script finds `.env`, outputs screenshots to `screenshots/`, and creates timestamped log files in `logs/`.
> * `main.py` runs a single check, purges old files, and exits immediately.
> * `>/dev/null 2>&1` silences shell redirection because the code manages its own timestamped log files.

### 3. Viewing Logs

* **List recent execution logs**:
  ```bash
  ls -lt logs/
  ```
* **View the latest execution log**:
  ```bash
  cat $(ls -td logs/*.log | head -1)
  ```
* **Live monitor the newest log**:
  ```bash
  tail -f $(ls -td logs/*.log | head -1)
  ```

---

## 🧹 Purging Old Screenshots & Logs (> 1 Week)

To prevent your disk from filling up over time with `.png` screenshots and `.log` execution files:

### Automatic Purging
Every time `main.py` executes (via cron or manually), it **automatically checks and deletes** screenshots in `screenshots/` and log files in `logs/` that are older than **7 days** (1 week).
* Retention duration can be configured in `.env` via `PURGE_DAYS=7` or CLI `--purge-days 7`.
* To disable auto-purge on a run, pass `--no-purge`.

### Manual Purge Script
You can also run the purge script directly at any time:

```bash
# Preview what files would be deleted (dry run)
python purge_old_files.py --dry-run

# Purge files older than 7 days
python purge_old_files.py --days 7

# Purge files older than 14 days
python purge_old_files.py --days 14
```

---

## 🧪 Running the Automated Test Suite

Run full unit and integration tests with `pytest`:

```bash
pytest -v
```

Tests cover:
- Decoding MIME headers and multipart payloads.
- HTML link extraction across various Netflix templates and edge cases.
- Playwright browser interactions with local mock web server (confirm, expired, already updated).
- End-to-end simulated pipeline.

---

## 📂 Project Structure

```
gmail_automation/
├── config.py                 # Configuration loader (.env and CLI options)
├── email_parser.py           # MIME email decoder and Netflix link extractor
├── gmail_client.py           # Gmail IMAP client for searching and fetching
├── browser_automator.py      # Playwright Chromium automation for "Confirm Update"
├── main.py                   # Main CLI entrypoint
├── .env.example              # Template configuration file
├── .gitignore                # Git ignore rules
├── README.md                 # Complete documentation
├── screenshots/              # Saved before/after screenshots
└── tests/
    ├── test_email_parser.py  # Unit tests for email parsing and link extraction
    ├── test_browser.py       # Integration tests with Playwright & mock server
    └── test_end_to_end.py    # Complete simulated end-to-end workflow test
```
