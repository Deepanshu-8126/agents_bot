import os
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import timezone, timedelta

def _load_env():
    env_file = Path(".env")
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

_load_env()

# Database
DB_PATH = os.getenv("JOB_HUNTER_DB", "job_hunter.db")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Location defaults
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Haldwani")
DEFAULT_RADIUS_KM = int(os.getenv("DEFAULT_RADIUS_KM", "100"))

# Time & Filters
try:
    TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Kolkata"))
except Exception:
    TZ = timezone(timedelta(hours=5, minutes=30))

DEFAULT_HOURS_OLD = int(os.getenv("HOURS_OLD", "168"))
MAX_JOBS_PER_ALERT = int(os.getenv("MAX_JOBS", "25"))
