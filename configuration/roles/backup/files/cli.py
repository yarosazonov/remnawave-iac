"""CLI entry point for backup and restore operations."""

import argparse
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from postgres import backup_postgres, restore_postgres
from sqlite import backup_sqlite, restore_sqlite
from archive import create_encrypted_archive, decrypt_archive
from cleanup import cleanup_old_backups
from telegram import send_document

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

BACKUPS_DIR = Path('/opt/remnawave-backups/data')

BACKUP_CONFIG = {
    'panel': {
        'backup_func': backup_postgres,
        'restore_func': restore_postgres,
        'caption': '🗄️ Panel Backup',
    },
    'krisa-bot': {
        'backup_func': backup_sqlite,
        'restore_func': restore_sqlite,
        'caption': '🗄️ Krisa-Bot Backup',
    },
}


def run_backup(backup_type: str) -> None:
    """Performs a backup and sends to admin.
    
    Args:
        backup_type: 'panel' or 'krisa-bot'
    """
    bot_token = os.environ.get('BOT_TOKEN')
    admin_id = os.environ.get('ADMIN_ID')
    backup_password = os.environ.get('BACKUP_PASSWORD')
    retention_days = int(os.environ.get('BACKUP_RETENTION_DAYS', '7'))
    
    if not all([bot_token, admin_id, backup_password]):
        logger.error("Missing required env vars: BOT_TOKEN, ADMIN_ID, BACKUP_PASSWORD")
        return
    
    date_str = datetime.now().strftime("%d-%m-%y")
    
    try:
        config = BACKUP_CONFIG[backup_type]
        dump_file = config['backup_func'](BACKUPS_DIR, date_str)
        
        if not dump_file:
            logger.error(f"{backup_type} backup: dump creation failed")
            return
        
        archive_path = create_encrypted_archive(dump_file, backup_password, prefix=backup_type)
        
        if archive_path:
            caption = f"{config['caption']} {date_str}"
            send_document(bot_token, admin_id, archive_path, caption)
            cleanup_old_backups(BACKUPS_DIR, retention_days)
            logger.info(f"{backup_type} backup completed successfully")
    except Exception as e:
        logger.error(f"{backup_type} backup failed: {e}")


def run_restore(encrypted_path: str, backup_type: str) -> bool:
    """Restores database from an encrypted backup.
    
    Args:
        encrypted_path: Path to the .gpg backup file
        backup_type: 'panel' or 'krisa-bot'
    """
    backup_password = os.environ.get('BACKUP_PASSWORD')
    
    if not backup_password:
        logger.error("Missing required env var: BACKUP_PASSWORD")
        return False
    
    logger.info(f"Starting {backup_type} restore from: {encrypted_path}")
    
    try:
        dump_file = decrypt_archive(Path(encrypted_path), backup_password)
        logger.info(f"Dump file extracted: {dump_file}")
        
        config = BACKUP_CONFIG[backup_type]
        success = config['restore_func'](dump_file)
        
        # Cleanup extracted dump file
        if dump_file.exists():
            dump_file.unlink()
            logger.info("Cleaned up extracted dump file")
        
        return success  
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description='Backup and restore utility')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create backup and send to admin')
    backup_group = backup_parser.add_mutually_exclusive_group(required=True)
    backup_group.add_argument('--panel', action='store_true', help='Backup panel (PostgreSQL)')
    backup_group.add_argument('--krisa-bot', action='store_true', help='Backup Krisa bot (SQLite)')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('backup_file', help='Path to .gpg backup file')
    restore_group = restore_parser.add_mutually_exclusive_group(required=True)
    restore_group.add_argument('--panel', action='store_true', help='Restore panel (PostgreSQL)')
    restore_group.add_argument('--krisa-bot', action='store_true', help='Restore Krisa bot (SQLite)')
    
    args = parser.parse_args()
    
    if args.command == 'backup':
        if args.panel:
            backup_type = 'panel'
        # argparse automatically converts hyphens to underscores
        elif args.krisa_bot:
            backup_type = 'krisa-bot'
        run_backup(backup_type)
    elif args.command == 'restore':
        if args.panel:
            backup_type = 'panel'
        elif args.krisa_bot:
            backup_type = 'krisa-bot'
        success = run_restore(args.backup_file, backup_type)
        if not success:
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
