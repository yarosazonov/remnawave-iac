"""Archive encryption and decryption using tar + gpg."""

import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def create_encrypted_archive(dump_file: Path, password: str, prefix: str) -> Path | None:
    """Archives and encrypts a single dump file with AES256.
    
    Args:
        dump_file: Path to the dump file to archive
        password: Encryption password
        prefix: Archive name prefix (e.g., 'panel' or 'krisa-bot')
    
    Returns:
        Path to the encrypted archive, or None on failure
    """
    date_str = datetime.now().strftime("%d-%m-%y")
    output_dir = dump_file.parent
    archive_path = output_dir / f'{prefix}-{date_str}.tar.gz'
    encrypted_path = output_dir / f'{prefix}-{date_str}.tar.gz.gpg'
    
    tar_cmd = [
        'tar', '-czf', str(archive_path),
        '-C', str(output_dir),
        dump_file.name
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
        dump_file.unlink()
        
        logger.info(f"Encrypted archive created: {encrypted_path.name}")
        return encrypted_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Archive creation failed: {e}")
        return None


def decrypt_archive(encrypted_path: Path, password: str) -> Path:
    """Decrypts and extracts a .tar.gz.gpg backup archive.
    
    Returns:
        Path to the extracted dump file
    """
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
        
        # Find the extracted dump file (*.dump or *.db)
        dump_files = list(extract_dir.glob("*.dump")) + list(extract_dir.glob("*.db"))
        if not dump_files:
            raise FileNotFoundError(f"No dump file found in {extract_dir}")
        
        return dump_files[0]
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Decryption/extraction failed: {e.stderr.decode() if e.stderr else e}")
        raise

