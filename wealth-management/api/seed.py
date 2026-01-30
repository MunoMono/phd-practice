"""
Database seed script - loads default portfolio data from Model Portfolio v0.2
"""
from database import SessionLocal, engine
import models
import schemas

# Default portfolio data from docs/first_release/Model Portfolio v0 1.xlsx
DEFAULT_PORTFOLIO = {
    "name": "Model Portfolio v0.2",
    "base_currency": "GBP",
    "total_target": 750000.0,
    "tolerance_pct": 5.0
}

DEFAULT_SLEEVES = [
    {"name": "Defensive Income", "code": "defensive", "target_pct": 35.0},
    {"name": "Equity Income & Growth", "code": "equity", "target_pct": 35.0},
    {"name": "Real Assets & Alternatives", "code": "real", "target_pct": 20.0},
    {"name": "Cash/Income Buffer", "code": "cash", "target_pct": 10.0}
]

DEFAULT_HOLDINGS = [
    # Defensive Income (35%)
    {"sleeve_code": "defensive", "ticker": "AGBP", "name": "iShares Core £ Corporate Bond UCITS ETF", "target_pct": 22.0, "notes": "IG credit core"},
    {"sleeve_code": "defensive", "ticker": "IGCB", "name": "iShares £ Corporate Bond 0-5yr UCITS ETF", "target_pct": 8.0, "notes": "Short duration IG"},
    {"sleeve_code": "defensive", "ticker": "GLTP", "name": "L&G Global Inflation Linked Bond Index Fund", "target_pct": 5.0, "notes": "Inflation protection"},
    
    # Equity Income & Growth (35%)
    {"sleeve_code": "equity", "ticker": "VHYL", "name": "Vanguard FTSE All-World High Dividend Yield UCITS ETF", "target_pct": 17.0, "notes": "Global dividend focus"},
    {"sleeve_code": "equity", "ticker": "GBDV", "name": "Goldman Sachs ActiveBeta World Equity UCITS ETF", "target_pct": 10.0, "notes": "Smart beta global"},
    {"sleeve_code": "equity", "ticker": "IUKD", "name": "iShares UK Dividend UCITS ETF", "target_pct": 3.0, "notes": "UK dividend tilt"},
    {"sleeve_code": "equity", "ticker": "STOCKS", "name": "Individual Stock Basket", "target_pct": 5.0, "notes": "12-stock equal-weight basket (UK/HK/SG)"},
    
    # Real Assets & Alternatives (20%)
    {"sleeve_code": "real", "ticker": "INPP", "name": "International Public Partnerships", "target_pct": 4.0, "notes": "Infrastructure fund"},
    {"sleeve_code": "real", "ticker": "HICL", "name": "HICL Infrastructure PLC", "target_pct": 3.0, "notes": "Infrastructure fund"},
    {"sleeve_code": "real", "ticker": "INFR", "name": "JLEN Environmental Assets", "target_pct": 3.0, "notes": "Renewable infrastructure"},
    {"sleeve_code": "real", "ticker": "IWDP", "name": "iShares Developed Markets Property Yield UCITS ETF", "target_pct": 7.0, "notes": "Global REITs"},
    {"sleeve_code": "real", "ticker": "TFIF", "name": "Tufton Oceanic Assets", "target_pct": 3.0, "notes": "Shipping assets"},
    
    # Cash/Income Buffer (10%)
    {"sleeve_code": "cash", "ticker": "GBP CASH", "name": "Cash - GBP", "target_pct": 5.0, "notes": "Liquidity buffer"},
    {"sleeve_code": "cash", "ticker": "ERNS", "name": "ERN (GBP Treasury ETF)", "target_pct": 5.0, "notes": "Short-term gilts"}
]

