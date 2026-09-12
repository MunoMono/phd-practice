import {
  Button,
  InlineNotification,
  Select,
  SelectItem,
  Tag,
  TextArea,
  TextInput,
  Tile
} from '@carbon/react'
import { DataVis_4 } from '@carbon/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createAtlasCoverageMissingness, createEmbeddingReadinessReview, getEmbeddingReadiness, getUmapProjection } from '../../api/viz'
import PanelHeader from '../../components/layout/PanelHeader'
import PageHeader from '../../components/layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import UmapProjection from '../../components/visualizations/UmapProjection'
import UmapPointDetail from '../../components/visualizations/UmapPointDetail'
import UmapEvidenceTable from '../../components/visualizations/UmapEvidenceTable'
import ClusterPanel from '../../components/visualizations/ClusterPanel'
import ConceptBridge from '../../components/visualizations/ConceptBridge'
import AtlasCoverageChart from '../../components/visualizations/AtlasCoverageChart'
import { buildClusterMemo, buildVisualAnalyticsMemo, downloadMarkdown } from '../../utils/memoExport'

const defaultFilters = {
  pointType: 'chunks',
  colorBy: 'cluster',
  yearMin: '',
  yearMax: '',
  theme: '',
  sourceType: ''
}

const createEmptyReadinessForm = () => ({
  status: 'draft', corpus_release: '', source_scope: '', exclusions: '', embedding_model: '', model_revision_or_checksum: '',
  vector_dimensions: '', runtime_and_license: '', normalisation_chunking_version: '', capacity_retention_plan: '',
  fts_separation_plan: 'FTS remains the evidence-selection method; vectors only support visual exploration.', analytical_question: '', reviewed_by: ''
})

const readinessTextFields = [
  ['corpus_release', 'Corpus release'],
  ['embedding_model', 'Embedding model'],
  ['model_revision_or_checksum', 'Model revision or checksum'],
  ['vector_dimensions', 'Vector dimensions'],
  ['normalisation_chunking_version', 'Normalisation and chunking version'],
  ['reviewed_by', 'Reviewing researcher']
]

const readinessLongFields = [
  ['source_scope', 'Approved source scope and access policy'],
  ['exclusions', 'Exclusions and reasons'],
  ['runtime_and_license', 'Runtime and licensing assessment'],
  ['capacity_retention_plan', 'Capacity, rollback, and retention plan'],
  ['fts_separation_plan', 'FTS separation plan'],
  ['analytical_question', 'First analytical question']
]

const framingCards = [
  {
    title: 'Oral-historical interpretation',
    body: 'Use the projection as a guide for close reading of testimony, interviews, and situated archival voices rather than as a substitute for them.'
  },
  {
    title: 'Archival LLM interrogation',
    body: 'Link visual clusters back to model-assisted evidence tracing so that semantic patterns remain tied to source chunks and PIDs.'
  },
  {
    title: 'Embedding-based visual analytics',
    body: 'Render semantic proximity, clustering, and outlier relations as prompts for scholarly investigation across the DDR corpus.'
  },
  {
    title: 'Corroborative checking layer',
    body: 'Compare spatial proximity with year, source type, and theme filters so that visual findings can be checked rather than merely admired.'
  }
]

