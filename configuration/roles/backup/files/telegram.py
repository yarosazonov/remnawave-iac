"""Send files to Telegram via Bot API using requests."""

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def send_document(token: str, chat_id: str, file_path: Path, caption: str = "") -> bool:
    """Send a document to Telegram chat via Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"document": f},
                timeout=120  # Large files may take time
            )
        
        if response.ok:
            logger.info(f"Sent backup to Telegram: {file_path.name}")
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Failed to send to Telegram: {e}")
        return False
