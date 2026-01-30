from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Sleeve schemas
class SleeveBase(BaseModel):
    name: str
    code: str
    target_pct: float

class SleeveCreate(SleeveBase):
    pass

class Sleeve(SleeveBase):
    id: int
    portfolio_id: int

    class Config:
        from_attributes = True

# Holding schemas
class HoldingBase(BaseModel):
    ticker: str
    name: str
    target_pct: float
    current_value: float = 0.0
    notes: Optional[str] = None

class HoldingCreate(HoldingBase):
    sleeve_id: int

class HoldingUpdate(BaseModel):
    ticker: Optional[str] = None
    name: Optional[str] = None
    target_pct: Optional[float] = None
    current_value: Optional[float] = None
    notes: Optional[str] = None
    sleeve_id: Optional[int] = None

class Holding(HoldingBase):
    id: int
    portfolio_id: int
    sleeve_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Portfolio schemas
class PortfolioBase(BaseModel):
    name: str
    base_currency: str = "GBP"
    total_target: float = 750000.0
    tolerance_pct: float = 5.0

class PortfolioCreate(PortfolioBase):
    sleeves: List[SleeveCreate] = []

class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    total_target: Optional[float] = None
    tolerance_pct: Optional[float] = None

class Portfolio(PortfolioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PortfolioDetail(Portfolio):
    sleeves: List[Sleeve] = []
    holdings: List[Holding] = []

    class Config:
        from_attributes = True

# Income record schemas
class IncomeRecordBase(BaseModel):
    source: str
    ticker: Optional[str] = None
    amount: float
    notes: Optional[str] = None

class IncomeRecordCreate(IncomeRecordBase):
    date: Optional[datetime] = None

class IncomeRecord(IncomeRecordBase):
    id: int
    portfolio_id: int
    date: datetime

    class Config:
        from_attributes = True

# Stock position schemas
class StockPositionBase(BaseModel):
    ticker: str
    company_name: str
    exchange: str
    country: str
    region: str
    sector: str
    role: str
    basket_weight_pct: float
    portfolio_weight_pct: float
    current_value: float = 0.0
    quantity: Optional[float] = None
    avg_price: Optional[float] = None
    notes: Optional[str] = None

class StockPositionCreate(StockPositionBase):
    pass

class StockPositionUpdate(BaseModel):
    current_value: Optional[float] = None
    quantity: Optional[float] = None
    avg_price: Optional[float] = None
    notes: Optional[str] = None

class StockPosition(StockPositionBase):
    id: int
    portfolio_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
