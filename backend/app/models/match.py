import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Match(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, default=gen_uuid)
    fixture_id = Column(Integer, unique=True, nullable=False, index=True)
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    match_date = Column(DateTime, nullable=False, index=True)
    group_name = Column(String(50), nullable=True)
    round = Column(String(50), nullable=True, default="group_stage")
    stadium = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="scheduled")
    created_at = Column(DateTime, default=datetime.utcnow)

    events = relationship("MatchEvent", back_populates="match", cascade="all, delete-orphan")
    stats = relationship("MatchStat", back_populates="match", cascade="all, delete-orphan")
    performances = relationship("PlayerPerformance", back_populates="match", cascade="all, delete-orphan")
    narratives = relationship("Narrative", back_populates="match", cascade="all, delete-orphan")


class MatchEvent(Base):
    __tablename__ = "match_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    minute = Column(Integer, nullable=False)
    extra_minute = Column(Integer, nullable=True)
    event_type = Column(String(30), nullable=False)
    detail = Column(String(200), nullable=True)
    player_name = Column(String(100), nullable=True)
    team = Column(String(100), nullable=True)
    assist_player = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="events")


class MatchStat(Base):
    __tablename__ = "match_stats"

    id = Column(String, primary_key=True, default=gen_uuid)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    team = Column(String(100), nullable=False)
    stat_type = Column(String(50), nullable=False)
    stat_value = Column(Float, nullable=True)

    match = relationship("Match", back_populates="stats")


class PlayerPerformance(Base):
    __tablename__ = "player_performances"

    id = Column(String, primary_key=True, default=gen_uuid)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    player_name = Column(String(100), nullable=False)
    team = Column(String(100), nullable=False)
    position = Column(String(50), nullable=True)
    rating = Column(Float, nullable=True)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    stats_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="performances")


class Narrative(Base):
    __tablename__ = "narratives"

    id = Column(String, primary_key=True, default=gen_uuid)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    style = Column(String(20), nullable=False)          # formal / funny / tactical
    card_index = Column(Integer, nullable=False)         # 卡片序号 1-8
    card_type = Column(String(30), nullable=True)        # overview / key_moment / player / stats / ...
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=True)
    model_version = Column(String(20), nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="narratives")
