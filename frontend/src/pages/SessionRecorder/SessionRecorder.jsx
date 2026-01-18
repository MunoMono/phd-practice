import { Grid, Column, Tile, DataTable, TableContainer, Table, TableHead, TableRow, TableHeader, TableBody, TableCell, Tag } from '@carbon/react'
import { Recording } from '@carbon/icons-react'
import '../../styles/pages/SessionRecorder.scss'

const SessionRecorder = () => {
  const headers = [
    { key: 'timestamp', header: 'Timestamp' },
    { key: 'query', header: 'Query' },
    { key: 'chunks', header: 'Retrieved Chunks' },
    { key: 'confidence', header: 'Confidence' }
  ]

  const rows = [
    {
      id: '1',
      timestamp: '2025-12-07 10:23:45',
      query: 'Analyze methodological shifts in early papers',
      chunks: '5',
      confidence: '0.87'
    }
  ]

  return (
    <Grid className="session-recorder" fullWidth>
      <Column lg={16} md={8} sm={4}>
        <div className="recorder__header">
          <div>
            <h1>Session Recorder</h1>
            <p className="recorder__description">
              Inference logging for explainable AI. 
              Every prediction links to source chunks for manual validation by supervisors.
            </p>
          </div>
          <Tag type="green" size="md">
            <Recording size={16} /> XAI Enabled
          </Tag>
        </div>
      </Column>

      <Column lg={16} md={8} sm={4}>
        <DataTable rows={rows} headers={headers}>
          {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Recent Sessions">
              <Table {...getTableProps()}>
                <TableHead>
                  <TableRow>
                    {headers.map((header) => (
                      <TableHeader {...getHeaderProps({ header })}>
                        {header.header}
                      </TableHeader>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow {...getRowProps({ row })}>
                      {row.cells.map((cell) => (
                        <TableCell key={cell.id}>{cell.value}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      </Column>
    </Grid>
  )
}

export default SessionRecorder
