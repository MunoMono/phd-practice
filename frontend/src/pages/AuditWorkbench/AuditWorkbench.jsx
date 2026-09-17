import { Button, InlineNotification, Select, SelectItem, Tag, Tile } from '@carbon/react'
import { Catalog, Download } from '@carbon/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { getAuthoritySummary } from '../../api/authorities'
import PageHeader from '../../components/layout/PageHeader'
import PanelHeader from '../../components/layout/PanelHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import apiRequest from '../../api/client'
import { exportClaimsCsv, exportClaimsMarkdown, getClaims } from '../../api/claims'
import { exportCrossReadCsv, exportCrossReadMarkdown, getCrossReadMap } from '../../api/crossRead'
import { getRuntimeLoadStatus } from '../../api/runtime'
import { getMissingnessEvents, getMissingnessSummary } from '../../api/missingness'
import { exportQueryRunJson, exportQueryRunMarkdown, getQueryRun, getQueryRuns } from '../../api/queryRuns'
import { getResearchStateTag } from '../../utils/researchState'
import { downloadFile } from '../../utils/workbenchExport'

const AuditWorkbench = () => {
  const [backendHealth, setBackendHealth] = useState(null)
  const [runtimeStatus, setRuntimeStatus] = useState(null)
  const [queryRuns, setQueryRuns] = useState([])
  const [selectedQueryId, setSelectedQueryId] = useState('')
  const [selectedQueryRun, setSelectedQueryRun] = useState(null)
  const [missingnessEvents, setMissingnessEvents] = useState([])
  const [missingnessSummary, setMissingnessSummary] = useState(null)
  const [crossReadMap, setCrossReadMap] = useState([])
  const [claims, setClaims] = useState([])
  const [authoritySummary, setAuthoritySummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let isCancelled = false

    const loadWorkbench = async () => {
      setLoading(true)
      setError('')

      try {
        const [healthPayload, runtimePayload, queryRunPayload, missingnessPayload, missingnessSummaryPayload, crossReadPayload, claimsPayload, authorityPayload] = await Promise.all([
          apiRequest('/health'),
          getRuntimeLoadStatus(),
          getQueryRuns(),
          getMissingnessEvents(),
          getMissingnessSummary(),
          getCrossReadMap(),
          getClaims(),
          getAuthoritySummary().catch(() => null),
        ])

        if (isCancelled) {
          return
        }

        const nextQueryRuns = queryRunPayload.query_runs || []
        const nextSelectedQueryId = nextQueryRuns[0]?.query_id || ''

        setBackendHealth(healthPayload)
        setRuntimeStatus(runtimePayload)
        setQueryRuns(nextQueryRuns)
        setSelectedQueryId(nextSelectedQueryId)
        setMissingnessEvents(missingnessPayload.events || [])
        setMissingnessSummary(missingnessSummaryPayload)
        setCrossReadMap(crossReadPayload.passages || [])
        setClaims(claimsPayload.claims || [])
        setAuthoritySummary(authorityPayload)
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError.message || 'Failed to load live provenance traces.')
        }
      } finally {
        if (!isCancelled) {
          setLoading(false)
        }
      }
    }

    loadWorkbench()

    return () => {
      isCancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedQueryId) {
      setSelectedQueryRun(null)
      return
    }

    let isCancelled = false

    const loadSelectedQueryRun = async () => {
      try {
        const payload = await getQueryRun(selectedQueryId)
        if (!isCancelled) {
          setSelectedQueryRun(payload)
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError.message || 'Failed to load the selected query run.')
          setSelectedQueryRun(null)
        }
      }
    }

    loadSelectedQueryRun()

    return () => {
      isCancelled = true
    }
  }, [selectedQueryId])

  const apparatusCards = useMemo(() => {
    const backendHealthAvailable = Boolean(backendHealth && typeof backendHealth === 'object' && !Array.isArray(backendHealth) && backendHealth.status)
    const evidenceLinkedClaims = claims.filter((claim) => (claim.evidence_count || 0) > 0).length
    const crossReadMappingCount = crossReadMap.reduce((total, passage) => total + (passage.mapping_count || passage.mappings?.length || 0), 0)

    return [
      {
        label: 'Backend health',
        value: loading ? 'Loading...' : backendHealthAvailable ? backendHealth.status : 'Unavailable',
        note: loading ? 'Checking deployment health surface' : backendHealthAvailable ? 'Live /health status' : 'Health endpoint is not exposed through the current deployment.',
      },
      {
        label: 'Runtime readiness',
        value: loading ? 'Loading...' : runtimeStatus?.model_status || 'Unavailable',
        note: loading ? 'Checking model state' : runtimeStatus?.model_ready ? 'Qwen3 8B ready' : 'Qwen3 8B unavailable',
      },
      {
        label: 'Semantic reranker',
        value: 'BAAI/bge-small-en-v1.5',
        note: '384-dimensional local Mac embeddings; cosine reranks provenance-valid documentary passages only, with no whole-corpus vector index.',
      },
      {
        label: 'Relevance reranker',
        value: 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        note: 'Local Mac joint question-passage scoring over provenance-valid documentary candidates; it does not generate historical claims.',
      },
      {
        label: 'Query runs',
        value: loading ? 'Loading...' : String(queryRuns.length),
        note: 'Recent source interrogations',
      },
      {
        label: 'Missingness events',
        value: loading ? 'Loading...' : String(missingnessEvents.length),
        note: 'Absences / retrieval-missingness trace',
      },
      {
        label: 'Cross-read traces',
        value: loading ? 'Loading...' : `${crossReadMap.length} passages / ${crossReadMappingCount} mappings`,
        note: 'Testimony-record mapping surface',
      },
      {
        label: 'Claims',
        value: loading ? 'Loading...' : `${claims.length} total / ${evidenceLinkedClaims} evidence-linked`,
        note: 'Claim-evidence apparatus outputs',
      },
      {
        label: 'Authority register',
        value: loading ? 'Loading...' : authoritySummary ? 'Available' : 'Unavailable',
        note: loading ? 'Checking authority register state' : authoritySummary ? `${authoritySummary.totalRecords} records / ${authoritySummary.count} types` : 'Authority register not available.',
      },
    ]
  }, [authoritySummary, backendHealth, claims, crossReadMap, runtimeStatus, loading, missingnessEvents.length, queryRuns.length])

  const selectedQueryRunExportsEnabled = Boolean(selectedQueryId)

  const handleExportSelectedQueryRunJson = async () => {
    if (!selectedQueryId) {
      return
    }

    try {
      const content = await exportQueryRunJson(selectedQueryId)
      downloadFile(`${selectedQueryId}.json`, content, 'application/json;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export retrieval trail JSON.')
    }
  }

  const handleExportSelectedQueryRunMarkdown = async () => {
    if (!selectedQueryId) {
      return
    }

    try {
      const content = await exportQueryRunMarkdown(selectedQueryId)
      downloadFile(`${selectedQueryId}.md`, content, 'text/markdown;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export retrieval trail Markdown.')
    }
  }

  const handleExportCrossReadCsv = async () => {
    try {
      const content = await exportCrossReadCsv()
      downloadFile('testimony-record-map.csv', content, 'text/csv;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export testimony-record map CSV.')
    }
  }

  const handleExportCrossReadMarkdown = async () => {
    try {
      const content = await exportCrossReadMarkdown()
      downloadFile('testimony-record-map.md', content, 'text/markdown;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export testimony-record map Markdown.')
    }
  }

  const handleExportClaimsCsv = async () => {
    try {
      const content = await exportClaimsCsv()
      downloadFile('claim-evidence-matrix.csv', content, 'text/csv;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export claim-evidence CSV.')
    }
  }

  const handleExportClaimsMarkdown = async () => {
    try {
      const content = await exportClaimsMarkdown()
      downloadFile('claim-evidence-matrix.md', content, 'text/markdown;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export claim-evidence Markdown.')
    }
  }

  const relationSummary = (passage) => {
    const mappings = passage.mappings || []
    if (mappings.length === 0) {
      return 'No mappings yet.'
    }

    const counts = mappings.reduce((accumulator, mapping) => {
      const key = mapping.relation_type || 'unclassified'
      accumulator[key] = (accumulator[key] || 0) + 1
      return accumulator
    }, {})

    return Object.entries(counts).map(([key, count]) => `${key}: ${count}`).join(' | ')
  }

  return (
    <PageGrid className="audit-workbench">
      <Column>
        <PageHeader
          title="Provenance"
          description="Consolidate retrieval trails, absences, testimony-record mappings, claim-evidence matrices, model readiness, and export surfaces into a reproducibility layer."
          actions={(
            <Tag type="teal" size="md">
              <Catalog size={16} /> Provenance and export layer
            </Tag>
          )}
        />
      </Column>

      <Column>
        <Tile>
          <PanelHeader title="Analytical output" description="Provenance consolidates live apparatus traces. It does not create findings; it gathers logs, exports, and evidence trails for review." />
        </Tile>
      </Column>

      {error && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Live provenance unavailable" subtitle={error} />
        </Column>
      )}

      <Column>
        <Tile>
          <PanelHeader title="Apparatus status" description="Live counts and readiness signals from the working apparatus." />
          <div className="app-card-grid app-card-grid--dense app-card-grid--responsive">
            {apparatusCards.map((card) => (
              <div key={card.label} className="app-stat-card audit-workbench__status-card">
                <strong className="app-stat-card__title">{card.label}</strong>
                <p className="app-stat-card__value">{card.value}</p>
                <p className="app-stat-card__note">{card.note}</p>
              </div>
            ))}
          </div>
        </Tile>
      </Column>

      {authoritySummary && (
        <Column>
          <Tile>
            <PanelHeader title="Authority register" description="Structured archive authorities are available to the research system as apparatus context, not as source-document evidence." />
            <div className="app-tag-row audit-workbench__tag-row">
              <Tag type="teal">{authoritySummary.totalRecords} authority records</Tag>
              <Tag type="blue">{authoritySummary.count} authority types</Tag>
              <Tag type="gray">{authoritySummary.coreRecords} core</Tag>
              <Tag type="purple">{authoritySummary.criticalRecords} critical</Tag>
            </div>
            <p className="app-copy-tight">Authorities support future entity resolution, filtering and controlled query expansion. They are not source-document evidence.</p>
            <div className="app-card-grid app-card-grid--dense app-card-grid--responsive audit-workbench__authority-grid">
              {authoritySummary.authorityTypes.map((item) => (
                <div key={item.authority_type} className="app-stat-card audit-workbench__status-card">
                  <strong className="app-stat-card__title">{item.authority_type.replaceAll('_', ' ')}</strong>
                  <p className="app-stat-card__value">{item.count}</p>
                  <p className="app-stat-card__note">{item.category} · {item.allowed_roles.join(', ').replaceAll('_', ' ')}</p>
                </div>
              ))}
            </div>
          </Tile>
        </Column>
      )}

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader title="Recent source interrogations" description="Recent query runs with persisted retrieval-trail exports." />
          {loading ? (
            <InlineNotification lowContrast kind="info" title="Loading query runs" subtitle="Fetching persisted source interrogations and retrieval-trail exports." />
          ) : queryRuns.length === 0 ? (
            <InlineNotification lowContrast kind="info" title="No query runs yet" subtitle="Run a source interrogation to surface persisted retrieval trails here." />
          ) : (
            <div className="app-card-grid app-card-grid--dense">
              {queryRuns.map((run) => (
                <div key={run.query_id} className="app-list-item">
                  <strong className="app-list-item__title">{run.prompt}</strong>
                  {getResearchStateTag(run) ? <Tag type={getResearchStateTag(run).type} size="sm">{getResearchStateTag(run).label}</Tag> : null}
                  <p className="app-list-item__body">Model: {run.model || 'Unavailable'} | Retrieved chunks: {run.retrieved_chunk_count} | Failed/partial: {run.failed_or_partial ? 'yes' : 'no'}</p>
                  <p className="app-list-item__note">{run.created_at || 'Timestamp unavailable'}</p>
                  <div className="app-actions-row">
                    <Button kind="ghost" size="sm" renderIcon={Download} onClick={async () => {
                      const content = await exportQueryRunJson(run.query_id)
                      downloadFile(`${run.query_id}.json`, content, 'application/json;charset=utf-8')
                    }}>Export JSON</Button>
                    <Button kind="ghost" size="sm" renderIcon={Download} onClick={async () => {
                      const content = await exportQueryRunMarkdown(run.query_id)
                      downloadFile(`${run.query_id}.md`, content, 'text/markdown;charset=utf-8')
                    }}>Export Markdown</Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Tile>
      </Column>

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader title="Absences / retrieval-missingness trace" description="Summary list of persisted missingness events tied to the current apparatus." />
          {loading ? (
            <InlineNotification lowContrast kind="info" title="Loading missingness trace" subtitle="Fetching persisted absences and retrieval-gap events." />
          ) : missingnessEvents.length === 0 ? (
            <InlineNotification lowContrast kind="info" title="No missingness events" subtitle="Persisted Absences events will appear here once created from retrieval gaps or review work." />
          ) : (
            <div className="app-card-grid app-card-grid--dense">
              {missingnessEvents.map((event) => (
                <div key={event.event_id} className="app-list-item">
                  <strong className="app-list-item__title">{event.type}</strong>
                  {getResearchStateTag(event) ? <Tag type={getResearchStateTag(event).type} size="sm">{getResearchStateTag(event).label}</Tag> : null}
                  <p className="app-list-item__body">{event.query_or_entity_or_field}</p>
                  <p className="app-list-item__meta">Status: {event.status} | Query run: {event.query_id || 'Unavailable'}</p>
                  <p className="app-list-item__note">{event.reviewer_note || event.evidence}</p>
                </div>
              ))}
            </div>
          )}
        </Tile>
      </Column>

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader
            title="Cross-readings trace"
            description="Summary list of persisted passages and testimony-record mappings."
            actions={(
              <div className="app-actions-row">
                <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportCrossReadCsv}>Export map CSV</Button>
                <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportCrossReadMarkdown}>Export map Markdown</Button>
              </div>
            )}
          />
          {loading ? (
            <InlineNotification lowContrast kind="info" title="Loading cross-read traces" subtitle="Fetching testimony-record mappings and related passage traces." />
          ) : crossReadMap.length === 0 ? (
            <InlineNotification lowContrast kind="info" title="No cross-read traces" subtitle="Persisted testimony-record mappings will appear here after Cross-readings runs." />
          ) : (
            <div className="app-card-grid app-card-grid--dense">
              {crossReadMap.map((passage) => (
                <div key={passage.passage_id} className="app-list-item">
                  <strong className="app-list-item__title">{passage.passage_label || passage.speaker_or_source || passage.passage_id}</strong>
                  {getResearchStateTag(passage) ? <Tag type={getResearchStateTag(passage).type} size="sm">{getResearchStateTag(passage).label}</Tag> : null}
                  <p className="app-list-item__body">Status: {passage.status} | Mapping count: {passage.mapping_count}</p>
                  <p className="app-list-item__note">{relationSummary(passage)}</p>
                </div>
              ))}
            </div>
          )}
        </Tile>
      </Column>

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader
            title="Claims and evidence trace"
            description="Summary list of claim-evidence outputs and export surface." 
            actions={(
              <div className="app-actions-row">
                <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportClaimsCsv}>Export claims CSV</Button>
                <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportClaimsMarkdown}>Export claims Markdown</Button>
              </div>
            )}
          />
          <InlineNotification lowContrast kind="info" title="Export rule" subtitle="Supported claims without evidence are not exported as supported." />
          {loading ? (
            <InlineNotification lowContrast kind="info" title="Loading claim traces" subtitle="Fetching persisted claim-evidence outputs and export state." />
          ) : (
            <div className="app-card-grid app-card-grid--dense audit-workbench__claims-list">
              {claims.map((claim) => (
                <div key={claim.claim_id} className="app-list-item">
                  <strong className="app-list-item__title">{claim.claim_text}</strong>
                  {getResearchStateTag(claim) ? <Tag type={getResearchStateTag(claim).type} size="sm">{getResearchStateTag(claim).label}</Tag> : null}
                  <p className="app-list-item__body">Support: {claim.support_level} | Evidence count: {claim.evidence_count} | Reviewer status: {claim.reviewer_status}</p>
                </div>
              ))}
            </div>
          )}
        </Tile>
      </Column>

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader title="Export surface" description="Reach the existing apparatus exports from one place." />
          <div className="app-card-grid app-card-grid--dense">
            <Select id="selected-query-run" labelText="Selected query run" value={selectedQueryId} onChange={(event) => setSelectedQueryId(event.target.value)}>
              <SelectItem value="" text={loading ? 'Loading query runs...' : queryRuns.length ? 'Choose a query run' : 'No query runs available'} />
              {queryRuns.map((run) => (
                <SelectItem key={run.query_id} value={run.query_id} text={`${run.query_id} · ${run.prompt}`} />
              ))}
            </Select>
            <div className="app-actions-row">
              <Button kind="ghost" size="sm" renderIcon={Download} disabled={!selectedQueryRunExportsEnabled} onClick={handleExportSelectedQueryRunJson}>Selected query-run JSON</Button>
              <Button kind="ghost" size="sm" renderIcon={Download} disabled={!selectedQueryRunExportsEnabled} onClick={handleExportSelectedQueryRunMarkdown}>Selected query-run Markdown</Button>
              <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportCrossReadCsv}>Testimony-record map CSV</Button>
              <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportCrossReadMarkdown}>Testimony-record map Markdown</Button>
              <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportClaimsCsv}>Claim-evidence CSV</Button>
              <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportClaimsMarkdown}>Claim-evidence Markdown</Button>
            </div>
            {selectedQueryRun && (
              <>
                <p className="app-copy-reset app-text-muted">
                  Selected run: {selectedQueryRun.query_id} | Retrieved chunks: {selectedQueryRun.retrieved_chunk_count} | Failed/partial: {selectedQueryRun.failed_or_partial ? 'yes' : 'no'}
                </p>
                <InlineNotification
                  lowContrast
                  kind={selectedQueryRun.provenance_sha256 ? 'info' : 'warning'}
                  title={selectedQueryRun.provenance_sha256 ? 'Integrity binding available' : 'Integrity binding unavailable'}
                  subtitle={selectedQueryRun.provenance_sha256
                    ? `SHA-256 ${selectedQueryRun.provenance_sha256}. ${selectedQueryRun.chunks?.filter((chunk) => chunk.content_sha256).length || 0}/${selectedQueryRun.chunks?.length || 0} retained source chunks are individually bound.`
                    : 'This historical run was stored before SHA-256 provenance bindings were introduced.'}
                />
                <p className="app-text-muted app-copy-tight">
                  A checksum detects changes to the retained record. It is not a digital signature, C2PA manifest, or assessment of a source's authenticity.
                </p>
              </>
            )}
          </div>
        </Tile>
      </Column>

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader title="Reproducibility note" description="Static note for review context." />
          <p className="app-copy-reset">
            This page consolidates provenance traces from the working apparatus. It does not create findings; it gathers logs, exports, and evidence trails for review.
          </p>
          {missingnessSummary?.retrieval_coverage?.label && (
            <p className="app-text-muted app-copy-tight">
              Retrieval coverage: {missingnessSummary.retrieval_coverage.label}
            </p>
          )}
        </Tile>
      </Column>
    </PageGrid>
  )
}

export default AuditWorkbench
