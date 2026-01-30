import { useState } from 'react';
import {
  Grid,
  Column,
  Tile,
  ProgressBar,
  Tag,
  InlineNotification,
  StructuredListWrapper,
  StructuredListHead,
  StructuredListBody,
  StructuredListRow,
  StructuredListCell
} from '@carbon/react';
import { Currency, TrendUp, TrendDown, Wallet, Dashboard as DashboardIcon } from '@carbon/icons-react';
import { DonutChart, StackedBarChart } from '@carbon/charts-react';
import { formatCurrency, formatPercent, calculateTotalCurrent } from '../../utils/portfolioCalculations';
import './Income.scss';

const Income = ({ portfolio }) => {
  // Income Policy from docs: £30k target, 4.25% max withdrawal, 1.5-2yr cash buffer (£45k-£60k)
  const INCOME_TARGET = 30000;
  const MAX_WITHDRAWAL_RATE = 4.25;
  const CASH_BUFFER_MIN = 45000;
  const CASH_BUFFER_MAX = 60000;

  const totalCurrent = calculateTotalCurrent(portfolio.holdings);

  // Expected yields per sleeve (from Strategic Asset Allocation.xlsx)
  const sleeveYields = {
    defensive: 3.5,   // Defensive Income: 3.5%
    equity: 3.0,      // Equity Income & Growth: 3.0%
    real: 4.5,        // Real Assets & Alternatives: 4.5%
    cash: 0.5         // Cash/Income Buffer: 0.5%
  };

  // Calculate projected income
  const incomeBySleeve = portfolio.sleeves.map(sleeve => {
    const sleeveHoldings = portfolio.holdings.filter(h => h.sleeveId === sleeve.id);
    const sleeveValue = sleeveHoldings.reduce((sum, h) => sum + (h.currentValue || 0), 0);
    const expectedYield = sleeveYields[sleeve.id] || 0;
    const projectedIncome = sleeveValue * (expectedYield / 100);
    
    return {
      id: sleeve.id,
      name: sleeve.name,
      value: sleeveValue,
      yield: expectedYield,
      income: projectedIncome
    };
  });

  const totalProjectedIncome = incomeBySleeve.reduce((sum, s) => sum + s.income, 0);
  const actualWithdrawalRate = (totalProjectedIncome / totalCurrent) * 100;
  
  // Cash buffer analysis
  const cashHolding = portfolio.holdings.find(h => h.ticker === 'GBP CASH');
  const cashBufferValue = cashHolding ? cashHolding.currentValue : 0;
  const cashBufferYears = cashBufferValue / INCOME_TARGET;
  
  // Constraint violations
  const violations = [];
  const warnings = [];
  
  if (totalProjectedIncome < INCOME_TARGET) {
    violations.push(`Income shortfall: £${(INCOME_TARGET - totalProjectedIncome).toLocaleString()} below £${INCOME_TARGET.toLocaleString()} target`);
  }
  
  if (actualWithdrawalRate > MAX_WITHDRAWAL_RATE) {
    violations.push(`Withdrawal rate ${actualWithdrawalRate.toFixed(2)}% exceeds ${MAX_WITHDRAWAL_RATE}% ceiling`);
  }
  
  if (cashBufferValue < CASH_BUFFER_MIN) {
    violations.push(`Cash buffer £${cashBufferValue.toLocaleString()} below minimum £${CASH_BUFFER_MIN.toLocaleString()}`);
  } else if (cashBufferValue > CASH_BUFFER_MAX) {
    warnings.push(`Cash buffer £${cashBufferValue.toLocaleString()} exceeds optimal £${CASH_BUFFER_MAX.toLocaleString()}`);
  }

  // Chart data
  const incomeDonutData = incomeBySleeve.map(s => ({
    group: s.name,
    value: s.income
  }));

  const incomeDonutOptions = {
    title: 'Annual Income by Source',
    resizable: true,
    donut: {
      center: {
        label: 'Total',
        numberFormatter: (value) => `£${Math.round(value).toLocaleString()}`
      }
    },
    height: '400px',
    theme: 'g100'
  };

  return (
    <div className="income-page" style={{ padding: '2rem', background: '#262626', minHeight: '100vh' }}>
      <Grid narrow>
        {/* Header */}
        <Column lg={14} md={8} sm={4}>
          <div style={{ 
            padding: '1.5rem',
            marginBottom: '2rem',
            background: '#393939',
            borderLeft: '4px solid #24a148'
          }}>
            <h3 style={{ margin: 0, color: '#f4f4f4', fontSize: '1.75rem', fontWeight: 400 }}>Income Tracker</h3>
            <p style={{ margin: '0.5rem 0 0 0', color: '#c6c6c6', fontSize: '0.875rem' }}>
              Target: £{INCOME_TARGET.toLocaleString()}/year | Max withdrawal: {MAX_WITHDRAWAL_RATE}%
            </p>
          </div>
        </Column>

        {/* Violations */}
        {violations.length > 0 && (
          <Column lg={14} md={8} sm={4}>
            <InlineNotification
              kind="error"
              title="Income Policy Violations"
              subtitle={violations.join(' • ')}
              lowContrast
            />
          </Column>
        )}

        {warnings.length > 0 && (
          <Column lg={14} md={8} sm={4}>
            <InlineNotification
              kind="warning"
              title="Warnings"
              subtitle={warnings.join(' • ')}
              lowContrast
            />
          </Column>
        )}

        {/* Key Metrics */}
        <Column lg={3} md={2} sm={2}>
          <Tile style={{ background: '#393939', padding: '1rem', minHeight: '120px', borderLeft: '3px solid #24a148' }}>
            <Currency size={24} style={{ color: '#24a148', marginBottom: '0.5rem' }} />
            <p style={{ color: '#c6c6c6', fontSize: '12px', margin: '0 0 0.25rem 0' }}>Projected Annual Income</p>
            <p style={{ color: '#f4f4f4', fontSize: '24px', fontWeight: 600, margin: 0 }}>
              {formatCurrency(totalProjectedIncome)}
            </p>
            <p style={{ color: totalProjectedIncome >= INCOME_TARGET ? '#24a148' : '#fa4d56', fontSize: '12px', margin: '0.25rem 0 0 0' }}>
              {totalProjectedIncome >= INCOME_TARGET ? '+' : ''}{formatCurrency(totalProjectedIncome - INCOME_TARGET)} vs target
            </p>
          </Tile>
        </Column>

        <Column lg={3} md={2} sm={2}>
          <Tile style={{ background: '#393939', padding: '1rem', minHeight: '120px', borderLeft: '3px solid #0f62fe' }}>
            <TrendUp size={24} style={{ color: '#0f62fe', marginBottom: '0.5rem' }} />
            <p style={{ color: '#c6c6c6', fontSize: '12px', margin: '0 0 0.25rem 0' }}>Withdrawal Rate</p>
            <p style={{ color: '#f4f4f4', fontSize: '24px', fontWeight: 600, margin: 0 }}>
              {actualWithdrawalRate.toFixed(2)}%
            </p>
            <p style={{ color: actualWithdrawalRate <= MAX_WITHDRAWAL_RATE ? '#24a148' : '#fa4d56', fontSize: '12px', margin: '0.25rem 0 0 0' }}>
              {actualWithdrawalRate <= MAX_WITHDRAWAL_RATE ? 'Within' : 'Exceeds'} {MAX_WITHDRAWAL_RATE}% ceiling
            </p>
          </Tile>
        </Column>

        <Column lg={4} md={2} sm={2}>
          <Tile style={{ background: '#393939', padding: '1rem', minHeight: '120px', borderLeft: '3px solid #8a3ffc' }}>
            <Wallet size={24} style={{ color: '#8a3ffc', marginBottom: '0.5rem' }} />
            <p style={{ color: '#c6c6c6', fontSize: '12px', margin: '0 0 0.25rem 0' }}>Cash Buffer</p>
            <p style={{ color: '#f4f4f4', fontSize: '24px', fontWeight: 600, margin: 0 }}>
              {formatCurrency(cashBufferValue)}
            </p>
            <p style={{ color: '#c6c6c6', fontSize: '12px', margin: '0.25rem 0 0 0' }}>
              {cashBufferYears.toFixed(1)} years @ £{INCOME_TARGET.toLocaleString()}/yr
            </p>
          </Tile>
        </Column>

        <Column lg={4} md={2} sm={2}>
          <Tile style={{ background: '#393939', padding: '1rem', minHeight: '120px', borderLeft: '3px solid #ff832b' }}>
            <DashboardIcon size={24} style={{ color: '#ff832b', marginBottom: '0.5rem' }} />
            <p style={{ color: '#c6c6c6', fontSize: '12px', margin: '0 0 0.25rem 0' }}>Average Yield</p>
            <p style={{ color: '#f4f4f4', fontSize: '24px', fontWeight: 600, margin: 0 }}>
              {((totalProjectedIncome / totalCurrent) * 100).toFixed(2)}%
            </p>
            <p style={{ color: '#c6c6c6', fontSize: '12px', margin: '0.25rem 0 0 0' }}>
              Across portfolio
            </p>
          </Tile>
        </Column>

        {/* Income Progress */}
        <Column lg={14} md={8} sm={4}>
          <Tile style={{ background: '#393939', padding: '1.5rem' }}>
            <h4 style={{ color: '#f4f4f4', marginBottom: '1rem' }}>Income Target Progress</h4>
            <ProgressBar
              label="Annual Income"
              value={(totalProjectedIncome / INCOME_TARGET) * 100}
              max={100}
              helperText={`£${totalProjectedIncome.toLocaleString()} of £${INCOME_TARGET.toLocaleString()} target`}
              size="big"
            />
          </Tile>
        </Column>

        {/* Charts */}
        <Column lg={7} md={4} sm={4}>
          <Tile style={{ background: '#393939', padding: '1rem', minHeight: '450px' }}>
            <DonutChart data={incomeDonutData} options={incomeDonutOptions} />
          </Tile>
        </Column>

        {/* Income Breakdown Table */}
        <Column lg={7} md={4} sm={4}>
          <Tile style={{ background: '#393939', padding: '1.5rem' }}>
            <h4 style={{ color: '#f4f4f4', marginBottom: '1rem' }}>Income by Sleeve</h4>
            <StructuredListWrapper>
              <StructuredListHead>
                <StructuredListRow head>
                  <StructuredListCell head>Sleeve</StructuredListCell>
                  <StructuredListCell head>Value</StructuredListCell>
                  <StructuredListCell head>Yield</StructuredListCell>
                  <StructuredListCell head>Annual Income</StructuredListCell>
                </StructuredListRow>
              </StructuredListHead>
              <StructuredListBody>
                {incomeBySleeve.map(sleeve => (
                  <StructuredListRow key={sleeve.id}>
                    <StructuredListCell style={{ color: '#f4f4f4' }}>
                      {sleeve.name}
                    </StructuredListCell>
                    <StructuredListCell style={{ color: '#c6c6c6' }}>
                      {formatCurrency(sleeve.value)}
                    </StructuredListCell>
                    <StructuredListCell style={{ color: '#c6c6c6' }}>
                      {sleeve.yield.toFixed(2)}%
                    </StructuredListCell>
                    <StructuredListCell>
                      <strong style={{ color: '#24a148' }}>
                        {formatCurrency(sleeve.income)}
                      </strong>
                    </StructuredListCell>
                  </StructuredListRow>
                ))}
                <StructuredListRow>
                  <StructuredListCell style={{ color: '#f4f4f4', fontWeight: 600, borderTop: '1px solid #525252', paddingTop: '0.5rem' }}>
                    TOTAL
                  </StructuredListCell>
                  <StructuredListCell style={{ borderTop: '1px solid #525252', paddingTop: '0.5rem' }}>
                    {formatCurrency(totalCurrent)}
                  </StructuredListCell>
                  <StructuredListCell style={{ borderTop: '1px solid #525252', paddingTop: '0.5rem' }}>
                    {actualWithdrawalRate.toFixed(2)}%
                  </StructuredListCell>
                  <StructuredListCell style={{ borderTop: '1px solid #525252', paddingTop: '0.5rem' }}>
                    <strong style={{ color: '#24a148', fontSize: '16px' }}>
                      {formatCurrency(totalProjectedIncome)}
                    </strong>
                  </StructuredListCell>
                </StructuredListRow>
              </StructuredListBody>
            </StructuredListWrapper>
          </Tile>
        </Column>

        {/* Income Policy Summary */}
        <Column lg={14} md={8} sm={4}>
          <Tile style={{ background: '#393939', padding: '1.5rem' }}>
            <h4 style={{ color: '#f4f4f4', marginBottom: '1rem' }}>📋 Income Policy (from docs)</h4>
            <Grid narrow>
              <Column lg={7} md={4} sm={4}>
                <ul style={{ color: '#c6c6c6', fontSize: '0.875rem', paddingLeft: '1.5rem', margin: 0 }}>
                  <li><strong>Target:</strong> £30,000/year net income</li>
                  <li><strong>Max withdrawal:</strong> 4.25% hard ceiling</li>
                  <li><strong>Cash buffer:</strong> 1.5-2 years (£45k-£60k)</li>
                  <li><strong>Income hierarchy:</strong> 75-80% natural income → rebalancing → cash buffer (last resort)</li>
                </ul>
              </Column>
              <Column lg={7} md={4} sm={4}>
                <ul style={{ color: '#c6c6c6', fontSize: '0.875rem', paddingLeft: '1.5rem', margin: 0 }}>
                  <li><strong>Rebalancing:</strong> Annual review, ±5% tolerance bands</li>
                  <li><strong>Defensive:</strong> 3.5% expected yield</li>
                  <li><strong>Equity:</strong> 3.0% expected yield</li>
                  <li><strong>Real Assets:</strong> 4.5% expected yield</li>
                </ul>
              </Column>
            </Grid>
          </Tile>
        </Column>
      </Grid>
    </div>
  );
};

export default Income;
