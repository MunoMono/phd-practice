import { useState } from 'react';
import {
  DataTable,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  TextInput,
  NumberInput,
  Dropdown,
  TextArea,
  Button
} from '@carbon/react';
import { TrashCan, Add } from '@carbon/icons-react';
import { generateId } from '../../utils/portfolioCalculations';
import './Holdings.scss';

const Holdings = ({ portfolio, onUpdateHolding, onDeleteHolding, onAddHolding }) => {
  const headers = [
    { key: 'sleeve', header: 'Sleeve' },
    { key: 'ticker', header: 'Ticker' },
    { key: 'holding', header: 'Holding' },
    { key: 'targetPct', header: 'Target %' },
    { key: 'currentValue', header: 'Current Value' },
    { key: 'notes', header: 'Notes' },
    { key: 'actions', header: 'Actions' }
  ];

  const sleeveItems = portfolio.sleeves.map(s => ({
    id: s.id,
    label: s.name
  }));

  const handleFieldChange = (holdingId, field, value) => {
    const holding = portfolio.holdings.find(h => h.id === holdingId);
    if (holding) {
      onUpdateHolding(holdingId, { ...holding, [field]: value });
    }
  };

  const handleAddHolding = () => {
    const newHolding = {
      id: generateId(),
      sleeveId: portfolio.sleeves[0]?.id || 'defensive',
      holding: 'New holding',
      ticker: '',
      targetPct: 0,
      currentValue: 0,
      notes: ''
    };
    onAddHolding(newHolding);
  };

  return (
    <div className="holdings-page">
      <div className="holdings-header">
        <h3>Holdings Editor</h3>
        <Button
          renderIcon={Add}
          onClick={handleAddHolding}
          size="sm"
        >
          Add Holding
        </Button>
      </div>

      <DataTable rows={portfolio.holdings} headers={headers}>
        {({ rows, headers, getHeaderProps, getTableProps }) => (
          <TableContainer>
            <Table {...getTableProps()} className="holdings-table">
              <TableHead>
                <TableRow>
                  {headers.map(header => (
                    <TableHeader {...getHeaderProps({ header })} key={header.key}>
                      {header.header}
                    </TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {portfolio.holdings.map(holding => (
                  <TableRow key={holding.id}>
                    <TableCell>
                      <Dropdown
                        id={`sleeve-${holding.id}`}
                        items={sleeveItems}
                        selectedItem={sleeveItems.find(s => s.id === holding.sleeveId)}
                        itemToString={(item) => item?.label || ''}
                        onChange={({ selectedItem }) => {
                          if (selectedItem) {
                            handleFieldChange(holding.id, 'sleeveId', selectedItem.id);
                          }
                        }}
                        size="sm"
                      />
                    </TableCell>
                    <TableCell>
                      <TextInput
                        id={`ticker-${holding.id}`}
                        value={holding.ticker}
                        onChange={(e) => handleFieldChange(holding.id, 'ticker', e.target.value)}
                        size="sm"
                        hideLabel
                        labelText="Ticker"
                      />
                    </TableCell>
                    <TableCell>
                      <TextInput
                        id={`holding-${holding.id}`}
                        value={holding.holding}
                        onChange={(e) => handleFieldChange(holding.id, 'holding', e.target.value)}
                        size="sm"
                        hideLabel
                        labelText="Holding"
                      />
                    </TableCell>
                    <TableCell>
                      <NumberInput
                        id={`targetPct-${holding.id}`}
                        value={holding.targetPct}
                        onChange={(e, { value }) => {
                          const num = parseFloat(value) || 0;
                          handleFieldChange(holding.id, 'targetPct', num);
                        }}
                        size="sm"
                        hideLabel
                        labelText="Target %"
                        min={0}
                        max={100}
                        step={0.5}
                      />
                    </TableCell>
                    <TableCell>
                      <NumberInput
                        id={`currentValue-${holding.id}`}
                        value={holding.currentValue}
                        onChange={(e, { value }) => {
                          const num = parseFloat(value) || 0;
                          handleFieldChange(holding.id, 'currentValue', num);
                        }}
                        size="sm"
                        hideLabel
                        labelText="Current Value"
                        min={0}
                        step={1000}
                      />
                    </TableCell>
                    <TableCell>
                      <TextArea
                        id={`notes-${holding.id}`}
                        value={holding.notes || ''}
                        onChange={(e) => handleFieldChange(holding.id, 'notes', e.target.value)}
                        rows={1}
                        hideLabel
                        labelText="Notes"
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        kind="ghost"
                        renderIcon={TrashCan}
                        iconDescription="Delete"
                        hasIconOnly
                        onClick={() => onDeleteHolding(holding.id)}
                        size="sm"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DataTable>
    </div>
  );
};

export default Holdings;
