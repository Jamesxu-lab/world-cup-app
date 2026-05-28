from pydantic_settings import BaseSettings
from functools import lru_cache


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

    # ChromaDB
    chroma_persist_dir: str = "./data/chromadb"

    # Redis (Celery broker, 生产环境使用)
    redis_url: str = "redis://localhost:6379/0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
