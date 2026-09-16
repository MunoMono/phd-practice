"""
Database connection for local PostgreSQL database.
Stores research data, embeddings, sessions, experiments, and digital assets.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# Local database (read/write)
local_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)
LocalSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)
LocalBase = declarative_base()


# Dependency for local database
def get_local_db():
    """Get local database session for research data"""
    db = LocalSessionLocal()
    try:
        yield db
    finally:
        db.close()
