import os
import tempfile
import time
import pytest

from purge_old_files import purge_old_files


def test_purge_old_files():
    temp_dir = tempfile.mkdtemp()
    try:
        now = time.time()
        # 1. Recent file (1 day old)
        recent_png = os.path.join(temp_dir, "recent.png")
        with open(recent_png, "w") as f:
            f.write("recent image")
        os.utime(recent_png, (now - 86400, now - 86400))

        # 2. Old file (10 days old)
        old_png = os.path.join(temp_dir, "old.png")
        with open(old_png, "w") as f:
            f.write("old image")
        os.utime(old_png, (now - 10 * 86400, now - 10 * 86400))

        # 3. Old log file (8 days old)
        old_log = os.path.join(temp_dir, "old.log")
        with open(old_log, "w") as f:
            f.write("old log line")
        os.utime(old_log, (now - 8 * 86400, now - 8 * 86400))

        # 4. Old non-matching extension (e.g. .keep)
        old_keep = os.path.join(temp_dir, ".gitkeep")
        with open(old_keep, "w") as f:
            f.write("keep")
        os.utime(old_keep, (now - 10 * 86400, now - 10 * 86400))

        # Run purge with threshold of 7 days
        deleted = purge_old_files(target_dirs=[temp_dir], days=7, dry_run=False)

        assert old_png in deleted
        assert old_log in deleted
        assert recent_png not in deleted
        assert old_keep not in deleted

        # Verify physical files
        assert not os.path.exists(old_png)
        assert not os.path.exists(old_log)
        assert os.path.exists(recent_png)
        assert os.path.exists(old_keep)
    finally:
        for f in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, f))
            except Exception:
                pass
        os.rmdir(temp_dir)


def test_purge_dry_run():
    temp_dir = tempfile.mkdtemp()
    try:
        now = time.time()
        old_file = os.path.join(temp_dir, "test.log")
        with open(old_file, "w") as f:
            f.write("test")
        os.utime(old_file, (now - 10 * 86400, now - 10 * 86400))

        deleted = purge_old_files(target_dirs=[temp_dir], days=7, dry_run=True)
        assert old_file in deleted
        # File should still exist in dry-run mode
        assert os.path.exists(old_file)
    finally:
        if os.path.exists(old_file):
            os.remove(old_file)
        os.rmdir(temp_dir)
