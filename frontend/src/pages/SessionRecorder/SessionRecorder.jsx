import { Tile, DataTable, TableContainer, Table, TableHead, TableRow, TableHeader, TableBody, TableCell, Tag } from '@carbon/react'
import { Recording } from '@carbon/icons-react'
import PageHeader from '../../components/layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'

const SessionRecorder = () => {
  const headers = [
    { key: 'timestamp', header: 'Timestamp' },
    { key: 'query', header: 'Query' },
    { key: 'chunks', header: 'Retrieved chunks' },
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
    <PageGrid className="session-recorder">
      <Column>
        <PageHeader
          title="Session recorder"
          description="Inference logging for explainable AI. Every prediction links to source chunks for manual validation by supervisors."
          actions={(
            <Tag type="green" size="md">
              <Recording size={16} /> XAI enabled
            </Tag>
          )}
        />
      </Column>

      <Column>
        <DataTable rows={rows} headers={headers}>
          {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Recent sessions">
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
    </PageGrid>
  )
}

export default SessionRecorder
