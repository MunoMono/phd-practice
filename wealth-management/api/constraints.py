"""
Portfolio constraint validation based on Sleeve Constraints v1.2 and Income Policy v1
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from . import models

class ValidationResult:
    def __init__(self):
        self.violations = []
        self.warnings = []
        self.is_valid = True
    
    def add_violation(self, severity: str, sleeve: str, rule: str, message: str):
        """Add a constraint violation"""
        violation = {
            "severity": severity,  # "error" or "warning"
            "sleeve": sleeve,
            "rule": rule,
            "message": message
        }
        if severity == "error":
            self.violations.append(violation)
            self.is_valid = False
        else:
            self.warnings.append(violation)
    
    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "violations": self.violations,
            "warnings": self.warnings
        }


def validate_defensive_income_sleeve(holdings: List[models.Holding], sleeve: models.Sleeve, portfolio: models.Portfolio) -> ValidationResult:
    """
    Defensive Income sleeve constraints:
    - GBP-anchored (base currency check)
    - Investment Grade (IG) credit average
    - Max 15% sub-investment grade
    - Duration: 3-6 years target (max 8 years)
    - Yield: 3.0-4.5%
    - Max 20% per instrument
    """
    result = ValidationResult()
    sleeve_name = sleeve.name
    
    # Calculate total value in sleeve
    total_value = sum(h.current_value for h in holdings)
    
    if total_value == 0:
        return result  # Empty sleeve, skip validation
    
    # Rule: Max 20% per instrument
    for holding in holdings:
        holding_pct = (holding.current_value / total_value) * 100 if total_value > 0 else 0
        if holding_pct > 20:
            result.add_violation(
                "error",
                sleeve_name,
                "Max 20% per instrument",
                f"{holding.ticker} represents {holding_pct:.1f}% of sleeve (max 20%)"
            )
    
    # Rule: Target yield 3.0-4.5%
    # (Would need yield data in holdings to validate - placeholder)
    result.add_violation(
        "warning",
        sleeve_name,
        "Target yield 3.0-4.5%",
        "Yield validation requires yield data for each holding"
    )
    
    return result


def validate_equity_income_sleeve(holdings: List[models.Holding], sleeve: models.Sleeve, portfolio: models.Portfolio) -> ValidationResult:
    """
    Equity Income & Growth sleeve constraints:
    - Global unhedged equities
    - Max 25% sector concentration
    - Max 20% UK home bias
    - Individual stocks: max 3% per name
    - Max 15% total in individual stocks
    - Min 12 stock holdings (if using stock basket)
    """
    result = ValidationResult()
    sleeve_name = sleeve.name
    
    # Calculate total value in sleeve
    total_value = sum(h.current_value for h in holdings)
    
    if total_value == 0:
        return result
    
    # Rule: Max 20% per position (for ETFs/funds)
    # Rule: Max 3% per stock (for individual stocks)
    stock_basket_total = 0
    stock_count = 0
    
    for holding in holdings:
        holding_pct = (holding.current_value / total_value) * 100 if total_value > 0 else 0
        
        # Check if this is the stock basket (ticker = "STOCKS")
        if holding.ticker == "STOCKS":
            stock_basket_total = holding_pct
            # Get actual stock positions to validate
            stock_positions = portfolio.stock_positions
            if stock_positions:
                stock_count = len(stock_positions)
                
                # Rule: Min 12 stocks in basket
                if stock_count < 12:
                    result.add_violation(
                        "error",
                        sleeve_name,
                        "Min 12 stock holdings",
                        f"Stock basket has {stock_count} stocks (minimum 12 required)"
                    )
                
                # Rule: Max 3% per stock within basket
                for stock in stock_positions:
                    if stock.portfolio_weight_pct > 3.0:
                        result.add_violation(
                            "error",
                            sleeve_name,
                            "Max 3% per stock",
                            f"{stock.ticker} represents {stock.portfolio_weight_pct:.2f}% of portfolio (max 3%)"
                        )
        else:
            # ETF/fund holding - max 20%
            if holding_pct > 20:
                result.add_violation(
                    "error",
                    sleeve_name,
                    "Max 20% per ETF/fund",
                    f"{holding.ticker} represents {holding_pct:.1f}% of sleeve (max 20%)"
                )
    
    # Rule: Max 15% total in individual stocks
    if stock_basket_total > 15:
        result.add_violation(
            "error",
            sleeve_name,
            "Max 15% in individual stocks",
            f"Stock basket represents {stock_basket_total:.1f}% of sleeve (max 15%)"
        )
    
    return result


def validate_real_assets_sleeve(holdings: List[models.Holding], sleeve: models.Sleeve, portfolio: models.Portfolio) -> ValidationResult:
    """
    Real Assets & Alternatives sleeve constraints:
    - REITs: max 10%
    - Infrastructure: max 10%
    - Credit/asset-backed: max 10%
    - No lock-up periods
    """
    result = ValidationResult()
    sleeve_name = sleeve.name
    
    # Calculate total value in sleeve
    total_value = sum(h.current_value for h in holdings)
    
    if total_value == 0:
        return result
    
    # Track subcategories (would need asset class metadata)
    reit_total = 0
    infra_total = 0
    credit_total = 0
    
    for holding in holdings:
        holding_pct = (holding.current_value / total_value) * 100 if total_value > 0 else 0
        
        # Heuristic classification based on ticker/name
        ticker = holding.ticker.upper()
        name = holding.name.upper()
        
        if "REIT" in name or "PROPERTY" in name:
            reit_total += holding_pct
        elif "INFR" in ticker or "INFRASTRUCTURE" in name:
            infra_total += holding_pct
        elif "CREDIT" in name or "BOND" in name:
            credit_total += holding_pct
    
    # Rule: Max 10% REITs
    if reit_total > 10:
        result.add_violation(
            "error",
            sleeve_name,
            "Max 10% REITs",
            f"REITs represent {reit_total:.1f}% of sleeve (max 10%)"
        )
    
    # Rule: Max 10% Infrastructure
    if infra_total > 10:
        result.add_violation(
            "error",
            sleeve_name,
            "Max 10% Infrastructure",
            f"Infrastructure represents {infra_total:.1f}% of sleeve (max 10%)"
        )
    
    # Rule: Max 10% Credit/asset-backed
    if credit_total > 10:
        result.add_violation(
            "error",
            sleeve_name,
            "Max 10% Credit/asset-backed",
            f"Credit/asset-backed represents {credit_total:.1f}% of sleeve (max 10%)"
        )
    
    return result


def validate_cash_buffer_sleeve(holdings: List[models.Holding], sleeve: models.Sleeve, portfolio: models.Portfolio) -> ValidationResult:
    """
    Cash/Income Buffer sleeve constraints:
    - GBP-only instruments
    - Duration ≤1 year
    - Size: 1.5-2.0 years of income (£45k-£60k for £30k annual need)
    """
    result = ValidationResult()
    sleeve_name = sleeve.name
    
    # Calculate total value in sleeve
    total_value = sum(h.current_value for h in holdings)
    
    # Rule: Size check (1.5-2.0 years of £30k income = £45k-£60k)
    target_income = 30000
    min_buffer = target_income * 1.5  # £45k
    max_buffer = target_income * 2.0  # £60k
    
    if total_value < min_buffer:
        result.add_violation(
            "warning",
            sleeve_name,
            "Min 1.5 years income buffer",
            f"Cash buffer is £{total_value:,.0f} (should be £{min_buffer:,.0f}-£{max_buffer:,.0f})"
        )
    elif total_value > max_buffer:
        result.add_violation(
            "warning",
            sleeve_name,
            "Max 2.0 years income buffer",
            f"Cash buffer is £{total_value:,.0f} (should be £{min_buffer:,.0f}-£{max_buffer:,.0f})"
        )
    
    # Rule: GBP-only (check holdings)
    for holding in holdings:
        if "GBP" not in holding.ticker and "CASH" not in holding.ticker.upper():
            result.add_violation(
                "warning",
                sleeve_name,
                "GBP-only instruments",
                f"{holding.ticker} may not be GBP-denominated"
            )
    
    return result


def validate_income_policy(portfolio: models.Portfolio, income_records: List[models.IncomeRecord]) -> ValidationResult:
    """
    Income Policy constraints:
    - Target: £30,000/year nominal income
    - Hard ceiling: 4.25% withdrawal rate
    - Income hierarchy: (1) natural income 75-80%, (2) rebalancing, (3) cash buffer
    """
    result = ValidationResult()
    
    # Rule: Max 4.25% withdrawal rate
    target_income = 30000
    max_withdrawal_rate = 0.0425
    max_withdrawal = portfolio.total_target * max_withdrawal_rate
    
    if target_income > max_withdrawal:
        result.add_violation(
            "error",
            "Portfolio",
            "Max 4.25% withdrawal rate",
            f"Target income £{target_income:,.0f} exceeds max withdrawal £{max_withdrawal:,.0f} (4.25% of £{portfolio.total_target:,.0f})"
        )
    
    # Calculate annual income if we have records
    if income_records:
        annual_income = sum(record.amount for record in income_records)
        
        # Check if we're hitting target
        if annual_income < target_income * 0.9:  # 90% threshold
            result.add_violation(
                "warning",
                "Portfolio",
                "Target £30k annual income",
                f"Projected annual income £{annual_income:,.0f} is below target £{target_income:,.0f}"
            )
    
    return result


def validate_portfolio_constraints(db: Session, portfolio_id: int) -> Dict[str, Any]:
    """
    Main validation function - validates all constraints for a portfolio
    """
    portfolio = db.query(models.Portfolio).filter(models.Portfolio.id == portfolio_id).first()
    
    if not portfolio:
        return {"error": "Portfolio not found"}
    
    all_results = ValidationResult()
    
    # Validate each sleeve
    for sleeve in portfolio.sleeves:
        sleeve_holdings = [h for h in portfolio.holdings if h.sleeve_id == sleeve.id]
        
        if sleeve.code == "defensive":
            sleeve_result = validate_defensive_income_sleeve(sleeve_holdings, sleeve, portfolio)
        elif sleeve.code == "equity":
            sleeve_result = validate_equity_income_sleeve(sleeve_holdings, sleeve, portfolio)
        elif sleeve.code == "real":
            sleeve_result = validate_real_assets_sleeve(sleeve_holdings, sleeve, portfolio)
        elif sleeve.code == "cash":
            sleeve_result = validate_cash_buffer_sleeve(sleeve_holdings, sleeve, portfolio)
        else:
            continue
        
        # Merge results
        all_results.violations.extend(sleeve_result.violations)
        all_results.warnings.extend(sleeve_result.warnings)
        if not sleeve_result.is_valid:
            all_results.is_valid = False
    
    # Validate income policy
    income_result = validate_income_policy(portfolio, portfolio.income_records)
    all_results.violations.extend(income_result.violations)
    all_results.warnings.extend(income_result.warnings)
    if not income_result.is_valid:
        all_results.is_valid = False
    
    return all_results.to_dict()
