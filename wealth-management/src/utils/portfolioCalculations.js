// Calculate total current value
export const calculateTotalCurrent = (holdings) => {
  return holdings.reduce((sum, h) => sum + (h.currentValue || 0), 0);
};

// Calculate per-holding metrics
export const calculateHoldingMetrics = (holding, totalCurrent) => {
  const safeTotal = totalCurrent || 1; // Avoid divide-by-zero
  const currentPct = (holding.currentValue / safeTotal) * 100;
  const driftPct = currentPct - holding.targetPct;
  const targetValue = (holding.targetPct / 100) * safeTotal;
  const trade = targetValue - holding.currentValue;

  return {
    ...holding,
    currentPct,
    driftPct,
    targetValue,
    trade,
    tradeAction: trade > 0 ? 'BUY' : trade < 0 ? 'SELL' : 'HOLD'
  };
};

// Calculate all holdings with metrics
export const calculateAllHoldings = (holdings, totalCurrent) => {
  return holdings.map(h => calculateHoldingMetrics(h, totalCurrent));
};

// Calculate sleeve metrics
export const calculateSleeveMetrics = (sleeve, holdings, totalCurrent, tolerancePct) => {
  const sleeveHoldings = holdings.filter(h => h.sleeveId === sleeve.id);
  const sleeveValue = sleeveHoldings.reduce((sum, h) => sum + (h.currentValue || 0), 0);
  const safeTotal = totalCurrent || 1;
  const sleeveCurrentPct = (sleeveValue / safeTotal) * 100;
  const sleeveDrift = sleeveCurrentPct - sleeve.targetPct;
  const withinBand = Math.abs(sleeveDrift) <= tolerancePct;

  return {
    ...sleeve,
    sleeveValue,
    sleeveCurrentPct,
    sleeveDrift,
    withinBand
  };
};

// Calculate all sleeves with metrics
export const calculateAllSleeves = (sleeves, holdings, totalCurrent, tolerancePct) => {
  return sleeves.map(s => calculateSleeveMetrics(s, holdings, totalCurrent, tolerancePct));
};

// Get drift badge info for a holding
export const getDriftBadge = (driftPct) => {
  const absDrift = Math.abs(driftPct);
  
  if (absDrift < 0.25) {
    return { label: 'On target', type: 'green' };
  } else if (absDrift < 1.00) {
    return { label: 'Minor drift', type: 'gray' };
  } else if (absDrift < 2.50) {
    return { label: 'Drifting', type: 'yellow' };
  } else {
    return { label: 'Action', type: 'red' };
  }
};

// Format currency
export const formatCurrency = (value, currency = 'GBP') => {
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(value);
};

// Format percent
export const formatPercent = (value) => {
  return `${value.toFixed(2)}%`;
};

// Generate random hex ID
export const generateId = () => {
  return `H_${Math.random().toString(16).substr(2, 8)}`;
};
