from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
BACKEND_ENV_FILE = BACKEND_DIR / ".env"


def resolve_database_url(database_url: str) -> str:
    """Resolve relative SQLite database URLs from the backend directory."""
    if database_url == "sqlite:///:memory:":
        return database_url
    if not database_url.startswith("sqlite:///") or database_url.startswith("sqlite:////"):
        return database_url

    raw_path = database_url.removeprefix("sqlite:///")
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = BACKEND_DIR / db_path
    return f"sqlite:///{db_path}"


class Settings(BaseSettings):
    # API-Football
    api_football_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    chat_model: str = ""  # 聊天专用模型（可选，默认复用 llm_model）

    # Database
    database_url: str = "sqlite:///./data/worldcup.db"

    # Match sync
    app_timezone: str = "Asia/Shanghai"
    sync_yesterday_on_startup: bool = True
    sync_startup_with_details: bool = False

    # Prediction snapshot sync
    prediction_sync_on_startup: bool = True
    prediction_sync_block_startup: bool = False
    prediction_sync_max_age_hours: int = 24
    prediction_sync_daily_enabled: bool = False
    prediction_sync_daily_time: str = "10:00"
    prediction_sync_injuries_path: str = ""

    # ChromaDB
    chroma_persist_dir: str = "./data/chromadb"

    # Redis (Celery broker, 生产环境使用)
    redis_url: str = "redis://localhost:6379/0"

    model_config = {"env_file": BACKEND_ENV_FILE, "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
