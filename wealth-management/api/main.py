from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import os

from . import models, schemas, crud
from .database import engine, get_db
from .constraints import validate_portfolio_constraints
from .analytics import generate_portfolio_analytics

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Wealth Management API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Wealth Management API v1.0.0", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Portfolio endpoints
@app.post("/api/portfolios/", response_model=schemas.Portfolio)
def create_portfolio(portfolio: schemas.PortfolioCreate, db: Session = Depends(get_db)):
    return crud.create_portfolio(db=db, portfolio=portfolio)

@app.get("/api/portfolios/", response_model=List[schemas.Portfolio])
def get_portfolios(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    portfolios = crud.get_portfolios(db, skip=skip, limit=limit)
    return portfolios

@app.get("/api/portfolios/{portfolio_id}", response_model=schemas.PortfolioDetail)
def get_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    db_portfolio = crud.get_portfolio(db, portfolio_id=portfolio_id)
    if db_portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return db_portfolio

@app.put("/api/portfolios/{portfolio_id}", response_model=schemas.Portfolio)
def update_portfolio(portfolio_id: int, portfolio: schemas.PortfolioUpdate, db: Session = Depends(get_db)):
    db_portfolio = crud.update_portfolio(db, portfolio_id=portfolio_id, portfolio=portfolio)
    if db_portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return db_portfolio

# Holding endpoints
@app.post("/api/portfolios/{portfolio_id}/holdings/", response_model=schemas.Holding)
def create_holding(portfolio_id: int, holding: schemas.HoldingCreate, db: Session = Depends(get_db)):
    return crud.create_holding(db=db, holding=holding, portfolio_id=portfolio_id)

@app.get("/api/portfolios/{portfolio_id}/holdings/", response_model=List[schemas.Holding])
def get_holdings(portfolio_id: int, db: Session = Depends(get_db)):
    return crud.get_holdings(db, portfolio_id=portfolio_id)

@app.put("/api/holdings/{holding_id}", response_model=schemas.Holding)
def update_holding(holding_id: int, holding: schemas.HoldingUpdate, db: Session = Depends(get_db)):
    db_holding = crud.update_holding(db, holding_id=holding_id, holding=holding)
    if db_holding is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    return db_holding

@app.delete("/api/holdings/{holding_id}")
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    success = crud.delete_holding(db, holding_id=holding_id)
    if not success:
        raise HTTPException(status_code=404, detail="Holding not found")
    return {"message": "Holding deleted successfully"}

# Validation endpoint
@app.post("/api/portfolios/{portfolio_id}/validate")
def validate_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    db_portfolio = crud.get_portfolio(db, portfolio_id=portfolio_id)
    if db_portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    validation_results = validate_portfolio_constraints(db_portfolio)
    return validation_results

# Analytics endpoint
@app.get("/api/portfolios/{portfolio_id}/analytics")
def get_portfolio_analytics(portfolio_id: int, db: Session = Depends(get_db)):
    db_portfolio = crud.get_portfolio(db, portfolio_id=portfolio_id)
    if db_portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    analytics = generate_portfolio_analytics(db_portfolio)
    return analytics

# Income tracking endpoints
@app.post("/api/portfolios/{portfolio_id}/income/", response_model=schemas.IncomeRecord)
def record_income(portfolio_id: int, income: schemas.IncomeRecordCreate, db: Session = Depends(get_db)):
    return crud.create_income_record(db=db, income=income, portfolio_id=portfolio_id)

@app.get("/api/portfolios/{portfolio_id}/income/", response_model=List[schemas.IncomeRecord])
def get_income_records(portfolio_id: int, db: Session = Depends(get_db)):
    return crud.get_income_records(db, portfolio_id=portfolio_id)

# Stock basket endpoints
@app.get("/api/portfolios/{portfolio_id}/stock-basket/", response_model=List[schemas.StockPosition])
def get_stock_basket(portfolio_id: int, db: Session = Depends(get_db)):
    return crud.get_stock_basket(db, portfolio_id=portfolio_id)

@app.post("/api/portfolios/{portfolio_id}/stock-basket/", response_model=schemas.StockPosition)
def add_stock_to_basket(portfolio_id: int, stock: schemas.StockPositionCreate, db: Session = Depends(get_db)):
    return crud.create_stock_position(db=db, stock=stock, portfolio_id=portfolio_id)

@app.put("/api/stock-basket/{stock_id}", response_model=schemas.StockPosition)
def update_stock_position(stock_id: int, stock: schemas.StockPositionUpdate, db: Session = Depends(get_db)):
    db_stock = crud.update_stock_position(db, stock_id=stock_id, stock=stock)
    if db_stock is None:
        raise HTTPException(status_code=404, detail="Stock position not found")
    return db_stock

@app.delete("/api/stock-basket/{stock_id}")
def delete_stock_position(stock_id: int, db: Session = Depends(get_db)):
    success = crud.delete_stock_position(db, stock_id=stock_id)
    if not success:
        raise HTTPException(status_code=404, detail="Stock position not found")
    return {"message": "Stock position deleted successfully"}
