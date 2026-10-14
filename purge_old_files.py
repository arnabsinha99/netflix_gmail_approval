import argparse
import logging
import os
import time
from typing import List, Optional

from config import config

logger = logging.getLogger("purge")


def purge_old_files(
    target_dirs: Optional[List[str]] = None,
    days: int = 7,
    dry_run: bool = False,
    extensions: Optional[List[str]] = None,
) -> List[str]:
    """
    Deletes files in target_dirs that are older than specified days.
    Default targets: screenshots (*.png) and logs (*.log).
    Returns list of deleted (or would-be deleted) file paths.
    """
    if target_dirs is None:
        target_dirs = [config.screenshots_dir, config.logs_dir]

    if extensions is None:
        extensions = [".png", ".log"]

    cutoff_seconds = time.time() - (days * 86400)
    deleted_files = []
    freed_bytes = 0

    for directory in target_dirs:
        if not os.path.exists(directory):
            continue

        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)

            # Skip subdirectories and special keep files
            if not os.path.isfile(filepath) or filename.startswith("."):
                continue

            # Check file extension filter
            _, ext = os.path.splitext(filename)
            if extensions and ext.lower() not in extensions:
                continue

            try:
                mtime = os.path.getmtime(filepath)
                file_size = os.path.getsize(filepath)

                if mtime < cutoff_seconds:
                    age_days = (time.time() - mtime) / 86400.0
                    if dry_run:
                        logger.info(
                            f"[DRY-RUN] Would delete: {filepath} "
                            f"(Age: {age_days:.1f} days, Size: {file_size} bytes)"
                        )
                    else:
                        os.remove(filepath)
                        logger.info(
                            f"Deleted: {filepath} "
                            f"(Age: {age_days:.1f} days, Size: {file_size} bytes)"
                        )
                    deleted_files.append(filepath)
                    freed_bytes += file_size
            except Exception as e:
                logger.error(f"Error checking/deleting file {filepath}: {e}")

    action_word = "Would purge" if dry_run else "Purged"
    mb_freed = freed_bytes / (1024 * 1024)
    logger.info(
        f"{action_word} {len(deleted_files)} file(s) older than {days} days "
        f"({mb_freed:.2f} MB freed)."
    )
    return deleted_files


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Purge screenshots (.png) and logs (.log) older than a specified duration.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--days",
        type=int,
        default=config.purge_days,
        help="Age threshold in days. Files older than this will be purged.",
    )
    parser.add_argument(
        "--dirs",
        nargs="+",
        default=[config.screenshots_dir, config.logs_dir],
        help="Directories to clean up.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be deleted without actually removing them.",
    )

    args = parser.parse_args()
    purge_old_files(target_dirs=args.dirs, days=args.days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
