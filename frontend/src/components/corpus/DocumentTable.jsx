import {
  DataTable,
  Loading,
  Pagination,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  Tile
} from '@carbon/react'
import { useEffect, useState } from 'react'

const headers = [
  { key: 'title', header: 'Title' },
  { key: 'publication_year', header: 'Year' },
  { key: 'processing_status', header: 'Status' },
  { key: 'id', header: 'Document ID' }
]

const statusTagType = {
  completed: 'green',
  pending: 'blue',
  failed: 'red'
}

const DocumentTable = ({ documents, loading, selectedDocumentId, onSelect }) => {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  useEffect(() => {
    setPage(1)
  }, [documents])

  if (loading) {
    return (
      <Tile>
        <Loading description="Loading corpus documents..." withOverlay={false} />
      </Tile>
    )
  }

  if (documents.length === 0) {
    return (
      <Tile>
        <h3>Corpus documents</h3>
        <p>No indexed DDR documents found. Sync or ingest corpus first.</p>
      </Tile>
    )
  }

  const startIndex = (page - 1) * pageSize
  const paginatedDocuments = documents.slice(startIndex, startIndex + pageSize)

  return (
    <Tile>
      <DataTable
        rows={paginatedDocuments.map((document) => ({
          id: document.id,
          title: document.title,
          publication_year: document.publication_year || 'N/A',
          processing_status: document.processing_status
        }))}
        headers={headers}
      >
        {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer
              className="corpus-document-table"
              title="Corpus documents"
              description="Select a document to inspect available annotation, PID, and archive-record metadata."
            >
            <Table {...getTableProps()}>
              <TableHead>
                <TableRow>
                  {headers.map((header) => (
                    <TableHeader key={header.key} {...getHeaderProps({ header })}>
                      {header.header}
                    </TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => (
                  <TableRow
                    key={row.id}
                    {...getRowProps({ row })}
                    onClick={() => onSelect(paginatedDocuments.find((document) => document.id === row.id))}
                    className={row.id === selectedDocumentId ? 'app-table-row--interactive app-table-row--selected' : 'app-table-row--interactive'}
                  >
                    {row.cells.map((cell) => (
                      <TableCell key={cell.id}>
                        {cell.info.header === 'processing_status' ? (
                          <Tag type={statusTagType[cell.value] || 'gray'}>{cell.value}</Tag>
                        ) : (
                          cell.value
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pagination
              page={page}
              pageSize={pageSize}
              pageSizes={[10, 20, 50]}
              totalItems={documents.length}
              onChange={({ page: nextPage, pageSize: nextPageSize }) => {
                setPage(nextPage)
                setPageSize(nextPageSize)
              }}
            />
          </TableContainer>
        )}
      </DataTable>
    </Tile>
  )
}

export default DocumentTable