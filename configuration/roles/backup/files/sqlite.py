"""SQLite backup and restore via docker exec."""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SQLITE_CONTAINER = 'remnawave-tg-bot'
SQLITE_DB_PATH = '/app/data/db/bot.db'


def backup_sqlite(backup_dir: Path, date_str: str) -> Path | None:
    """Creates a SQLite backup using sqlite3 .backup command via docker exec."""
    backup_file = backup_dir / f"sqlite-backup-{date_str}.db"
    temp_path = '/tmp/sqlite_backup.db'
    
    # Use sqlite3 .backup inside container (safe, handles locks)
    backup_cmd = [
        'docker', 'exec', SQLITE_CONTAINER,
        'sqlite3', SQLITE_DB_PATH, f'.backup {temp_path}'
    ]
    
    # Copy the backup out of the container
    copy_cmd = ['docker', 'cp', f'{SQLITE_CONTAINER}:{temp_path}', str(backup_file)]
    
    try:
        subprocess.run(backup_cmd, check=True, capture_output=True)
        subprocess.run(copy_cmd, check=True, capture_output=True)
        logger.info("SQLite dump successful")
        return backup_file
    except subprocess.CalledProcessError as e:
        logger.error(f"SQLite dump failed: {e}")
        return None


def restore_sqlite(backup_dir: Path) -> bool:
    """Restores SQLite database from a backup file."""
    sqlite_files = list(backup_dir.glob("sqlite-backup-*.db"))
    
    if not sqlite_files:
        logger.error(f"No SQLite backup file found in {backup_dir}")
        return False
    
    backup_file = sqlite_files[0]
    logger.info(f"Restoring SQLite from: {backup_file.name}")
    
    temp_path = '/tmp/sqlite_restore.db'
    
    # Copy backup into container
    copy_cmd = ['docker', 'cp', str(backup_file), f'{SQLITE_CONTAINER}:{temp_path}']
    
    # Move to target location (overwrites existing)
    move_cmd = [
        'docker', 'exec', SQLITE_CONTAINER,
        'mv', temp_path, SQLITE_DB_PATH
    ]
    
    try:
        subprocess.run(copy_cmd, check=True, capture_output=True)
        subprocess.run(move_cmd, check=True, capture_output=True)
        logger.info("SQLite restore successful")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"SQLite restore failed: {e}")
        return False
