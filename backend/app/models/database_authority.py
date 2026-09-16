from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import LocalBase


class DatabaseAuthority(LocalBase):
    __tablename__ = 'database_authorities'

    id = Column(Integer, primary_key=True, index=True)
    authority_type = Column(String(50), nullable=False, index=True)
    authority_id = Column(String(100), nullable=False)
    code = Column(String(100), nullable=True)
    label = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(20), nullable=False, index=True)
    metadata_json = Column('metadata', JSONB, nullable=False, default=dict)
    synced_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())