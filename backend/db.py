import uuid
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    Boolean, DateTime, Text, JSON, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
from backend.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)


class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, default="queued")  # queued|ingesting|phase1|phase2|phase3|done|error
    markets = Column(JSON, default=["us"])
    sources = Column(JSON, default=[])
    query_config = Column(JSON, default={})
    runpod_job_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    item_count = Column(Integer, default=0)
    cluster_count = Column(Integer, default=0)
    video_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    r2_prefix = Column(String, nullable=True)


class RawContent(Base):
    __tablename__ = "raw_content"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    source = Column(String, nullable=False)
    content_id = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    text = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    market = Column(String, nullable=False)
    layer = Column(String, nullable=False)
    data_category = Column(String, nullable=False)
    engagement_score = Column(Float, default=0.0)
    cluster_id = Column(Integer, nullable=True)
    is_triaged = Column(Boolean, default=False)
    meta = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class ClusterRecord(Base):
    __tablename__ = "clusters"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    cluster_id = Column(Integer, nullable=False)
    cluster_type = Column(String, nullable=False)
    keywords = Column(JSON, default=[])
    sample_texts = Column(JSON, default=[])
    size = Column(Integer, default=0)
    sentiment = Column(Float, default=0.0)
    layer_mix = Column(JSON, default={})


class RecipeRecord(Base):
    __tablename__ = "recipes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    cluster_id = Column(Integer, nullable=False)
    market = Column(String, nullable=False)
    recipe = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    message = Column(Text, nullable=False)
    level = Column(String, default="info")
    created_at = Column(DateTime, default=datetime.utcnow)
