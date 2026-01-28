"""PostgreSQL backup and restore via docker exec."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

POSTGRES_CONTAINER = 'remnawave-db'
POSTGRES_USER = 'postgres'
POSTGRES_DB = 'postgres'


def backup_postgres(backup_dir: Path, date_str: str) -> Path | None:
    """Creates a PostgreSQL dump using pg_dump."""
    backup_file = backup_dir / f"postgres-backup-{date_str}.dump"
    cmd = [
        'docker', 'exec', '-i', POSTGRES_CONTAINER,
        'pg_dump', '-U', POSTGRES_USER, '-d', POSTGRES_DB, '-Fc'
    ]
    
    try:
        with open(backup_file, "wb") as f:
            subprocess.run(cmd, stdout=f, check=True)
        logger.info("PostgreSQL dump successful")
        return backup_file
    except subprocess.CalledProcessError as e:
        logger.error(f"PostgreSQL dump failed: {e}")
        return None


def restore_postgres(dump_file: Path) -> bool:
    """Restores PostgreSQL from a dump file.
    
    Args:
        dump_file: Path to the PostgreSQL dump file
    """
    if not dump_file.exists():
        logger.error(f"Dump file not found: {dump_file}")
        return False
    
    logger.info(f"Restoring PostgreSQL from: {dump_file.name}")
    
    # Terminate existing connections
    drop_cmd = [
        'docker', 'exec', '-i', POSTGRES_CONTAINER,
        'psql', '-U', POSTGRES_USER, '-c',
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{POSTGRES_DB}' AND pid <> pg_backend_pid();"
    ]
    
    # Drop and recreate public schema (wipe database)
    cleanup_cmd = [
        'docker', 'exec', '-i', POSTGRES_CONTAINER,
        'psql', '-U', POSTGRES_USER, '-d', POSTGRES_DB, '-c',
        "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO public;"
    ]
    
    restore_cmd = [
        'docker', 'exec', '-i', POSTGRES_CONTAINER,
        'pg_restore', '-U', POSTGRES_USER, '-d', POSTGRES_DB,
        '--clean', '--if-exists', '--no-owner', '--no-privileges'
    ]
    
    try:
        subprocess.run(drop_cmd, capture_output=True)
        
        # Run cleanup
        logger.info("Wiping existing database content...")
        cleanup_result = subprocess.run(cleanup_cmd, capture_output=True)
        if cleanup_result.returncode != 0:
            logger.error(f"Failed to wipe database: {cleanup_result.stderr.decode()}")
            return False
            
        with open(dump_file, 'rb') as f:
            result = subprocess.run(restore_cmd, stdin=f, capture_output=True)
        
        if result.returncode != 0:
            stderr = result.stderr.decode() if result.stderr else ''
            if 'ERROR' in stderr and 'already exists' not in stderr and 'does not exist' not in stderr:
                logger.error(f"PostgreSQL restore failed: {stderr}")
                return False
            logger.warning(f"PostgreSQL restore completed with warnings")
        
        logger.info("PostgreSQL restore successful")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"PostgreSQL restore failed: {e}")
        return False
