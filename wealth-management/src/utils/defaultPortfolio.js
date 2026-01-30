export const DEFAULT_PORTFOLIO = {
  portfolioName: "Model Portfolio v0.2",
  baseCurrency: "GBP",
  totalTarget: 750000,
  tolerancePct: 5,
  sleeves: [
    { id: "defensive", name: "Defensive Income", targetPct: 35 },
    { id: "equity", name: "Equity Income & Growth", targetPct: 35 },
    { id: "real", name: "Real Assets & Alternatives", targetPct: 20 },
    { id: "cash", name: "Cash / Income Buffer", targetPct: 10 }
  ],
  holdings: [
    { id: "AGBP", sleeveId: "defensive", holding: "iShares Core Global Aggregate Bond UCITS ETF GBP Hedged (Dist)", ticker: "AGBP", targetPct: 22, notes: "Core global IG bonds, GBP-hedged", currentValue: 165000 },
    { id: "IGCB", sleeveId: "defensive", holding: "Invesco GBP Corporate Bond UCITS ETF Dist", ticker: "IGCB", targetPct: 8, notes: "GBP investment-grade corporates (Invesco)", currentValue: 60000 },
    { id: "GLTP", sleeveId: "defensive", holding: "Invesco UK Gilts UCITS ETF Dist", ticker: "GLTP", targetPct: 5, notes: "UK gilt ballast / liquidity (Invesco)", currentValue: 37500 },

    { id: "VHYL", sleeveId: "equity", holding: "Vanguard FTSE All-World High Dividend Yield UCITS ETF (Dist)", ticker: "VHYL", targetPct: 17, notes: "Broad global dividend equity core", currentValue: 127500 },
    { id: "GBDV", sleeveId: "equity", holding: "SPDR S&P Global Dividend Aristocrats UCITS ETF (Dist)", ticker: "GBDV", targetPct: 10, notes: "Dividend-quality screen; diversifier", currentValue: 75000 },
    { id: "IUKD", sleeveId: "equity", holding: "iShares UK Dividend UCITS ETF (Dist)", ticker: "IUKD", targetPct: 3, notes: "Small UK income satellite", currentValue: 22500 },
    { id: "STOCKS", sleeveId: "equity", holding: "Individual stock basket (12+ names; max 3% per name)", ticker: "STOCKS", targetPct: 5, notes: "Hands-on satellite; rules-based sizing", currentValue: 37500 },

    { id: "INPP", sleeveId: "real", holding: "International Public Partnerships (Investment Trust)", ticker: "INPP", targetPct: 4, notes: "Infrastructure-style contracted cashflows", currentValue: 30000 },
    { id: "HICL", sleeveId: "real", holding: "HICL Infrastructure (Investment Trust)", ticker: "HICL", targetPct: 3, notes: "Infrastructure-style contracted cashflows", currentValue: 22500 },
    { id: "INFR", sleeveId: "real", holding: "iShares Global Infrastructure UCITS ETF (Dist)", ticker: "INFR", targetPct: 3, notes: "Global infra diversification", currentValue: 22500 },
    { id: "IWDP", sleeveId: "real", holding: "iShares Developed Markets Property Yield UCITS ETF (Dist)", ticker: "IWDP", targetPct: 7, notes: "Global REIT/property yield", currentValue: 52500 },
    { id: "TFIF", sleeveId: "real", holding: "TwentyFour Income Fund (Investment Trust)", ticker: "TFIF", targetPct: 3, notes: "Credit/asset-backed income (small, monitored)", currentValue: 22500 },

    { id: "GBP_CASH", sleeveId: "cash", holding: "GBP cash at IBKR (or equivalent)", ticker: "GBP CASH", targetPct: 5, notes: "Liquidity + optional FX dry powder", currentValue: 37500 },
    { id: "ERNS", sleeveId: "cash", holding: "iShares £ Ultrashort Bond UCITS ETF GBP (Dist)", ticker: "ERNS", targetPct: 5, notes: "Cash-like ultrashort IG bond sleeve", currentValue: 37500 }
  ]
};
