"""
Database connections for dual database architecture:
- Local: Research data, embeddings, sessions, experiments
- DDR Archive: Read-only access to archive metadata
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

# DDR Archive database (read-only)
ddr_engine = None
DDRSessionLocal = None

if settings.DDR_DATABASE_URL:
    ddr_engine = create_engine(
        settings.DDR_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
        # Read-only connection
        connect_args={"options": "-c default_transaction_read_only=on"}
    )
    DDRSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ddr_engine)

# Dependency for local database
def get_local_db():
    """Get local database session for research data"""
    db = LocalSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency for DDR archive database
def get_ddr_db():
    """Get DDR archive database session (read-only)"""
    if not DDRSessionLocal:
        raise Exception("DDR Archive database not configured")
    db = DDRSessionLocal()
    try:
        yield db
    finally:
        db.close()
