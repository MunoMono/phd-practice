import { Button, DataTable, Pagination, Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from '@carbon/react'
import { useEffect, useMemo, useState } from 'react'

const headers = [
  { key: 'title', header: 'Archival trace' },
  { key: 'year', header: 'Year' },
  { key: 'pid', header: 'PID' },
  { key: 'page', header: 'Page' },
  { key: 'actions', header: '' },
]

const UmapEvidenceTable = ({ points, onInspect }) => {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const rows = useMemo(() => points.map((point) => ({
    id: String(point.id),
    title: point.title || 'Untitled trace',
    year: point.year || 'Undated',
    pid: point.pid || 'Unavailable',
    page: point.sourcePage ? `p. ${point.sourcePage}` : 'Unavailable',
    actions: 'Inspect',
  })), [points])

  useEffect(() => {
    setPage(1)
  }, [points])

  return (
    <DataTable rows={rows} headers={headers} isSortable>
      {({ rows: tableRows, headers: tableHeaders, getHeaderProps, getRowProps, getTableProps }) => {
        const startIndex = (page - 1) * pageSize
        const currentRows = tableRows.slice(startIndex, startIndex + pageSize)

        return (
          <TableContainer>
            <Table {...getTableProps()} aria-label="Visible archival evidence">
              <TableHead>
                <TableRow>
                  {tableHeaders.map((header) => <TableHeader key={header.key} {...getHeaderProps({ header })}>{header.header}</TableHeader>)}
                </TableRow>
              </TableHead>
              <TableBody>
                {currentRows.map((row) => <TableRow key={row.id} {...getRowProps({ row })}>
                  {row.cells.map((cell) => <TableCell key={cell.id}>
                    {cell.info.header === 'actions'
                      ? <Button kind="ghost" size="sm" onClick={() => onInspect(points.find((point) => String(point.id) === row.id))}>Inspect</Button>
                      : cell.value}
                  </TableCell>)}
                </TableRow>)}
              </TableBody>
            </Table>
            <Pagination
              page={page}
              pageSize={pageSize}
              pageSizes={[10, 25, 50]}
              totalItems={rows.length}
              onChange={({ page: nextPage, pageSize: nextPageSize }) => {
                setPage(nextPage)
                setPageSize(nextPageSize)
              }}
            />
          </TableContainer>
        )
      }}
    </DataTable>
  )
}

export default UmapEvidenceTable
