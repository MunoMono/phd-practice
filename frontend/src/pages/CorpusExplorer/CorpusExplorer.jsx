import { InlineNotification, Tag } from '@carbon/react'
import { Search } from '@carbon/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getAuthorityRegister, getAuthoritySummary } from '../../api/authorities'
import { listDocuments, getDocument, getDocumentAnnotations, getDocumentChunks, syncDocumentMetadata } from '../../api/documents'
import { getArchiveRecordSiblings, autocompleteSearch } from '../../api/search'
import CorpusSearchPanel from '../../components/corpus/CorpusSearchPanel'
import DocumentChunkReader from '../../components/corpus/DocumentChunkReader'
import DocumentTable from '../../components/corpus/DocumentTable'
import DocumentDetailPanel from '../../components/corpus/DocumentDetailPanel'
import PageHeader from '../../components/layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'

const defaultFilters = {
  keyword: '',
  year: '',
  status: '',
  authorityId: ''
}

const CorpusExplorer = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const handoffDocumentId = searchParams.get('documentId') || ''
  const handoffPid = searchParams.get('pid') || ''
  const handoffRequested = searchParams.has('documentId') || searchParams.has('pid')
  const [filters, setFilters] = useState(defaultFilters)
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [handoffError, setHandoffError] = useState('')
  const [selectedDocumentId, setSelectedDocumentId] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [selectedDetail, setSelectedDetail] = useState(null)
  const [suggestions, setSuggestions] = useState({ documents: [], themes: [], entities: [] })
  const [authoritySummary, setAuthoritySummary] = useState(null)
  const [authorityRecords, setAuthorityRecords] = useState([])
  const [chunkReader, setChunkReader] = useState({ chunks: [], access: {}, loading: false, error: '' })
  const [selectedChunks, setSelectedChunks] = useState({})

  useEffect(() => {
    let isCancelled = false

    const loadDocuments = async () => {
      setLoading(true)
      setError('')
      setHandoffError('')

      try {
        const payload = await listDocuments({
          year: filters.year || undefined,
          status: filters.status || undefined,
          authority_id: filters.authorityId || undefined
        })

        if (isCancelled) {
          return
        }

        setDocuments(payload.documents)

        if (handoffRequested) {
          const requestedDocument = handoffDocumentId
            ? payload.documents.find((document) => document.id === handoffDocumentId)
            : null
          const requestedPid = requestedDocument?.attached_media_pid || requestedDocument?.pid || ''
          const pidMatches = !handoffPid || String(requestedPid) === handoffPid

          if (!requestedDocument || !pidMatches) {
            setSelectedDetail(null)
            setSelectedDocumentId(null)
            setHandoffError('The requested local source record could not be matched to the current Sources dataset.')
            return
          }

          setSelectedDocumentId(requestedDocument.id)
          return
        }

        setSelectedDocumentId((currentSelectedId) => {
          if (payload.documents.length === 0) {
            setSelectedDetail(null)
            return null
          }

          const selectionExists = currentSelectedId && payload.documents.some((document) => document.id === currentSelectedId)
          return selectionExists ? currentSelectedId : payload.documents[0].id
        })
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError.message || 'Failed to load corpus documents.')
        }
      } finally {
        if (!isCancelled) {
          setLoading(false)
        }
      }
    }

    loadDocuments()

    return () => {
      isCancelled = true
    }
  }, [filters.year, filters.status, filters.authorityId, handoffDocumentId, handoffPid, handoffRequested])

  useEffect(() => {
    let isCancelled = false

    const loadAuthorityContext = async () => {
      try {
        const [summary, records] = await Promise.all([
          getAuthoritySummary(),
          getAuthorityRegister({ limit: 500 })
        ])
        if (!isCancelled) {
          setAuthoritySummary(summary)
          setAuthorityRecords(records)
        }
      } catch (authorityError) {
        if (!isCancelled) {
          console.error('Failed to load authority summary:', authorityError)
        }
      }
    }

    loadAuthorityContext()

    return () => {
      isCancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedDocumentId) {
      setSelectedDetail(null)
      return
    }

    const selectedDocument = documents.find((document) => document.id === selectedDocumentId)

    if (!selectedDocument) {
      return
    }

    let isCancelled = false

    const loadDocumentDetail = async () => {
      setDetailLoading(true)

      try {
        const [detail, annotations, related] = await Promise.all([
          getDocument(selectedDocument.id),
          getDocumentAnnotations(selectedDocument.id),
          getArchiveRecordSiblings(selectedDocument.id).catch(() => ({ relatedDocuments: [], metadata: {} }))
        ])

        if (isCancelled) {
          return
        }

        setSelectedDetail({
          document: {
            ...selectedDocument,
            ...detail,
            pid: annotations.pid || selectedDocument.pid || null,
            page_count: annotations.page_count ?? detail.page_count ?? null
          },
          annotations,
          relatedDocuments: related.relatedDocuments || []
        })
      } catch (detailError) {
        if (!isCancelled) {
          setSelectedDetail({
            document: selectedDocument,
            annotations: null,
            relatedDocuments: [],
            error: detailError.message || 'Failed to load document detail.'
          })
        }
      } finally {
        if (!isCancelled) {
          setDetailLoading(false)
        }
      }
    }

    loadDocumentDetail()

    return () => {
      isCancelled = true
    }
  }, [documents, selectedDocumentId])

  useEffect(() => {
    if (!selectedDocumentId) {
      setChunkReader({ chunks: [], access: {}, loading: false, error: '' })
      return undefined
    }

    let isCancelled = false
    setChunkReader({ chunks: [], access: {}, loading: true, error: '' })
    getDocumentChunks(selectedDocumentId, { limit: 100 })
      .then((payload) => {
        if (!isCancelled) {
          setChunkReader({ chunks: payload.chunks, access: payload.access, loading: false, error: '' })
        }
      })
      .catch((chunkError) => {
        if (!isCancelled) {
          setChunkReader({ chunks: [], access: {}, loading: false, error: chunkError.message || 'Failed to load permitted passages.' })
        }
      })

    return () => { isCancelled = true }
  }, [selectedDocumentId])

  useEffect(() => {
    const query = filters.keyword.trim()

    if (query.length < 2) {
      setSuggestions({ documents: [], themes: [], entities: [] })
      return
    }

    const timeoutId = window.setTimeout(async () => {
      try {
        const nextSuggestions = await autocompleteSearch({ q: query })
        setSuggestions(nextSuggestions)
      } catch (autocompleteError) {
        console.error('Failed to fetch autocomplete suggestions:', autocompleteError)
      }
    }, 250)

    return () => window.clearTimeout(timeoutId)
  }, [filters.keyword])

  const filteredDocuments = useMemo(() => {
    const query = filters.keyword.trim().toLowerCase()

    if (!query) {
      return documents
    }

    return documents.filter((document) => {
      return [document.title, document.id, document.pid]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(query))
    })
  }, [documents, filters.keyword])

  const handleDocumentSelect = (document) => {
    setSelectedDocumentId(document.id)
  }

  const handleMetadataRefresh = async () => {
    if (!selectedDocumentId) {
      return null
    }

    const result = await syncDocumentMetadata(selectedDocumentId)
    const [document, annotations] = await Promise.all([
      getDocument(selectedDocumentId),
      getDocumentAnnotations(selectedDocumentId)
    ])

    setSelectedDetail((current) => ({
      ...(current || {}),
      document: {
        ...(current?.document || {}),
        ...document,
        pid: annotations.pid || document.pid || null,
        page_count: annotations.page_count ?? document.page_count ?? null
      },
      annotations,
      syncResult: result
    }))
    setDocuments((current) => current.map((item) => (
      item.id === selectedDocumentId ? { ...item, ...document } : item
    )))
    return result
  }

  const handleToggleChunk = (chunk) => {
    setSelectedChunks((current) => {
      if (current[chunk.chunk_id]) {
        const remaining = { ...current }
        delete remaining[chunk.chunk_id]
        return remaining
      }
      return { ...current, [chunk.chunk_id]: chunk }
    })
  }

  const handleSynthesizeSelected = (question, chunkIds) => {
    const params = new URLSearchParams({ query: question, selectedChunkIds: chunkIds.join(',') })
    navigate(`/source-interrogation?${params.toString()}`)
  }

  return (
    <PageGrid className="corpus-explorer-page">
      <Column>
        <PageHeader
          title="Sources"
          description="Inspect DDR records, ingestion status, metadata, PID links, and source handoffs before moving into interrogation or analysis."
          actions={(
            <Tag type="blue" size="md">
              <Search size={16} /> Endpoint-driven
            </Tag>
          )}
        />
      </Column>

      <Column>
        <InlineNotification
          lowContrast
          kind="info"
          title="Methodological distinction"
          subtitle="This view separates corpus-control policy, archive / catalogue metadata, and source provenance so researchers can inspect corpus decisions without mistaking them for source-document evidence."
        />
      </Column>

      {authoritySummary && (
        <Column>
          <InlineNotification
            lowContrast
            kind="info"
            title="Archive authorities"
            subtitle={`${authoritySummary.totalRecords} authority records across ${authoritySummary.count} types. Authorities support future entity resolution, filtering and controlled query expansion. They are not source-document evidence.`}
          />
        </Column>
      )}

      {error && (
        <Column>
          <InlineNotification
            lowContrast
            kind="error"
            title="Corpus load failed"
            subtitle={error}
          />
        </Column>
      )}

      {handoffError && (
        <Column>
          <InlineNotification
            lowContrast
            kind="error"
            title="Requested source could not be loaded"
            subtitle={handoffError}
          />
        </Column>
      )}

      <Column lg={3}>
        <CorpusSearchPanel
          filters={filters}
          suggestions={suggestions}
          authorityRecords={authorityRecords}
          onChange={setFilters}
          onReset={() => setFilters(defaultFilters)}
        />
      </Column>

      <Column lg={7}>
        <DocumentTable
          documents={filteredDocuments}
          loading={loading}
          selectedDocumentId={selectedDocumentId}
          onSelect={handleDocumentSelect}
        />
      </Column>

      <Column lg={5}>
        <DocumentDetailPanel
          detail={selectedDetail}
          loading={detailLoading}
          authoritySummary={authoritySummary}
          onRefreshMetadata={handleMetadataRefresh}
          onTraceEvidence={() => navigate('/source-interrogation')}
          onViewAnalytics={() => navigate('/semantic-atlas')}
          onInspectMissingness={() => {
            const source = selectedDetail?.document
            const params = new URLSearchParams()
            if (source?.id) params.set('sourceDocumentId', source.id)
            if (source?.pid) params.set('pid', source.pid)
            if (source?.page_count) params.set('pageRange', `1-${source.page_count}`)
            navigate(`/absences${params.size ? `?${params.toString()}` : ''}`)
          }}
        />
      </Column>

      <Column lg={10}>
        <DocumentChunkReader
          chunks={chunkReader.chunks}
          loading={chunkReader.loading}
          error={chunkReader.error}
          access={chunkReader.access}
          selectedChunks={selectedChunks}
          onToggleChunk={handleToggleChunk}
          onSynthesize={handleSynthesizeSelected}
        />
      </Column>
    </PageGrid>
  )
}

export default CorpusExplorer