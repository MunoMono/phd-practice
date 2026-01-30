from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    base_currency = Column(String, default="GBP")
    total_target = Column(Float, default=750000.0)
    tolerance_pct = Column(Float, default=5.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sleeves = relationship("Sleeve", back_populates="portfolio", cascade="all, delete-orphan")
    holdings = relationship("Holding", back_populates="portfolio", cascade="all, delete-orphan")
    income_records = relationship("IncomeRecord", back_populates="portfolio", cascade="all, delete-orphan")
    stock_positions = relationship("StockPosition", back_populates="portfolio", cascade="all, delete-orphan")

class Sleeve(Base):
    __tablename__ = "sleeves"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    name = Column(String)
    code = Column(String, index=True)  # defensive, equity, real, cash
    target_pct = Column(Float)
    
    portfolio = relationship("Portfolio", back_populates="sleeves")
    holdings = relationship("Holding", back_populates="sleeve")

class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    sleeve_id = Column(Integer, ForeignKey("sleeves.id"))
    ticker = Column(String, index=True)
    name = Column(String)
    target_pct = Column(Float)
    current_value = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="holdings")
    sleeve = relationship("Sleeve", back_populates="holdings")

class IncomeRecord(Base):
    __tablename__ = "income_records"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    date = Column(DateTime, default=datetime.utcnow)
    source = Column(String)  # dividend, coupon, distribution, rebalance, cash_buffer
    ticker = Column(String, nullable=True)
    amount = Column(Float)
    notes = Column(Text, nullable=True)

    portfolio = relationship("Portfolio", back_populates="income_records")

class StockPosition(Base):
    __tablename__ = "stock_positions"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    ticker = Column(String, index=True)
    company_name = Column(String)
    exchange = Column(String)  # LSE, HKEX, SGX
    country = Column(String)  # UK, HK, SG
    region = Column(String)  # UK, HK, SG
    sector = Column(String)
    role = Column(Text)  # e.g., "Defensive dividend compounder"
    basket_weight_pct = Column(Float)  # Weight within the stock basket (1/12 = 8.33%)
    portfolio_weight_pct = Column(Float)  # Weight in total portfolio (usually 5% / 12 = 0.417%)
    current_value = Column(Float, default=0.0)
    quantity = Column(Float, nullable=True)
    avg_price = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="stock_positions")
