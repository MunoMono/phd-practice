import { useState } from 'react';
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
  StructuredListCell
} from '@carbon/react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import {
  calculateTotalCurrent,
  calculateAllHoldings,
  calculateAllSleeves,
  getDriftBadge,
  formatCurrency,
  formatPercent
} from '../../utils/portfolioCalculations';
import './Dashboard.scss';

const COLORS = ['#0f62fe', '#24a148', '#da1e28', '#f1c21b', '#8a3ffc', '#ff832b'];

const Dashboard = ({ portfolio, onUpdateTolerancePct }) => {
  const [showOnlyActions, setShowOnlyActions] = useState(false);

  const totalCurrent = calculateTotalCurrent(portfolio.holdings);
  const holdingsWithMetrics = calculateAllHoldings(portfolio.holdings, totalCurrent);
  const sleevesWithMetrics = calculateAllSleeves(
    portfolio.sleeves,
    portfolio.holdings,
    totalCurrent,
    portfolio.tolerancePct
  );

  // Prepare pie chart data
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
    <div className="dashboard-page">
      <Grid>
        {/* Tolerance Setting */}
        <Column lg={16} md={8} sm={4}>
          <Tile className="dashboard-tile">
            <div className="tile-header">
              <h4>Tolerance Band</h4>
            </div>
            <NumberInput
              id="tolerance-input"
              label="Sleeve tolerance (%)"
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

        {/* Sleeve Allocation Chart */}
        <Column lg={8} md={4} sm={4}>
          <Tile className="dashboard-tile">
            <div className="tile-header">
              <h4>Sleeve Allocation</h4>
            </div>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => formatCurrency(value, portfolio.baseCurrency)} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
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
        <Column lg={16} md={8} sm={4}>
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