# Individual stock basket (12 stocks from Model Portfolio v0 1.xlsx)
STOCK_BASKET = [
    # UK stocks (6)
    {"ticker": "ULVR", "company_name": "Unilever PLC", "exchange": "LSE", "country": "UK", "region": "Europe", "sector": "Consumer Staples", "role": "Defensive quality", "basket_weight_pct": 8.33},
    {"ticker": "DGE", "company_name": "Diageo PLC", "exchange": "LSE", "country": "UK", "region": "Europe", "sector": "Consumer Staples", "role": "Premium spirits", "basket_weight_pct": 8.33},
    {"ticker": "AZN", "company_name": "AstraZeneca PLC", "exchange": "LSE", "country": "UK", "region": "Europe", "sector": "Healthcare", "role": "Pharma growth", "basket_weight_pct": 8.33},
    {"ticker": "GSK", "company_name": "GSK PLC", "exchange": "LSE", "country": "UK", "region": "Europe", "sector": "Healthcare", "role": "Healthcare yield", "basket_weight_pct": 8.33},
    {"ticker": "NG.", "company_name": "National Grid PLC", "exchange": "LSE", "country": "UK", "region": "Europe", "sector": "Utilities", "role": "Regulated utility", "basket_weight_pct": 8.33},
    {"ticker": "LGEN", "company_name": "Legal & General Group", "exchange": "LSE", "country": "UK", "region": "Europe", "sector": "Financials", "role": "Asset manager", "basket_weight_pct": 8.33},
    
    # Hong Kong stocks (3)
    {"ticker": "1299", "company_name": "AIA Group Ltd", "exchange": "HKEX", "country": "Hong Kong", "region": "Asia", "sector": "Financials", "role": "Pan-Asian insurer", "basket_weight_pct": 8.33},
    {"ticker": "0388", "company_name": "Hong Kong Exchanges & Clearing", "exchange": "HKEX", "country": "Hong Kong", "region": "Asia", "sector": "Financials", "role": "Exchange monopoly", "basket_weight_pct": 8.33},
    {"ticker": "0823", "company_name": "Link REIT", "exchange": "HKEX", "country": "Hong Kong", "region": "Asia", "sector": "Real Estate", "role": "HK retail REIT", "basket_weight_pct": 8.33},
    
    # Singapore stocks (3)
    {"ticker": "D05", "company_name": "DBS Group Holdings", "exchange": "SGX", "country": "Singapore", "region": "Asia", "sector": "Financials", "role": "Southeast Asian bank", "basket_weight_pct": 8.33},
    {"ticker": "Z74", "company_name": "Singtel", "exchange": "SGX", "country": "Singapore", "region": "Asia", "sector": "Telecommunications", "role": "Regional telco", "basket_weight_pct": 8.33},
    {"ticker": "S63", "company_name": "ST Engineering", "exchange": "SGX", "country": "Singapore", "region": "Asia", "sector": "Industrials", "role": "Defense/engineering", "basket_weight_pct": 8.33}
]


def seed_database():
    """Create initial portfolio with all data"""
    db = SessionLocal()
    
    try:
        # Check if portfolio already exists
        existing = db.query(models.Portfolio).filter(models.Portfolio.name == DEFAULT_PORTFOLIO["name"]).first()
        if existing:
            print(f"Portfolio '{DEFAULT_PORTFOLIO['name']}' already exists. Skipping seed.")
            return
        
        # Create portfolio
        portfolio = models.Portfolio(
            name=DEFAULT_PORTFOLIO["name"],
            base_currency=DEFAULT_PORTFOLIO["base_currency"],
            total_target=DEFAULT_PORTFOLIO["total_target"],
            tolerance_pct=DEFAULT_PORTFOLIO["tolerance_pct"]
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)
        print(f"✓ Created portfolio: {portfolio.name}")
        
        # Create sleeves
        sleeve_map = {}
        for sleeve_data in DEFAULT_SLEEVES:
            sleeve = models.Sleeve(
                portfolio_id=portfolio.id,
                name=sleeve_data["name"],
                code=sleeve_data["code"],
                target_pct=sleeve_data["target_pct"]
            )
            db.add(sleeve)
            db.commit()
            db.refresh(sleeve)
            sleeve_map[sleeve_data["code"]] = sleeve.id
            print(f"  ✓ Created sleeve: {sleeve.name} ({sleeve.target_pct}%)")
        
        # Create holdings
        for holding_data in DEFAULT_HOLDINGS:
            sleeve_id = sleeve_map[holding_data["sleeve_code"]]
            
            # Calculate initial value based on target percentage
            target_value = portfolio.total_target * (holding_data["target_pct"] / 100)
            
            holding = models.Holding(
                portfolio_id=portfolio.id,
                sleeve_id=sleeve_id,
                ticker=holding_data["ticker"],
                name=holding_data["name"],
                target_pct=holding_data["target_pct"],
                current_value=target_value,  # Start at target
                notes=holding_data.get("notes", "")
            )
            db.add(holding)
            print(f"    ✓ Created holding: {holding.ticker} ({holding.target_pct}%)")
        
        db.commit()
        
        # Create stock basket positions
        for stock_data in STOCK_BASKET:
            # Calculate portfolio weight (5% basket / 12 stocks = 0.4167% each)
            portfolio_weight_pct = 5.0 / 12
            initial_value = portfolio.total_target * (portfolio_weight_pct / 100)
            
            stock = models.StockPosition(
                portfolio_id=portfolio.id,
                ticker=stock_data["ticker"],
                company_name=stock_data["company_name"],
                exchange=stock_data["exchange"],
                country=stock_data["country"],
                region=stock_data["region"],
                sector=stock_data["sector"],
                role=stock_data["role"],
                basket_weight_pct=stock_data["basket_weight_pct"],
                portfolio_weight_pct=portfolio_weight_pct,
                current_value=initial_value,
                quantity=0.0,
                avg_price=0.0,
                notes=""
            )
            db.add(stock)
            print(f"      ✓ Created stock: {stock.ticker} ({stock.company_name})")
        
        db.commit()
        
        print(f"\n✅ Database seeded successfully!")
        print(f"   Portfolio: {portfolio.name}")
        print(f"   Total target: £{portfolio.total_target:,.0f}")
        print(f"   Sleeves: {len(DEFAULT_SLEEVES)}")
        print(f"   Holdings: {len(DEFAULT_HOLDINGS)}")
        print(f"   Stock basket: {len(STOCK_BASKET)} stocks")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    print("✓ Tables created")
    
    print("\nSeeding database with default portfolio...")
    seed_database()
