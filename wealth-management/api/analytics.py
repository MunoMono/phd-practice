"""
Portfolio analytics using NumPy and Matplotlib
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from . import models

def calculate_portfolio_metrics(portfolio: models.Portfolio) -> Dict[str, Any]:
    """Calculate key portfolio metrics using NumPy"""
    
    # Get all holdings
    holdings = portfolio.holdings
    
    if not holdings:
        return {"error": "No holdings in portfolio"}
    
    # Extract data as numpy arrays
    target_pcts = np.array([h.target_pct for h in holdings])
    current_values = np.array([h.current_value for h in holdings])
    
    # Calculate totals
    total_current = np.sum(current_values)
    total_target = portfolio.total_target
    
    # Calculate current percentages
    current_pcts = (current_values / total_current * 100) if total_current > 0 else np.zeros_like(current_values)
    
    # Calculate drift
    drift = current_pcts - target_pcts
    abs_drift = np.abs(drift)
    
    # Portfolio statistics
    metrics = {
        "total_target": float(total_target),
        "total_current": float(total_current),
        "total_drift_pct": float((total_current - total_target) / total_target * 100) if total_target > 0 else 0,
        "max_position_drift": float(np.max(abs_drift)),
        "avg_position_drift": float(np.mean(abs_drift)),
        "positions_out_of_tolerance": int(np.sum(abs_drift > portfolio.tolerance_pct)),
        "total_positions": len(holdings)
    }
    
    return metrics


def calculate_sleeve_metrics(portfolio: models.Portfolio) -> List[Dict[str, Any]]:
    """Calculate metrics for each sleeve"""
    
    sleeve_metrics = []
    
    for sleeve in portfolio.sleeves:
        sleeve_holdings = [h for h in portfolio.holdings if h.sleeve_id == sleeve.id]
        
        if not sleeve_holdings:
            continue
        
        # Calculate sleeve totals
        current_values = np.array([h.current_value for h in sleeve_holdings])
        sleeve_current = np.sum(current_values)
        
        # Calculate sleeve target value
        sleeve_target = portfolio.total_target * (sleeve.target_pct / 100)
        
        # Calculate drift
        sleeve_drift_pct = ((sleeve_current - sleeve_target) / sleeve_target * 100) if sleeve_target > 0 else 0
        
        sleeve_metrics.append({
            "sleeve_name": sleeve.name,
            "sleeve_code": sleeve.code,
            "target_pct": sleeve.target_pct,
            "target_value": float(sleeve_target),
            "current_value": float(sleeve_current),
            "current_pct": float(sleeve_current / portfolio.total_target * 100) if portfolio.total_target > 0 else 0,
            "drift_pct": float(sleeve_drift_pct),
            "is_out_of_tolerance": abs(sleeve_drift_pct) > portfolio.tolerance_pct
        })
    
    return sleeve_metrics


def generate_allocation_chart(portfolio: models.Portfolio) -> str:
    """Generate pie chart of current allocation and return as base64 image"""
    
    sleeves = portfolio.sleeves
    
    if not sleeves:
        return None
    
    # Prepare data
    labels = []
    sizes = []
    colors = ['#0f62fe', '#24a148', '#8a3ffc', '#da1e28']  # IBM Carbon colors
    
    for sleeve in sleeves:
        sleeve_holdings = [h for h in portfolio.holdings if h.sleeve_id == sleeve.id]
        sleeve_value = sum(h.current_value for h in sleeve_holdings)
        
        if sleeve_value > 0:
            labels.append(sleeve.name)
            sizes.append(sleeve_value)
    
    if not sizes:
        return None
    
    # Create pie chart
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors[:len(sizes)], startangle=90)
    ax.axis('equal')
    plt.title('Portfolio Allocation by Sleeve', fontsize=16, fontweight='bold')
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f"data:image/png;base64,{image_base64}"


def generate_drift_chart(portfolio: models.Portfolio) -> str:
    """Generate bar chart showing drift from target allocation"""
    
    sleeve_metrics = calculate_sleeve_metrics(portfolio)
    
    if not sleeve_metrics:
        return None
    
    # Prepare data
    sleeves = [m['sleeve_name'] for m in sleeve_metrics]
    drifts = [m['drift_pct'] for m in sleeve_metrics]
    colors = ['#da1e28' if abs(d) > portfolio.tolerance_pct else '#24a148' for d in drifts]
    
    # Create bar chart
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(sleeves, drifts, color=colors)
    
    # Add tolerance bands
    ax.axhline(y=portfolio.tolerance_pct, color='#da1e28', linestyle='--', linewidth=1, alpha=0.5, label=f'+{portfolio.tolerance_pct}% tolerance')
    ax.axhline(y=-portfolio.tolerance_pct, color='#da1e28', linestyle='--', linewidth=1, alpha=0.5, label=f'-{portfolio.tolerance_pct}% tolerance')
    ax.axhline(y=0, color='#161616', linewidth=1)
    
    ax.set_ylabel('Drift from Target (%)', fontsize=12)
    ax.set_title('Sleeve Drift Analysis', fontsize=16, fontweight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    # Rotate x labels for readability
    plt.xticks(rotation=45, ha='right')
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f"data:image/png;base64,{image_base64}"


def calculate_income_projection(portfolio: models.Portfolio) -> Dict[str, Any]:
    """
    Calculate expected income based on Strategic Asset Allocation yields
    
    Expected yields from docs:
    - Defensive Income: 3.5%
    - Equity Income & Growth: 3.0%
    - Real Assets & Alternatives: 4.5%
    - Cash/Income Buffer: 0.5%
    """
    
    # Expected yields by sleeve code
    expected_yields = {
        "defensive": 0.035,  # 3.5%
        "equity": 0.030,     # 3.0%
        "real": 0.045,       # 4.5%
        "cash": 0.005        # 0.5%
    }
    
    total_expected_income = 0
    sleeve_income = []
    
    for sleeve in portfolio.sleeves:
        sleeve_holdings = [h for h in portfolio.holdings if h.sleeve_id == sleeve.id]
        sleeve_value = sum(h.current_value for h in sleeve_holdings)
        
        yield_rate = expected_yields.get(sleeve.code, 0.03)  # Default 3%
        expected_income = sleeve_value * yield_rate
        
        total_expected_income += expected_income
        
        sleeve_income.append({
            "sleeve_name": sleeve.name,
            "sleeve_code": sleeve.code,
            "current_value": float(sleeve_value),
            "expected_yield_pct": float(yield_rate * 100),
            "expected_annual_income": float(expected_income)
        })
    
    # Calculate withdrawal rate
    withdrawal_rate = (total_expected_income / portfolio.total_target * 100) if portfolio.total_target > 0 else 0
    
    return {
        "total_expected_annual_income": float(total_expected_income),
        "target_income": 30000.0,  # From Income Policy v1
        "income_gap": float(30000 - total_expected_income),
        "withdrawal_rate_pct": float(withdrawal_rate),
        "max_withdrawal_rate_pct": 4.25,  # Hard ceiling from docs
        "is_sustainable": withdrawal_rate <= 4.25,
        "sleeve_breakdown": sleeve_income
    }


def generate_income_chart(portfolio: models.Portfolio) -> str:
    """Generate stacked bar chart showing income by sleeve"""
    
    income_data = calculate_income_projection(portfolio)
    sleeve_breakdown = income_data['sleeve_breakdown']
    
    if not sleeve_breakdown:
        return None
    
    # Prepare data
    sleeves = [s['sleeve_name'] for s in sleeve_breakdown]
    incomes = [s['expected_annual_income'] for s in sleeve_breakdown]
    
    # Create bar chart
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(sleeves, incomes, color='#0f62fe')
    
    # Add target line
    target_income = income_data['target_income']
    ax.axhline(y=target_income, color='#24a148', linestyle='--', linewidth=2, label=f'Target £{target_income:,.0f}')
    
    # Add total line
    total_income = income_data['total_expected_annual_income']
    ax.axhline(y=total_income, color='#8a3ffc', linestyle='-', linewidth=2, label=f'Total £{total_income:,.0f}')
    
    ax.set_ylabel('Expected Annual Income (£)', fontsize=12)
    ax.set_title('Expected Income by Sleeve', fontsize=16, fontweight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    # Format y-axis as currency
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'£{x:,.0f}'))
    
    # Rotate x labels
    plt.xticks(rotation=45, ha='right')
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f"data:image/png;base64,{image_base64}"


def generate_rebalance_recommendations(portfolio: models.Portfolio) -> List[Dict[str, Any]]:
    """Generate specific trade recommendations to bring portfolio back to target"""
    
    recommendations = []
    
    for sleeve in portfolio.sleeves:
        sleeve_holdings = [h for h in portfolio.holdings if h.sleeve_id == sleeve.id]
        sleeve_current = sum(h.current_value for h in sleeve_holdings)
        sleeve_target = portfolio.total_target * (sleeve.target_pct / 100)
        
        drift_value = sleeve_current - sleeve_target
        drift_pct = (drift_value / sleeve_target * 100) if sleeve_target > 0 else 0
        
        # Only recommend if outside tolerance band
        if abs(drift_pct) > portfolio.tolerance_pct:
            action = "SELL" if drift_value > 0 else "BUY"
            
            recommendations.append({
                "sleeve_name": sleeve.name,
                "action": action,
                "amount": float(abs(drift_value)),
                "current_value": float(sleeve_current),
                "target_value": float(sleeve_target),
                "drift_pct": float(drift_pct),
                "priority": "HIGH" if abs(drift_pct) > portfolio.tolerance_pct * 2 else "MEDIUM"
            })
    
    # Sort by absolute drift percentage (highest first)
    recommendations.sort(key=lambda x: abs(x['drift_pct']), reverse=True)
    
    return recommendations


def generate_portfolio_analytics(db: Session, portfolio_id: int) -> Dict[str, Any]:
    """
    Main analytics function - generates all charts and metrics
    """
    portfolio = db.query(models.Portfolio).filter(models.Portfolio.id == portfolio_id).first()
    
    if not portfolio:
        return {"error": "Portfolio not found"}
    
    # Calculate all metrics and generate charts
    return {
        "portfolio_metrics": calculate_portfolio_metrics(portfolio),
        "sleeve_metrics": calculate_sleeve_metrics(portfolio),
        "income_projection": calculate_income_projection(portfolio),
        "rebalance_recommendations": generate_rebalance_recommendations(portfolio),
        "charts": {
            "allocation_pie": generate_allocation_chart(portfolio),
            "drift_bar": generate_drift_chart(portfolio),
            "income_bar": generate_income_chart(portfolio)
        }
    }
