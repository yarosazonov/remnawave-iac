"""SQLite backup and restore via docker exec."""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SQLITE_CONTAINER = 'krisa-bot'
SQLITE_DB_PATH = '/app/data/db/bot.db'


def backup_sqlite(backup_dir: Path, date_str: str) -> Path | None:
    """Creates a SQLite backup using sqlite3 .backup command via docker exec."""
    backup_file = backup_dir / f"sqlite-backup-{date_str}.db"
    temp_path = '/tmp/sqlite_backup.db'
    
    # Use python to backup (since sqlite3 cli is not present in python slim)
    backup_script = (
        f"import sqlite3; "
        f"src = sqlite3.connect('{SQLITE_DB_PATH}'); "
        f"dst = sqlite3.connect('{temp_path}'); "
        f"src.backup(dst); "
        f"dst.close(); src.close()"
    )
    
    backup_cmd = [
        'docker', 'exec', SQLITE_CONTAINER,
        'python', '-c', backup_script
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


def restore_sqlite(dump_file: Path) -> bool:
    """Restores SQLite database from a backup file.
    
    Args:
        dump_file: Path to the SQLite backup file
    """
    if not dump_file.exists():
        logger.error(f"Backup file not found: {dump_file}")
        return False
    
    logger.info(f"Restoring SQLite from: {dump_file.name}")
    
    temp_path = '/tmp/sqlite_restore.db'
    
    # Copy backup into container
    copy_cmd = ['docker', 'cp', str(dump_file), f'{SQLITE_CONTAINER}:{temp_path}']
    
    # Use python to restore safely (handles locks/WAL/permissions natively)
    restore_script = (
        f"import sqlite3; "
        f"bck = sqlite3.connect('{temp_path}'); "
        f"live = sqlite3.connect('{SQLITE_DB_PATH}'); "
        f"bck.backup(live); "
        f"live.close(); bck.close()"
    )
    
    restore_cmd = [
        'docker', 'exec', '-u', '0', SQLITE_CONTAINER,
        'python', '-c', restore_script
    ]

    cleanup_cmd = [
        'docker', 'exec', '-u', '0', SQLITE_CONTAINER,
        'rm', temp_path
    ]
    
    try:
        subprocess.run(copy_cmd, check=True, capture_output=True)
        subprocess.run(restore_cmd, check=True, capture_output=True)
        logger.info("SQLite restore successful")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"SQLite restore failed: {e}")
        if e.stderr:
            logger.error(f"STDERR: {e.stderr.decode()}")
        return False
    finally:
        # Always cleanup temp file
        try:
            subprocess.run(cleanup_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logger.warning(f"Failed to cleanup temp file: {temp_path}")
