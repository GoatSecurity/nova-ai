import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "NOVA"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"
    
    # Server network settings
    HOST: str = "127.0.0.1"
    PORT: int = 46815
    ALLOW_LAN: bool = False
    ALLOWED_ORIGINS: List[str] = [
        "http://127.0.0.1:46815",
        "http://localhost:46815",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
    
    # Storage and paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    LOGS_DIR: Path = LOGS_DIR
    DATABASE_PATH: Path = DATA_DIR / "nova.db"
    STATIC_DIR: Path = BASE_DIR / "frontend" / "dist"
    ATTACHMENTS_DIR: Path = DATA_DIR / "attachments"
    
    # Execution & Security
    DEFAULT_PERMISSION_MODE: str = "allow_safe"  # "ask_every_time", "allow_safe", "session_approval", "manual"
    DEFAULT_EXECUTION_TIMEOUT: int = 1800  # 30 minutes for deep research & heavy tasks
    MAX_OUTPUT_BYTES: int = 500_000  # 500 KB cap on terminal output
    MAX_AGENT_ITERATIONS: int = 50  # allow thorough multi-step reasoning without premature stop
    SCRATCH_DIR: Path = BASE_DIR / "scratch"
    DEFAULT_WORKSPACE: str = str(BASE_DIR / "scratch")
    
    # Agent Context limits
    MAX_CONTEXT_TOKENS: int = 32000
    RESERVE_TOKENS_FOR_RESPONSE: int = 4096
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
settings.ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
