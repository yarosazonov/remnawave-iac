"""CLI entry point for backup and restore operations."""

import argparse
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from .postgres import backup_postgres, restore_postgres
from .sqlite import backup_sqlite, restore_sqlite
from .archive import create_encrypted_archive, decrypt_archive
from .cleanup import cleanup_old_backups
from .telegram import send_document

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

BACKUPS_DIR = Path('/opt/remnawave-backups/data')


def run_backup() -> Path | None:
    """Performs a full backup and sends to admin."""
    # Read config from environment
    bot_token = os.environ.get('BOT_TOKEN')
    admin_id = os.environ.get('ADMIN_ID')
    backup_password = os.environ.get('BACKUP_PASSWORD')
    retention_days = int(os.environ.get('BACKUP_RETENTION_DAYS', '7'))
    
    if not all([bot_token, admin_id, backup_password]):
        logger.error("Missing required env vars: BOT_TOKEN, ADMIN_ID, BACKUP_PASSWORD")
        return None
    
    date_str = datetime.now().strftime("%d-%m-%y")
    backup_dir = BACKUPS_DIR / date_str
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Backup both databases
    backup_postgres(backup_dir, date_str)
    backup_sqlite(backup_dir, date_str)
    
    # Create encrypted archive
    archive_path = create_encrypted_archive(backup_dir, backup_password)
    
    if archive_path:
        # Send to Telegram
        caption = f"🗄️ Backup {date_str}"
        send_document(bot_token, admin_id, archive_path, caption)
        
        # Cleanup old backups
        cleanup_old_backups(BACKUPS_DIR, retention_days)
    
    return archive_path


def run_restore(encrypted_path: str, postgres_only: bool = False, sqlite_only: bool = False) -> bool:
    """Restores databases from an encrypted backup."""
    backup_password = os.environ.get('BACKUP_PASSWORD')
    
    if not backup_password:
        logger.error("Missing required env var: BACKUP_PASSWORD")
        return False
    
    logger.info(f"Starting restore from: {encrypted_path}")
    
    try:
        backup_dir = decrypt_archive(Path(encrypted_path), backup_password)
        logger.info(f"Backup extracted to: {backup_dir}")
        
        success = True
        
        if not sqlite_only:
            if not restore_postgres(backup_dir):
                success = False
        
        if not postgres_only:
            if not restore_sqlite(backup_dir):
                logger.warning("SQLite restore failed, but continuing anyway")
        
        # Cleanup
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
            logger.info("Cleaned up extracted backup directory")
        
        return success
        
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description='Backup and restore utility')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    subparsers.add_parser('backup', help='Create backup and send to admin')
    
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('backup_file', help='Path to .gpg backup file')
    restore_parser.add_argument('--postgres-only', action='store_true')
    restore_parser.add_argument('--sqlite-only', action='store_true')
    
    args = parser.parse_args()
    
    if args.command == 'backup' or args.command is None:
        run_backup()
    elif args.command == 'restore':
        success = run_restore(
            args.backup_file,
            postgres_only=args.postgres_only,
            sqlite_only=args.sqlite_only
        )
        if not success:
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