const VisualAnalytics = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [filters, setFilters] = useState(defaultFilters)
  const [projection, setProjection] = useState({ points: [], clusters: [], metadata: {}, message: '' })
  const [loading, setLoading] = useState(false)
  const [errorState, setErrorState] = useState('')
  const [selectedPoint, setSelectedPoint] = useState(null)
  const [selectedCluster, setSelectedCluster] = useState(null)
  const [memoPoints, setMemoPoints] = useState([])
  const [refreshToken, setRefreshToken] = useState(0)
  const [copyFeedback, setCopyFeedback] = useState(null)
  const [readiness, setReadiness] = useState({ ready_for_embedding: false, review: null, message: '' })
  const [readinessForm, setReadinessForm] = useState(createEmptyReadinessForm())
  const [savingReadiness, setSavingReadiness] = useState(false)
  const [readinessError, setReadinessError] = useState('')
  const [recordingCoverageGap, setRecordingCoverageGap] = useState(false)

  const highlightedTrace = useMemo(() => ({
    chunkId: searchParams.get('chunkId'),
    pid: searchParams.get('pid'),
    documentId: searchParams.get('documentId')
  }), [searchParams])

  useEffect(() => {
    let isCancelled = false

    const loadProjection = async () => {
      setLoading(true)
      setErrorState('')

      try {
        const payload = await getUmapProjection({
          point_type: filters.pointType,
          color_by: filters.colorBy,
          year_min: filters.yearMin || undefined,
          year_max: filters.yearMax || undefined,
          theme: filters.theme || undefined,
          source_type: filters.sourceType || undefined,
          include_missingness: true
        })

        if (isCancelled) {
          return
        }

        setProjection(payload)
        setSelectedCluster(null)
      } catch (error) {
        if (isCancelled) {
          return
        }

        if (error.status === 404 || error.status === 501) {
          setErrorState('The backend UMAP endpoint is currently unavailable. The next backend job is embedding generation followed by UMAP projection over the locally ingested evidence surface.')
        } else {
          setErrorState(error.message || 'Failed to load visual analytics projection.')
        }
        setProjection({ points: [], clusters: [], metadata: {}, message: '' })
      } finally {
        if (!isCancelled) {
          setLoading(false)
        }
      }
    }

    loadProjection()

    return () => {
      isCancelled = true
    }
  }, [filters, refreshToken])

  useEffect(() => {
    let isCancelled = false
    getEmbeddingReadiness()
      .then((payload) => { if (!isCancelled) setReadiness(payload) })
      .catch((error) => { if (!isCancelled) setReadinessError(error.message || 'Readiness state could not be loaded.') })
    return () => { isCancelled = true }
  }, [])

  useEffect(() => {
    if (!projection.points.length) {
      return
    }

    const match = projection.points.find((point) => (
      (highlightedTrace.chunkId && point.chunkId === highlightedTrace.chunkId) ||
      (highlightedTrace.documentId && point.documentId === highlightedTrace.documentId) ||
      (highlightedTrace.pid && point.pid === highlightedTrace.pid)
    ))

    if (match) {
      setSelectedPoint(match)
    }
  }, [projection.points, highlightedTrace])

  const statusTag = useMemo(() => {
    if (highlightedTrace.chunkId || highlightedTrace.pid || highlightedTrace.documentId) {
      return { label: 'Trace selected', type: 'purple' }
    }
    if (errorState) {
      return { label: 'Endpoint unavailable', type: 'red' }
    }
    if (projection.points.length > 0) {
      return { label: 'UMAP ready', type: 'green' }
    }
    return { label: 'Awaiting embeddings', type: 'gray' }
  }, [projection.points.length, errorState, highlightedTrace])

  const filteredPoints = useMemo(() => {
    if (!selectedCluster) {
      return projection.points
    }

    return projection.points.filter((point) => point.clusterId === selectedCluster.id || point.clusterLabel === selectedCluster.label)
  }, [projection.points, selectedCluster])

  const scope = projection.metadata.evidenceSurfaceScope || {}
  const warnings = projection.metadata.interpretationWarnings || []

  const highlightedNoticeNeeded = useMemo(() => {
    if (!(highlightedTrace.chunkId || highlightedTrace.pid || highlightedTrace.documentId)) {
      return false
    }

    return !projection.points.some((point) => (
      (highlightedTrace.chunkId && point.chunkId === highlightedTrace.chunkId) ||
      (highlightedTrace.documentId && point.documentId === highlightedTrace.documentId) ||
      (highlightedTrace.pid && point.pid === highlightedTrace.pid)
    ))
  }, [highlightedTrace, projection.points])

  const updateFilter = (field, value) => {
    setFilters((current) => ({ ...current, [field]: value }))
  }

  const handleResetView = () => {
    setFilters(defaultFilters)
    setSelectedCluster(null)
    setSelectedPoint(null)
  }

  const handleRecordCoverageGap = async () => {
    setRecordingCoverageGap(true)
    setErrorState('')
    try {
      const event = await createAtlasCoverageMissingness({
        document_id: highlightedTrace.documentId || undefined,
        chunk_id: highlightedTrace.chunkId || undefined,
        pid: highlightedTrace.pid || undefined,
        projection_id: projection.metadata.projectionId || undefined,
      })
      navigate(`/absences?eventId=${encodeURIComponent(event.event_id)}`)
    } catch (error) {
      setErrorState(error.message || 'The Atlas coverage condition could not be recorded.')
    } finally {
      setRecordingCoverageGap(false)
    }
  }

  const updateReadinessField = (field, value) => setReadinessForm((current) => ({ ...current, [field]: value }))

  const handleSaveReadiness = async () => {
    setSavingReadiness(true)
    setReadinessError('')
    try {
      const payload = await createEmbeddingReadinessReview({ ...readinessForm, vector_dimensions: Number(readinessForm.vector_dimensions) })
      setReadiness(payload)
      setReadinessForm(createEmptyReadinessForm())
    } catch (error) {
      setReadinessError(error.message || 'Readiness review could not be saved.')
    } finally {
      setSavingReadiness(false)
    }
  }

  const handleCopyClusterMemo = async () => {
    const memo = selectedCluster
      ? buildClusterMemo({ cluster: selectedCluster, visiblePoints: filteredPoints })
      : ''
    await copyValue(memo, 'Cluster interpretation note')
  }

  const handleExportMemo = () => {
    const memo = buildVisualAnalyticsMemo({
      filters,
      projection: { ...projection, points: filteredPoints },
      selectedPoint,
      selectedCluster
    })
    downloadMarkdown('visual-analytics-memo.md', memo)
  }

  const handleAddToMemo = () => {
    if (!selectedPoint) {
      return
    }

    setMemoPoints((current) => {
      if (current.some((point) => point.id === selectedPoint.id)) {
        return current
      }
      return [...current, selectedPoint]
    })
  }

  const copyValue = async (value, label = 'Value') => {
    setCopyFeedback(null)
    try {
      if (!value) {
        throw new Error('No value is available to copy.')
      }
      if (!navigator?.clipboard?.writeText) {
        throw new Error('Clipboard access is unavailable.')
      }
      await navigator.clipboard.writeText(value)
      setCopyFeedback({ kind: 'success', title: `${label} copied`, subtitle: 'The current atlas state remains unchanged.' })
    } catch (copyError) {
      setCopyFeedback({ kind: 'error', title: `${label} could not be copied`, subtitle: copyError.message || 'The current atlas state remains unchanged.' })
    }
  }

  return (
    <PageGrid className="visual-analytics-page">
      <Column>
        <PageHeader
          title="Semantic atlas"
          description="Use embeddings, UMAP, clusters, proximity, anomaly, and metadata overlays as a visual hypothesis space, not as proof."
          actions={(
            <div className="visual-analytics-page__status-tags">
              <Tag type={statusTag.type}><DataVis_4 size={16} /> {statusTag.label}</Tag>
              {projection.metadata.isDemo && <Tag type="warm-gray">Demo data</Tag>}
            </div>
          )}
        />
      </Column>

      {highlightedNoticeNeeded && (
        <Column>
          <InlineNotification
            lowContrast
            kind="warning"
            title="Trace selected"
            subtitle="No visual point is currently available for this trace. The handoff parameters were received, but the current projection does not contain a matching chunk, document, or PID."
          />
          <Button kind="secondary" size="sm" onClick={handleRecordCoverageGap} disabled={recordingCoverageGap}>
            {recordingCoverageGap ? 'Recording coverage condition...' : 'Record computational coverage condition'}
          </Button>
        </Column>
      )}

      {errorState && (
        <Column>
          <InlineNotification
            lowContrast
            kind="warning"
            title="UMAP endpoint unavailable"
            subtitle={errorState}
          />
        </Column>
      )}

      {copyFeedback && (
        <Column>
          <InlineNotification lowContrast kind={copyFeedback.kind} title={copyFeedback.title} subtitle={copyFeedback.subtitle} />
        </Column>
      )}

      <Column>
        <InlineNotification
          lowContrast
          kind="info"
          title="Analytical output"
          subtitle="This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface."
        />
      </Column>

      <Column>
        <Tile className="visual-analytics-page__controls">
          <PanelHeader
            title="Embedding readiness review"
            description="A review records whether prerequisites are met. Approval does not generate embeddings or start a projection job."
            actions={<Tag type={readiness.ready_for_embedding ? 'green' : 'gray'}>{readiness.review?.status || 'not started'}</Tag>}
          />
          {readinessError && <InlineNotification lowContrast kind="error" title="Readiness review unavailable" subtitle={readinessError} />}
          {readiness.review ? (
            <div className="visual-analytics-page__scope-grid">
              <p><strong>Review:</strong> {readiness.review.review_id}</p>
              <p><strong>Corpus release:</strong> {readiness.review.corpus_release}</p>
              <p><strong>Model:</strong> {readiness.review.embedding_model}</p>
              <p><strong>Revision:</strong> {readiness.review.model_revision_or_checksum}</p>
              <p><strong>Dimensions:</strong> {readiness.review.vector_dimensions}</p>
              <p><strong>Reviewed by:</strong> {readiness.review.reviewed_by || 'Not approved'}</p>
            </div>
          ) : (
            <div className="visual-analytics-page__controls-grid">
              <Select id="readiness-status" labelText="Review decision" value={readinessForm.status} onChange={(event) => updateReadinessField('status', event.target.value)}>
                <SelectItem value="draft" text="draft" />
                <SelectItem value="blocked" text="blocked" />
                <SelectItem value="approved" text="approved" />
              </Select>
              {readinessTextFields.map(([field, label]) => (
                <TextInput key={field} id={`readiness-${field}`} labelText={label} value={readinessForm[field]} onChange={(event) => updateReadinessField(field, field === 'vector_dimensions' ? event.target.value.replace(/[^0-9]/g, '') : event.target.value)} />
              ))}
              {readinessLongFields.map(([field, label]) => (
                <TextArea key={field} id={`readiness-${field}`} labelText={label} rows={3} value={readinessForm[field]} onChange={(event) => updateReadinessField(field, event.target.value)} />
              ))}
            </div>
          )}
          {!readiness.review && <div className="visual-analytics-page__controls-actions"><Button size="sm" onClick={handleSaveReadiness} disabled={savingReadiness}>Save readiness review</Button></div>}
        </Tile>
      </Column>

      <Column>
        <InlineNotification
          lowContrast
          kind="warning"
          title="Clusters are hypotheses, not findings"
          subtitle={scope.scopeNote || 'This projection represents only the current locally ingested / embedded evidence surface, not the whole DDR archive, and should be checked against source records.'}
        />
      </Column>

      {!loading && !errorState && projection.points.length === 0 && (
        <Column>
          <InlineNotification
            lowContrast
            kind="info"
            title="Atlas not yet generated"
            subtitle="No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."
          />
        </Column>
      )}

      {framingCards.map((card) => (
        <Column key={card.title} lg={5} xlg={5} max={5} md={4} sm={4}>
          <Tile className="visual-analytics-page__framing-card">
            <h3>{card.title}</h3>
            <p>{card.body}</p>
          </Tile>
        </Column>
      ))}

      <Column>
        <Tile className="visual-analytics-page__controls">
          <div className="visual-analytics-page__controls-grid">
            <Select id="point-type" labelText="Point type" value={filters.pointType} onChange={(event) => updateFilter('pointType', event.target.value)}>
              <SelectItem value="chunks" text="Chunks" />
              <SelectItem value="documents" text="Documents" />
            </Select>
            <Select id="color-by" labelText="Colour by" value={filters.colorBy} onChange={(event) => updateFilter('colorBy', event.target.value)}>
              <SelectItem value="cluster" text="Cluster" />
              <SelectItem value="year" text="Year" />
              <SelectItem value="source_type" text="Source type" />
              <SelectItem value="theme" text="Theme" />
              <SelectItem value="confidence" text="Confidence" />
              <SelectItem value="drift_score" text="Drift score" />
            </Select>
            <TextInput id="year-min" labelText="Year min" value={filters.yearMin} onChange={(event) => updateFilter('yearMin', event.target.value.replace(/[^0-9]/g, ''))} />
            <TextInput id="year-max" labelText="Year max" value={filters.yearMax} onChange={(event) => updateFilter('yearMax', event.target.value.replace(/[^0-9]/g, ''))} />
            <TextInput id="theme-filter" labelText="Theme filter" value={filters.theme} onChange={(event) => updateFilter('theme', event.target.value)} />
            <TextInput id="source-type-filter" labelText="Source type filter" value={filters.sourceType} onChange={(event) => updateFilter('sourceType', event.target.value)} />
          </div>
          <div className="visual-analytics-page__controls-actions">
            <Button kind="secondary" onClick={() => setRefreshToken((current) => current + 1)}>Refresh</Button>
            <Button kind="ghost" onClick={handleResetView}>Reset view</Button>
            <Button kind="ghost" onClick={handleExportMemo}>Export atlas coordinates / cluster summary</Button>
          </div>
        </Tile>
      </Column>

      <Column>
        <Tile className="visual-analytics-page__scope-panel">
          <PanelHeader
            title="Metadata overlays and evidence surface scope"
            description="UMAP is presented here as a diagnostic projection of the currently ingested, text-extracted, embedded evidence surface."
            actions={(
              <div className="visual-analytics-page__panel-meta">
                <Tag type="blue">Method: {projection.metadata.projectionMethod || 'none'}</Tag>
                <Tag type="gray">Historical model PDFs: {scope.ingestedGranitePdfs ?? 0}</Tag>
              </div>
            )}
          />
          <div className="visual-analytics-page__scope-grid">
            <p><strong>Returned points:</strong> {scope.returnedPoints ?? projection.points.length}</p>
            <p><strong>Total candidates:</strong> {scope.totalCandidates ?? 0}</p>
            <p><strong>Embedded chunks:</strong> {scope.embeddedChunks ?? 0}</p>
            <p><strong>Documents with embeddings:</strong> {scope.documentsWithEmbeddings ?? 0}</p>
            <p><strong>Documents with extracted text:</strong> {scope.documentsWithExtractedText ?? 0}</p>
            <p><strong>Total documents in DB:</strong> {scope.totalDocumentsInDb ?? 0}</p>
            <p><strong>Scoped missingness v0.2 records:</strong> {scope.archiveWideRecordsFromScopedMissingnessV02 ?? 0}</p>
            <p><strong>Records with PDFs:</strong> {scope.recordsWithPdfs ?? 0}</p>
            <p><strong>Image-only records:</strong> {scope.imageOnlyRecords ?? 0}</p>
            <p><strong>No-asset records:</strong> {scope.noAssetRecords ?? 0}</p>
            <p><strong>Unknown until Docling:</strong> {scope.unknownUntilDoclingRecords ?? 0}</p>
            <p><strong>Distinct PIDs represented:</strong> {scope.distinctPidsRepresented ?? 0}</p>
          </div>
          {warnings.length > 0 && (
            <div className="visual-analytics-page__warning-list">
              {warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}
        </Tile>
      </Column>

      <Column lg={5} md={8} sm={4}>
        <Tile className="visual-analytics-page__coverage-panel">
          <PanelHeader
            title="Evidence surface coverage"
            description="These counts describe local technical representation. They do not measure archival completeness or historical absence."
          />
          <AtlasCoverageChart scope={scope} visiblePointCount={filteredPoints.length} />
        </Tile>
      </Column>

      <Column lg={8} md={8} sm={4}>
        <Tile className="visual-analytics-page__projection-panel">
          <PanelHeader
            title="UMAP projection"
            description="Spatial proximity is a prompt for archival investigation, not proof of relation."
            actions={(
              <div className="visual-analytics-page__panel-meta">
                <Tag type="gray">Visible points: {filteredPoints.length}</Tag>
                <Tag type="warm-gray">Not a complete archive map</Tag>
              </div>
            )}
          />
          <UmapProjection
            points={filteredPoints}
            loading={loading}
            errorState={errorState}
            selectedPoint={selectedPoint}
            highlightedTrace={highlightedTrace}
            colorBy={filters.colorBy}
            onSelectPoint={setSelectedPoint}
          />
        </Tile>
      </Column>

      <Column lg={6} md={8} sm={4}>
        <UmapPointDetail
          point={selectedPoint}
          onOpenCorpus={() => navigate(`/sources?${new URLSearchParams(selectedPoint?.documentId ? { documentId: selectedPoint.documentId } : selectedPoint?.pid ? { pid: selectedPoint.pid } : {}).toString()}`)}
          onTraceEvidence={() => navigate(`/source-interrogation?${new URLSearchParams(selectedPoint?.chunkId ? { chunkId: selectedPoint.chunkId } : selectedPoint?.pid ? { pid: selectedPoint.pid } : {}).toString()}`)}
          onOpenAbsences={() => navigate(`/absences?${new URLSearchParams({
            ...(selectedPoint?.documentId ? { sourceDocumentId: selectedPoint.documentId } : {}),
            ...(selectedPoint?.chunkId ? { sourceChunkId: selectedPoint.chunkId } : {}),
            ...(selectedPoint?.pid ? { pid: selectedPoint.pid } : {})
          }).toString()}`)}
          onOpenCrossReadings={() => navigate(`/cross-readings?${new URLSearchParams({
            ...(selectedPoint?.documentId ? { sourceDocumentId: selectedPoint.documentId } : {}),
            ...(selectedPoint?.chunkId ? { sourceChunkId: selectedPoint.chunkId } : {}),
            ...(selectedPoint?.pid ? { pid: selectedPoint.pid } : {})
          }).toString()}`)}
          onCopyPid={() => copyValue(selectedPoint?.pid)}
          onCopyExcerpt={() => copyValue(selectedPoint?.excerpt)}
          onAddToMemo={handleAddToMemo}
        />
      </Column>

      <Column>
        <Tile className="visual-analytics-page__projection-panel">
          <PanelHeader title="Visible archival evidence" description="Sort the current evidence surface and select a row to inspect its archival source." />
          <UmapEvidenceTable points={filteredPoints} onInspect={setSelectedPoint} />
        </Tile>
      </Column>

      <Column lg={5} md={8} sm={4}>
        <ClusterPanel
          clusters={projection.clusters}
          selectedCluster={selectedCluster}
          onSelectCluster={setSelectedCluster}
          onCopyClusterMemo={handleCopyClusterMemo}
        />
      </Column>

      <Column lg={9} md={8} sm={4}>
        <Tile>
          <PanelHeader title="Cluster interpretation notes" description="Treat clustered groupings as prompts for close reading, corroboration, and claim formation." />
          <ConceptBridge />
        </Tile>
      </Column>

      {memoPoints.length > 0 && (
        <Column>
          <InlineNotification
            lowContrast
            kind="info"
            title="Memo staging"
            subtitle={`Local memo queue contains ${memoPoints.length} point${memoPoints.length === 1 ? '' : 's'} selected from the current visual reading.`}
          />
        </Column>
      )}
    </PageGrid>
  )
}

export default VisualAnalytics