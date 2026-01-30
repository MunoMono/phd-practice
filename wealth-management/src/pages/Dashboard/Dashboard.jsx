import { useState, useMemo } from 'react';
import {
  Grid,
  Column,
  Tile,
  NumberInput,
  Toggle,
  Tag,
  StructuredListWrapper,
  StructuredListHead,
  StructuredListBody,
  StructuredListRow,
  StructuredListCell,
  InlineNotification
} from '@carbon/react';
import { DonutChart, StackedBarChart, LineChart } from '@carbon/charts-react';
import { ChartBullet, Analytics, Collaborate, Dashboard as DashboardIcon } from '@carbon/icons-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import {
  calculateTotalCurrent,
  calculateAllHoldings,
  calculateAllSleeves,
  getDriftBadge,
  formatCurrency,
  formatPercent
} from '../../utils/portfolioCalculations';
import '@carbon/charts-react/styles.css';
import './Dashboard.scss';

const COLORS = ['#0f62fe', '#24a148', '#da1e28', '#f1c21b', '#8a3ffc', '#ff832b'];

const Dashboard = ({ portfolio, onUpdateTolerancePct }) => {
  const [showOnlyActions, setShowOnlyActions] = useState(false);
  const [chartError, setChartError] = useState(null);

  console.log('Dashboard rendering with portfolio:', portfolio);

  // Add data validation
  if (!portfolio) {
    console.error('Portfolio is null or undefined');
    return (
      <div className="dashboard-page">
        <Grid narrow>
          <Column lg={14} md={8} sm={4}>
            <InlineNotification
              kind="error"
              title="Portfolio data is NULL"
              subtitle="Portfolio object is null or undefined. Check App.jsx state initialization."
            />
          </Column>
        </Grid>
      </div>
    );
  }

  if (!portfolio.holdings) {
    console.error('Holdings array is missing:', portfolio);
    return (
      <div className="dashboard-page">
        <Grid narrow>
          <Column lg={14} md={8} sm={4}>
            <InlineNotification
              kind="error"
              title="Holdings missing"
              subtitle={`Portfolio name: ${portfolio.portfolioName || 'N/A'} but holdings array is missing`}
            />
          </Column>
        </Grid>
      </div>
    );
  }

  if (!portfolio.sleeves) {
    console.error('Sleeves array is missing:', portfolio);
    return (
      <div className="dashboard-page">
        <Grid narrow>
          <Column lg={14} md={8} sm={4}>
            <InlineNotification
              kind="error"
              title="Sleeves missing"
              subtitle={`Portfolio has ${portfolio.holdings.length} holdings but no sleeves array`}
            />
          </Column>
        </Grid>
      </div>
    );
  }

  console.log('Portfolio data valid - calculating metrics');
  let totalCurrent, holdingsWithMetrics, sleevesWithMetrics;
  
  try {
    totalCurrent = calculateTotalCurrent(portfolio.holdings);
    console.log('Total current:', totalCurrent);
    holdingsWithMetrics = calculateAllHoldings(portfolio.holdings, totalCurrent);
    console.log('Holdings with metrics:', holdingsWithMetrics.length);
    sleevesWithMetrics = calculateAllSleeves(
      portfolio.sleeves,
      portfolio.holdings,
      totalCurrent,
      portfolio.tolerancePct
    );
    console.log('Sleeves with metrics:', sleevesWithMetrics.length);
  } catch (error) {
    console.error('Error calculating metrics:', error);
    return (
      <div className="dashboard-page" style={{ padding: '2rem', background: '#262626', minHeight: '400px' }}>
        <Grid narrow>
          <Column lg={14} md={8} sm={4}>
            <Tile style={{ background: '#393939', color: '#f4f4f4', padding: '2rem' }}>
              <h3 style={{ color: '#ff6b6b', marginBottom: '1rem' }}>Calculation Error</h3>
              <p style={{ color: '#f4f4f4' }}>{error.message}</p>
              <pre style={{ background: '#161616', padding: '1rem', marginTop: '1rem', color: '#24a148', overflow: 'auto' }}>
                {error.stack}
              </pre>
            </Tile>
          </Column>
        </Grid>
      </div>
    );
  }

  // Prepare Carbon Charts data
  let donutData, donutOptions, driftData, driftOptions;
  try {
    donutData = sleevesWithMetrics.map(sleeve => ({
      group: sleeve.name,
      value: sleeve.sleeveValue
    }));
    console.log('Donut data prepared:', donutData);

    donutOptions = {
      title: 'Sleeve Allocation',
      resizable: true,
      donut: {
        center: {
          label: 'Total',
          numberFormatter: (value) => `£${Math.round(value).toLocaleString()}`
        },
        alignment: 'center'
      },
      height: '400px',
    theme: 'g100',
    legend: {
      alignment: 'center'
    },
    color: {
      scale: {
        'Defensive Income': '#0f62fe',
        'Equity Income & Growth': '#24a148', 
        'Real Assets & Alternatives': '#8a3ffc',
        'Cash/Income Buffer': '#da1e28'
      }
    }
    };

    // Drift chart data
    driftData = sleevesWithMetrics.map(sleeve => ({
      group: sleeve.name,
      key: sleeve.withinBand ? 'Within tolerance' : 'Requires action',
      value: Math.abs(sleeve.sleeveDrift)
    }));
    console.log('Drift data prepared:', driftData);

    driftOptions = {
    title: 'Sleeve Drift from Target',
    axes: {
      left: {
        mapsTo: 'value',
        title: 'Drift (%)',
        scaleType: 'linear'
      },
      bottom: {
        mapsTo: 'group',
        scaleType: 'labels'
      }
    },
    bars: {
      maxWidth: 50
    },
    height: '400px',
    theme: 'g100',
    color: {
      scale: {
        'Within tolerance': '#24a148',
        'Requires action': '#da1e28'
      }
    }
    };
    console.log('Chart options prepared successfully');
  } catch (error) {
    console.error('Error preparing chart data:', error);
    setChartError(error.message);
  }

  // Metrics cards data
  const totalTarget = portfolio.totalTarget || 750000;
  const totalDrift = ((totalCurrent - totalTarget) / totalTarget) * 100;
  const actionsRequired = sleevesWithMetrics.filter(s => !s.withinBand).length;

  // Prepare pie chart data (fallback for recharts)
  const pieData = sleevesWithMetrics.map(sleeve => ({
    name: sleeve.name,
    value: sleeve.sleeveValue
  }));

  // Filter holdings for rebalance suggestions
  const rebalanceHoldings = showOnlyActions
    ? holdingsWithMetrics.filter(h => Math.abs(h.driftPct) >= 2.5)
    : holdingsWithMetrics;

  const getSleeveName = (sleeveId) => {
    const sleeve = portfolio.sleeves.find(s => s.id === sleeveId);
    return sleeve ? sleeve.name : sleeveId;
  };

  return (
    <div className="dashboard-page" style={{ padding: '1rem', background: '#262626', minHeight: '100vh' }}>
      {/* Metrics Header */}
      <Grid narrow className="metrics-grid">\n        <Column lg={3} md={2} sm={2}>
          <Tile className="metric-tile">
            <DashboardIcon size={24} className="metric-icon" />
            <div className="metric-content">
              <p className="metric-label">Total Value</p>
              <p className="metric-value">{formatCurrency(totalCurrent)}</p>
            </div>
          </Tile>
        </Column>
        
        <Column lg={3} md={2} sm={2}>
          <Tile className="metric-tile">
            <ChartBullet size={24} className="metric-icon" />
            <div className="metric-content">
              <p className="metric-label">vs Target</p>
              <p className={`metric-value ${totalDrift >= 0 ? 'positive' : 'negative'}`}>
                {totalDrift >= 0 ? '+' : ''}{totalDrift.toFixed(2)}%
              </p>
            </div>
          </Tile>
        </Column>

        <Column lg={4} md={2} sm={2}>
          <Tile className="metric-tile">
            <Analytics size={24} className="metric-icon" />
            <div className="metric-content">
              <p className="metric-label">Actions Required</p>
              <p className="metric-value">{actionsRequired}</p>
            </div>
          </Tile>
        </Column>

        <Column lg={4} md={2} sm={2}>
          <Tile className="metric-tile">
            <Collaborate size={24} className="metric-icon" />
            <div className="metric-content">
              <p className="metric-label">Tolerance</p>
              <p className="metric-value">±{portfolio.tolerancePct}%</p>
            </div>
          </Tile>
        </Column>
      </Grid>

      <Grid narrow>
        {/* Tolerance Setting */}
        <Column lg={14} md={8} sm={4}>
          <Tile className="dashboard-tile">
            <div className="tile-header">
              <h4>Tolerance Band</h4>
            </div>
            <NumberInput
              id="tolerance-input"
              label="Sleeve tolerance (%)"
              helperText="Trigger rebalancing when sleeve drifts beyond ±X%"
              value={portfolio.tolerancePct}
              onChange={(e, { value }) => {
                if (!isNaN(value)) {
                  onUpdateTolerancePct(value);
                }
              }}
              min={0}
              max={20}
              step={0.5}
            />
          </Tile>
        </Column>

        {/* Carbon Charts */}
        <Column lg={8} md={4} sm={4}>
          <Tile className="dashboard-tile chart-tile">
            {chartError ? (
              <InlineNotification
                kind="warning"
                title="Chart rendering issue"
                subtitle={chartError}
                lowContrast
              />
            ) : (
              <DonutChart data={donutData} options={donutOptions} />
            )}
          </Tile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <Tile className="dashboard-tile chart-tile">
            {chartError ? (
              <InlineNotification
                kind="warning"
                title="Chart rendering issue"
                subtitle={chartError}
                lowContrast
              />
            ) : (
              <StackedBarChart data={driftData} options={driftOptions} />
            )}
          </Tile>
        </Column>

        {/* Sleeve Drift List */}
        <Column lg={8} md={4} sm={4}>
          <Tile className="dashboard-tile">
            <div className="tile-header">
              <h4>Sleeve Drift Analysis</h4>
            </div>
            <StructuredListWrapper>
              <StructuredListHead>
                <StructuredListRow head>
                  <StructuredListCell head>Sleeve</StructuredListCell>
                  <StructuredListCell head>Status</StructuredListCell>
                  <StructuredListCell head>Target</StructuredListCell>
                  <StructuredListCell head>Current</StructuredListCell>
                  <StructuredListCell head>Drift</StructuredListCell>
                </StructuredListRow>
              </StructuredListHead>
              <StructuredListBody>
                {sleevesWithMetrics.map(sleeve => (
                  <StructuredListRow key={sleeve.id}>
                    <StructuredListCell>
                      {sleeve.name}
                      <div className="sleeve-value">
                        {formatCurrency(sleeve.sleeveValue, portfolio.baseCurrency)}
                      </div>
                    </StructuredListCell>
                    <StructuredListCell>
                      <Tag type={sleeve.withinBand ? 'green' : 'red'} size="sm">
                        {sleeve.withinBand ? 'Within' : 'Out of band'}
                      </Tag>
                    </StructuredListCell>
                    <StructuredListCell>{formatPercent(sleeve.targetPct)}</StructuredListCell>
                    <StructuredListCell>{formatPercent(sleeve.sleeveCurrentPct)}</StructuredListCell>
                    <StructuredListCell>
                      <span className={sleeve.sleeveDrift > 0 ? 'drift-positive' : 'drift-negative'}>
                        {formatPercent(sleeve.sleeveDrift)}
                      </span>
                    </StructuredListCell>
                  </StructuredListRow>
                ))}
              </StructuredListBody>
            </StructuredListWrapper>
          </Tile>
        </Column>

        {/* Rebalance Suggestions */}
        <Column lg={14} md={8} sm={4}>
          <Tile className="dashboard-tile">
            <div className="tile-header">
              <h4>Rebalance Suggestions</h4>
              <Toggle
                id="show-actions-toggle"
                labelText="Show only actions"
                labelA="All"
                labelB="Actions only"
                toggled={showOnlyActions}
                onToggle={(checked) => setShowOnlyActions(checked)}
                size="sm"
              />
            </div>
            <StructuredListWrapper>
              <StructuredListHead>
                <StructuredListRow head>
                  <StructuredListCell head>Ticker</StructuredListCell>
                  <StructuredListCell head>Status</StructuredListCell>
                  <StructuredListCell head>Sleeve</StructuredListCell>
                  <StructuredListCell head>Target</StructuredListCell>
                  <StructuredListCell head>Current</StructuredListCell>
                  <StructuredListCell head>Drift</StructuredListCell>
                  <StructuredListCell head>Trade</StructuredListCell>
                </StructuredListRow>
              </StructuredListHead>
              <StructuredListBody>
                {rebalanceHoldings.map(holding => {
                  const badge = getDriftBadge(holding.driftPct);
                  return (
                    <StructuredListRow key={holding.id}>
                      <StructuredListCell>
                        <strong>{holding.ticker}</strong>
                      </StructuredListCell>
                      <StructuredListCell>
                        <Tag type={badge.type} size="sm">
                          {badge.label}
                        </Tag>
                      </StructuredListCell>
                      <StructuredListCell>{getSleeveName(holding.sleeveId)}</StructuredListCell>
                      <StructuredListCell>{formatPercent(holding.targetPct)}</StructuredListCell>
                      <StructuredListCell>{formatPercent(holding.currentPct)}</StructuredListCell>
                      <StructuredListCell>
                        <span className={holding.driftPct > 0 ? 'drift-positive' : 'drift-negative'}>
                          {formatPercent(holding.driftPct)}
                        </span>
                      </StructuredListCell>
                      <StructuredListCell>
                        {holding.trade !== 0 && (
                          <span className={holding.trade > 0 ? 'trade-buy' : 'trade-sell'}>
                            {holding.trade > 0 ? 'BUY' : 'SELL'}{' '}
                            {formatCurrency(Math.abs(holding.trade), portfolio.baseCurrency)}
                          </span>
                        )}
                      </StructuredListCell>
                    </StructuredListRow>
                  );
                })}
              </StructuredListBody>
            </StructuredListWrapper>
          </Tile>
        </Column>
      </Grid>
    </div>
  );
};

export default Dashboard;
