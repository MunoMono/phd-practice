const STORAGE_KEY = 'wm_portfolio_mvp_v1';

export const loadPortfolio = (defaultPortfolio) => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error('Failed to load portfolio from localStorage:', error);
  }
  return defaultPortfolio;
};

export const savePortfolio = (portfolio) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(portfolio));
  } catch (error) {
    console.error('Failed to save portfolio to localStorage:', error);
  }
};

export const resetPortfolio = (defaultPortfolio) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(defaultPortfolio));
    return defaultPortfolio;
  } catch (error) {
    console.error('Failed to reset portfolio:', error);
    return defaultPortfolio;
  }
};
