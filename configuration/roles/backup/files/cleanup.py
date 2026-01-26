"""Cleanup old backup files based on retention policy."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_old_backups(backups_dir: Path, retention_days: int) -> int:
    """Delete .gpg backup files older than retention_days based on filename date."""
    if retention_days <= 0:
        logger.debug("Backup cleanup disabled (retention_days <= 0)")
        return 0
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0
    
    for gpg_file in backups_dir.glob("*.tar.gz.gpg"):
        # Parse "14-01-26" from "14-01-26.tar.gz.gpg"
        date_str = gpg_file.name.split(".")[0]
        try:
            file_date = datetime.strptime(date_str, "%d-%m-%y")
            if file_date < cutoff_date:
                gpg_file.unlink()
                logger.info(f"Deleted old backup: {gpg_file.name}")
                deleted_count += 1
        except ValueError:
            logger.debug(f"Skipping file with non-standard name: {gpg_file.name}")
            continue
    
    if deleted_count > 0:
        logger.info(f"Cleanup complete: {deleted_count} old backup(s) removed")
    
    return deleted_count
