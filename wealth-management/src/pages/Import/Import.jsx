import { useState } from 'react';
import {
  Grid,
  Column,
  Tile,
  TextArea,
  Button,
  InlineNotification
} from '@carbon/react';
import { Download, Upload } from '@carbon/icons-react';
import { exportToCSV, downloadCSV, importCSV } from '../../utils/csvHelpers';
import './Import.scss';

const Import = ({ portfolio, onImportPortfolio }) => {
  const [csvText, setCsvText] = useState('');
  const [notification, setNotification] = useState(null);

  const handleExport = () => {
    try {
      const { csv, filename } = exportToCSV(portfolio);
      downloadCSV(csv, filename);
      setNotification({ kind: 'success', title: 'Export successful', subtitle: `Downloaded ${filename}` });
      setTimeout(() => setNotification(null), 5000);
    } catch (error) {
      setNotification({ kind: 'error', title: 'Export failed', subtitle: error.message });
      setTimeout(() => setNotification(null), 5000);
    }
  };

  const handleImport = () => {
    try {
      const updatedPortfolio = importCSV(csvText, portfolio);
      onImportPortfolio(updatedPortfolio);
      setNotification({ kind: 'success', title: 'Import successful', subtitle: `Imported ${updatedPortfolio.holdings.length} holdings` });
      setCsvText('');
      setTimeout(() => setNotification(null), 5000);
    } catch (error) {
      setNotification({ kind: 'error', title: 'Import failed', subtitle: error.message });
      setTimeout(() => setNotification(null), 5000);
    }
  };

  const previewCSV = () => {
    const { csv } = exportToCSV(portfolio);
    const lines = csv.split('\n').slice(0, 6); // Header + 5 rows
    return lines.join('\n');
  };

  return (
    <div className="import-page">
      <Grid>
        {notification && (
          <Column lg={16} md={8} sm={4}>
            <InlineNotification
              kind={notification.kind}
              title={notification.title}
              subtitle={notification.subtitle}
              onCloseButtonClick={() => setNotification(null)}
            />
          </Column>
        )}

        <Column lg={8} md={4} sm={4}>
          <Tile className="import-tile">
            <h4>Export Portfolio</h4>
            <p>Download current portfolio as CSV file</p>
            <Button
              renderIcon={Download}
              onClick={handleExport}
              size="md"
            >
              Export CSV
            </Button>
            
            <div className="preview-section">
              <h5>Preview (first 5 holdings):</h5>
              <pre className="csv-preview">{previewCSV()}</pre>
            </div>
          </Tile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <Tile className="import-tile">
            <h4>Import Portfolio</h4>
            <p>Paste CSV text below and click Import to replace current holdings</p>
            <TextArea
              id="csv-import"
              labelText="CSV Data"
              placeholder="sleeve,holding,ticker,targetPct,currentValue,notes&#10;..."
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              rows={10}
            />
            <div className="import-actions">
              <Button
                renderIcon={Upload}
                onClick={handleImport}
                disabled={!csvText.trim()}
                size="md"
              >
                Import CSV
              </Button>
              <Button
                kind="secondary"
                onClick={() => setCsvText('')}
                disabled={!csvText.trim()}
                size="md"
              >
                Clear
              </Button>
            </div>

            <div className="import-help">
              <h5>CSV Format:</h5>
              <ul>
                <li>Required columns: sleeve, holding, ticker, targetPct</li>
                <li>Optional columns: currentValue, notes</li>
                <li>Use quotes for text fields with commas</li>
                <li>New sleeves will be created automatically with targetPct=0</li>
              </ul>
            </div>
          </Tile>
        </Column>
      </Grid>
    </div>
  );
};

export default Import;
