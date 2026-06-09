"""
Database connection and session management.
Synchronous SQLAlchemy 2.0 setup.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from backend.config import DATABASE_URL
from backend.db.models import Base


# Create engine (synchronous)
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session
)


def get_session() -> Session:
    """Get a database session."""
    return SessionLocal()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all tables with CASCADE to handle any residual FK constraints."""
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    # Discard pooled connections: their type OID caches are stale after schema drop.
    engine.dispose()
