from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import get_settings, resolve_database_url

settings = get_settings()
database_url = resolve_database_url(settings.database_url)

engine = create_engine(
    database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表"""
    from app.models import match  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_match_score_columns()


def _ensure_match_score_columns():
    """Add nullable score columns that older SQLite DB files may not have."""
    if not database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    existing_columns = {column["name"] for column in inspector.get_columns("matches")}
    missing_columns = [
        ("penalty_home_score", "INTEGER"),
        ("penalty_away_score", "INTEGER"),
    ]

    with engine.begin() as conn:
        for column_name, column_type in missing_columns:
            if column_name not in existing_columns:
                conn.execute(text(f"ALTER TABLE matches ADD COLUMN {column_name} {column_type}"))
