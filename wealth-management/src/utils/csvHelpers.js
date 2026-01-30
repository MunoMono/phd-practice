// Export portfolio to CSV
export const exportToCSV = (portfolio) => {
  const { portfolioName, sleeves, holdings } = portfolio;
  
  // Create header
  const header = 'sleeve,holding,ticker,targetPct,currentValue,notes\n';
  
  // Create rows
  const rows = holdings.map(h => {
    const sleeve = sleeves.find(s => s.id === h.sleeveId);
    const sleeveName = sleeve ? sleeve.name : '';
    
    // Escape quotes by doubling them, then wrap in quotes
    const escapedSleeve = `"${sleeveName.replace(/"/g, '""')}"`;
    const escapedHolding = `"${h.holding.replace(/"/g, '""')}"`;
    const escapedTicker = `"${h.ticker.replace(/"/g, '""')}"`;
    const escapedNotes = `"${(h.notes || '').replace(/"/g, '""')}"`;
    
    return `${escapedSleeve},${escapedHolding},${escapedTicker},"${h.targetPct}","${h.currentValue || 0}",${escapedNotes}`;
  }).join('\n');
  
  const csv = header + rows;
  
  // Create filename
  const filename = `${portfolioName.replace(/\s+/g, '_')}.csv`;
  
  return { csv, filename };
};

// Download CSV file
export const downloadCSV = (csv, filename) => {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

// Parse CSV text
export const parseCSV = (csvText) => {
  const lines = csvText.trim().split('\n');
  if (lines.length < 2) {
    throw new Error('CSV must have at least a header and one data row');
  }
  
  // Simple CSV parser that handles quoted fields
  const parseLine = (line) => {
    const fields = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      const next = line[i + 1];
      
      if (char === '"') {
        if (inQuotes && next === '"') {
          // Double quote = escaped quote
          current += '"';
          i++; // Skip next quote
        } else {
          // Toggle quote mode
          inQuotes = !inQuotes;
        }
      } else if (char === ',' && !inQuotes) {
        fields.push(current);
        current = '';
      } else {
        current += char;
      }
    }
    fields.push(current); // Last field
    
    return fields;
  };
  
  const header = parseLine(lines[0].toLowerCase());
  const data = lines.slice(1).map(line => {
    const values = parseLine(line);
    const row = {};
    header.forEach((key, i) => {
      row[key.trim()] = values[i] || '';
    });
    return row;
  });
  
  return data;
};

// Import CSV data into portfolio
export const importCSV = (csvText, portfolio) => {
  const data = parseCSV(csvText);
  
  // Validate required columns
  const requiredCols = ['sleeve', 'holding', 'ticker', 'targetpct'];
  const firstRow = data[0] || {};
  const missingCols = requiredCols.filter(col => !(col in firstRow));
  
  if (missingCols.length > 0) {
    throw new Error(`Missing required columns: ${missingCols.join(', ')}`);
  }
  
  const newSleeves = [...portfolio.sleeves];
  const newHoldings = [];
  
  // Map sleeve names to IDs (case-insensitive)
  const sleeveMap = new Map();
  portfolio.sleeves.forEach(s => {
    sleeveMap.set(s.name.toLowerCase(), s.id);
  });
  
  data.forEach((row, index) => {
    const sleeveName = row.sleeve?.trim() || '';
    const holding = row.holding?.trim() || 'Unnamed holding';
    const ticker = row.ticker?.trim() || '';
    const targetPct = parseFloat(row.targetpct) || 0;
    const currentValue = parseFloat(row.currentvalue || '0') || 0;
    const notes = row.notes?.trim() || '';
    
    // Find or create sleeve
    let sleeveId = sleeveMap.get(sleeveName.toLowerCase());
    if (!sleeveId) {
      // Create new sleeve
      sleeveId = sleeveName.toLowerCase().replace(/\s+/g, '_');
      const newSleeve = {
        id: sleeveId,
        name: sleeveName,
        targetPct: 0
      };
      newSleeves.push(newSleeve);
      sleeveMap.set(sleeveName.toLowerCase(), sleeveId);
    }
    
    // Create holding
    const holdingId = ticker || `H_${Math.random().toString(16).substr(2, 8)}`;
    newHoldings.push({
      id: holdingId,
      sleeveId,
      holding,
      ticker,
      targetPct,
      currentValue,
      notes
    });
  });
  
  return {
    ...portfolio,
    sleeves: newSleeves,
    holdings: newHoldings
  };
};
