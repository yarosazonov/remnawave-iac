"""Archive encryption and decryption using tar + gpg."""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def create_encrypted_archive(backup_dir: Path, password: str) -> Path | None:
    """Archives and encrypts a backup folder with AES256."""
    date_str = backup_dir.name
    archive_path = backup_dir.parent / f'{date_str}.tar.gz'
    encrypted_path = backup_dir.parent / f'{date_str}.tar.gz.gpg'
    
    tar_cmd = [
        'tar', '-czf', str(archive_path),
        '-C', str(backup_dir.parent),
        backup_dir.name
    ]
    
    gpg_cmd = [
        'gpg', '--batch', '--yes',
        '--passphrase-fd', '0',
        '--cipher-algo', 'AES256',
        '-c', '-o', str(encrypted_path),
        str(archive_path)
    ]
    
    try:
        subprocess.run(tar_cmd, check=True)
        subprocess.run(gpg_cmd, input=password.encode(), check=True)
        
        # Cleanup intermediate files
        archive_path.unlink()
        shutil.rmtree(backup_dir)
        
        logger.info(f"Encrypted archive created: {encrypted_path.name}")
        return encrypted_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Archive creation failed: {e}")
        return None


def decrypt_archive(encrypted_path: Path, password: str) -> Path:
    """Decrypts and extracts a .tar.gz.gpg backup archive."""
    encrypted_path = Path(encrypted_path)
    
    if not encrypted_path.exists():
        raise FileNotFoundError(f"Backup file not found: {encrypted_path}")
    
    if encrypted_path.suffix != '.gpg':
        raise ValueError(f"Expected .gpg file, got: {encrypted_path.suffix}")
    
    tar_path = encrypted_path.with_suffix('')
    extract_dir = encrypted_path.parent
    
    gpg_cmd = [
        'gpg', '--batch', '--yes',
        '--passphrase-fd', '0',
        '-d', '-o', str(tar_path),
        str(encrypted_path)
    ]
    
    tar_cmd = ['tar', '-xzf', str(tar_path), '-C', str(extract_dir)]
    
    try:
        subprocess.run(gpg_cmd, input=password.encode(), check=True, capture_output=True)
        logger.info(f"Decrypted archive: {tar_path.name}")
        
        subprocess.run(tar_cmd, check=True)
        logger.info(f"Extracted archive to: {extract_dir}")
        
        tar_path.unlink()
        
        backup_folder_name = encrypted_path.stem.replace('.tar.gz', '')
        return extract_dir / backup_folder_name
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Decryption/extraction failed: {e.stderr.decode() if e.stderr else e}")
        raise
