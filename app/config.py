"""Application settings loaded from .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings:
    # Site scraping
    site_username: str = os.getenv("SITE_USERNAME", "")
    site_password: str = os.getenv("SITE_PASSWORD", "")
    site_url: str = os.getenv("SITE_URL", "https://www.allagentreports.com")

    # App auth
    app_username: str = os.getenv("APP_USERNAME", "admin")
    app_password: str = os.getenv("APP_PASSWORD", "changeme")

    # Telegram
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Paths
    db_path: str = str(DATA_DIR / "book.db")
    chrome_profile: str = str(DATA_DIR / "chrome_profile")

    # Defaults (overridden by settings table at runtime)
    scrape_interval_minutes: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60"))
    payday_hour: int = int(os.getenv("PAYDAY_HOUR", "9"))


settings = Settings()
