from sqlalchemy.orm import Session
from . import models, schemas

# Portfolio CRUD
def get_portfolio(db: Session, portfolio_id: int):
    return db.query(models.Portfolio).filter(models.Portfolio.id == portfolio_id).first()

def get_portfolios(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Portfolio).offset(skip).limit(limit).all()

def create_portfolio(db: Session, portfolio: schemas.PortfolioCreate):
    db_portfolio = models.Portfolio(
        name=portfolio.name,
        base_currency=portfolio.base_currency,
        total_target=portfolio.total_target,
        tolerance_pct=portfolio.tolerance_pct
    )
    db.add(db_portfolio)
    db.commit()
    db.refresh(db_portfolio)
    
    # Create sleeves
    for sleeve in portfolio.sleeves:
        db_sleeve = models.Sleeve(
            portfolio_id=db_portfolio.id,
            name=sleeve.name,
            code=sleeve.code,
            target            target            target            target            target            target es            target            tartf            target          b:             tarli            target        mas.PortfolioUpdate):
                                                                                           Non                                                                fo                                                                    ey, value)
    
    db.commit()
    db.refresh(db_portfolio)
    return db    return db    return db    rett_ho    return db    return db io    return db    return db    return db    re).filter(models.Holding.portfolio_id == portfolio_id).all()

def create_holding(db: Session, holdindef create_holdingCreate,def creato_id: idef create_holding(db: Sesss.Holdidef create_ **holdingdef create_holding(db: Session, hololdef create_holding(db: Sessioning)
def create_holding(db: Session, holdindeg)def create_holding(db: Sess updef create_holding(db: Sessilddef create_holding(db: Session, holdindeg)def create_holding(db: Sess updef create_holding(db: Sessilddef create_holding(db: Session, holdindeg)def create_holding(db: Sess updef create_holding(db: Sessilddef create_holding(db: Session, holdordef create_holding(db: Session, holdindeg)def create_holding(db: Sess updef create_holding(db: Sessilddef create_holding(db: Session, holdindeg)def create_holding(db: Sess updef create_holding(db: Sessilddef create_holding(db: Session, h).deftedef create_holngdef create_holding(db: S()
    if not db_holding:
        return False
    db.delete(db_holding)
    db.commit()
    return True

# Income record CRUD
def get_income_records(db: Session, portfolio_id: int):
    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    reome     ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    reome     ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    reome     ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    retoc    ret    retstock_pos    ret    ret   , stock_id: int, stock: schemas.StockPositionUpdate):
    db_stock = db.query(models    db_stock = db.query(models    db_stock = db.queryck_id).first()
    if not db_stock:
        return None
    
    update_data = stock.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_stock, key, value)
    
    db.commit()
    db.refresh(db_stock)
    return db_stock

def delete_stock_position(db: Session, stock_id: int):
    db_stock = db.query(models.StockPosition).filter(models.StockPosition.id == stock_id).first()
    if not db_stock:
        return False
    db.delete(db_stock)
    db.commit()
    return True
