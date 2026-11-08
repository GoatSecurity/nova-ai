import os
import sys
import logging
import json
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from backend.app.core.config import settings

LOGS_FILE = settings.LOGS_DIR / "nova.log"
AUDIT_LOGS_FILE = settings.LOGS_DIR / "audit.log"

class SanitizingFormatter(logging.Formatter):
    """Formatter that strips out API keys and credentials before emitting logs"""
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        # Redact obvious token patterns
        import re
        msg = re.sub(r'(sk-[A-Za-z0-9_\-]{16,})', r'sk-...[REDACTED]', msg)
        msg = re.sub(r'(gsk_[A-Za-z0-9_\-]{16,})', r'gsk_...[REDACTED]', msg)
        msg = re.sub(r'(Bearer\s+[A-Za-z0-9_\.\-]{16,})', r'Bearer [REDACTED]', msg)
        return msg

def setup_logging():
    logger = logging.getLogger("nova")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers on reload
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_fmt = SanitizingFormatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(module)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    # File handler with rotation (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        LOGS_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_fmt = SanitizingFormatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S"
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    return logger

logger = setup_logging()

def audit_log(event_type: str, actor: str, details: dict):
    """
    Appends an immutable audit event to audit.log
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "actor": actor,
        "details": details
    }
    try:
        with open(AUDIT_LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
