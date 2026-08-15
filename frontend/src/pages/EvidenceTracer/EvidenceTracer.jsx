import {
  Button,
  InlineLoading,
  InlineNotification,
  Select,
  SelectItem,
  Tag,
  TextArea,
  Tile
} from '@carbon/react'
import { Copy, Download, Search, Checkmark } from '@carbon/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { exportExperimentRunJson, interrogateTurin } from '../../api/experiments'
import EvidenceChain from '../../components/evidence/EvidenceChain'
import EvidenceStatusControl from '../../components/evidence/EvidenceStatusControl'
import PanelHeader from '../../components/layout/PanelHeader'
import PageHeader from '../../components/layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import EvidenceGraph from '../../components/visualizations/EvidenceGraph'
import { buildEvidenceTraceMemo, downloadMarkdown } from '../../utils/memoExport'
import { downloadJson } from '../../utils/workbenchExport'

const defaultStatus = 'Needs review'

const EvidenceTracer = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('granite')
  const [traceData, setTraceData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [persistenceError, setPersistenceError] = useState('')
  const [validationStatuses, setValidationStatuses] = useState({ overall: defaultStatus })

  useEffect(() => {
    const seededQuery = searchParams.get('query') || searchParams.get('pid') || searchParams.get('chunkId') || ''
    if (seededQuery && !query) {
      setQuery(seededQuery)
    }
  }, [query, searchParams])

  const handleTrace = async () => {
    if (!query.trim() || loading || mode !== 'granite') {
      return
    }

    setLoading(true)
    setError('')
    setPersistenceError('')

    try {
      const analysis = await interrogateTurin(query, { top_k: 5 })
      const enrichedSources = (analysis.retrieved_evidence || []).map((source) => ({
        chunkId: source.chunk_id,
        documentId: source.document_id,
        pid: source.pid,
        title: source.snapshot?.title || source.snapshot?.catalogue_metadata?.title || source.document_id,
        page: source.page_start,
        section: source.snapshot?.source_section || null,
        excerpt: source.excerpt,
        score: source.score,
        citation: `${source.snapshot?.title || source.document_id} | PID: ${source.pid || 'unavailable'} | Page: ${source.page_start || 'unavailable'}`,
        citationStatus: source.archive_resolution_status === 'resolved_current' ? 'loaded' : 'unavailable',
        provenance: source.snapshot?.provenance || null,
        provenanceStatus: source.archive_resolution_status === 'resolved_current' ? 'loaded' : 'unavailable'
      }))

      const nextTrace = {
        queryId: analysis.run_id,
        prompt: query,
        answer: analysis.answer || '',
        response: analysis.answer || '',
        model: analysis.model?.name || 'Granite experiment',
        retrievedChunkIds: enrichedSources.map((source) => source.chunkId).filter(Boolean),
        citations: enrichedSources.map((source) => source.citation).filter(Boolean),
        pageRanges: enrichedSources.map((source) => source.page).filter(Boolean),
        sourceMetadata: enrichedSources.map((source) => ({
          chunkId: source.chunkId,
          documentId: source.documentId,
          pid: source.pid,
          title: source.title,
          page: source.page,
          section: source.section,
          score: source.score
        })),
        timestamp: analysis.created_at || new Date().toISOString(),
        failed_or_partial: analysis.status !== 'completed' || analysis.interpretative_status !== 'unassessed',
        caveats: analysis.missingness?.map((item) => item.explanation) || [],
        sources: enrichedSources,
        inferenceProvenance: analysis.provenance_validation,
        authorityEvidence: analysis.authority_evidence || [],
        documentaryEvidence: analysis.documentary_evidence || [],
        inferences: analysis.inferences || [],
        contradictions: analysis.contradictions || [],
        missingness: analysis.missingness || [],
        followUpQueries: analysis.follow_up_queries || [],
        runStatus: analysis.status,
        interpretativeStatus: analysis.interpretative_status,
        rawModelResponse: analysis.raw_model_response
      }

      setTraceData({
        ...nextTrace,
        persisted: true,
        retrievedChunkCount: nextTrace.retrievedChunkIds.length,
        failureReason: analysis.error_message || null
      })

      setValidationStatuses({
        overall: defaultStatus,
        ...Object.fromEntries(enrichedSources.map((source, index) => [source.chunkId || `source-${index}`, defaultStatus]))
      })
    } catch (traceError) {
      const failedTrace = {
        query,
        answer: '',
        model: 'Granite retrieval, stable',
        modelVersion: 'Unavailable',
        inferenceId: null,
        queryId: `query-${Date.now()}`,
        prompt: query,
        response: '',
        retrievedChunkIds: [],
        citations: [],
        pageRanges: [],
        sourceMetadata: [],
        timestamp: new Date().toISOString(),
        failed_or_partial: true,
        failureReason: traceError.message || 'Evidence trace failed.',
        caveats: [traceError.message || 'Evidence trace failed.'],
        sources: [],
        inferenceProvenance: null
      }

      setError(traceError.message || 'Evidence trace failed.')
      setTraceData(failedTrace)
      setValidationStatuses({ overall: defaultStatus })
    } finally {
      setLoading(false)
    }
  }

  const provenanceStatus = useMemo(() => {
    if (!traceData) {
      return { label: 'Retrieval ready', type: 'blue' }
    }

    const loaded = traceData.sources.filter((source) => source.provenanceStatus === 'loaded').length
    if (loaded === traceData.sources.length && loaded > 0) {
      return { label: 'Provenance enabled', type: 'green' }
    }

    if (loaded > 0 || traceData.sources.some((source) => source.citationStatus === 'loaded')) {
      return { label: 'Partial provenance', type: 'blue' }
    }

    return { label: 'Retrieval only', type: 'gray' }
  }, [traceData])

  const updateValidationStatus = (key, value) => {
    setValidationStatuses((current) => ({
      ...current,
      [key]: value
    }))
  }

  const handleToggleProvenance = (source) => {
    setTraceData((current) => {
      if (!current) {
        return current
      }

      return {
        ...current,
        sources: current.sources.map((item) => {
          const key = item.chunkId || item.documentId || item.pid
          const sourceKey = source.chunkId || source.documentId || source.pid
          return key === sourceKey
            ? { ...item, provenanceExpanded: !item.provenanceExpanded }
            : item
        })
      }
    })
  }

  const handleCopyCitation = async (source) => {
    const citationText = typeof source.citation === 'string'
      ? source.citation
      : source.citation
        ? [source.citation.title, source.citation.pid ? `PID: ${source.citation.pid}` : null, source.citation.page ? `Page: ${source.citation.page}` : null, source.citation.publicUrl || null].filter(Boolean).join(' | ')
        : 'Not available from current endpoint.'

    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(citationText)
    }
  }

  const handleCopyMemo = async () => {
    if (!traceData) {
      return
    }

    const memo = buildEvidenceTraceMemo({ trace: traceData, validationStatuses })
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(memo)
    }
  }

  const handleDownloadMemo = () => {
    if (!traceData) {
      return
    }

    const memo = buildEvidenceTraceMemo({ trace: traceData, validationStatuses })
    const slug = (traceData.query || 'evidence-trace').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'evidence-trace'
    downloadMarkdown(`${slug}.md`, memo)
  }

  const goToCorpus = (source) => {
    const params = new URLSearchParams()
    if (source.documentId) params.set('documentId', source.documentId)
    if (source.pid) params.set('pid', source.pid)
    navigate(`/sources?${params.toString()}`)
  }

  const goToAnalytics = (source) => {
    const params = new URLSearchParams()
    if (source.chunkId) params.set('chunkId', source.chunkId)
    if (source.pid) params.set('pid', source.pid)
    navigate(`/semantic-atlas?${params.toString()}`)
  }

  const exportRetrievalTrail = async () => {
    if (!traceData) {
      return
    }

    if (traceData.persisted && traceData.queryId) {
      try {
        const payload = await exportExperimentRunJson(traceData.queryId)
        downloadJson(`${traceData.queryId}.json`, payload)
        return
      } catch (exportError) {
        setPersistenceError(exportError.message || 'Failed to export the persisted retrieval trail.')
      }
    }

    downloadJson('ask-retrieval-trail.json', {
      query_id: traceData.queryId,
      prompt: traceData.prompt,
      response: traceData.response,
      model: traceData.model,
      retrieved_chunk_ids: traceData.retrievedChunkIds,
      citations: traceData.citations,
      page_ranges: traceData.pageRanges,
      source_metadata: traceData.sourceMetadata,
      timestamp: traceData.timestamp,
      failed_or_partial: traceData.failed_or_partial,
      caveats: traceData.caveats
    })
  }

  const showNoSourcesReturned = Boolean(
    traceData &&
    !loading &&
    (traceData.retrievedChunkCount ?? traceData.sources?.length ?? 0) === 0
  )

  return (
    <PageGrid className="evidence-tracer">
      <Column>
        <PageHeader
          title="Source interrogation"
          description="Ask research questions against retrieved archival chunks, then inspect the source stack, caveats, and provenance trail."
          actions={(
            <Tag type={provenanceStatus.type} size="md">
              <Checkmark size={16} /> {provenanceStatus.label}
            </Tag>
          )}
        />
      </Column>

      <Column>
        <Tile className="tracer__panel tracer__panel--query">
          <PanelHeader
            title="Research query"
            description="Use the stable Granite retrieval path first. This view preserves the working local Granite route and treats provenance as mandatory, not optional."
          />

          <div className="tracer__query-grid">
            <TextArea
              id="query-input"
              labelText="Research query"
              rows={4}
              placeholder="Ask a research question about DDR traces, themes, testimony, projects, or design knowledge..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />

            <Select id="trace-mode" labelText="Mode / model selector" value={mode} onChange={(e) => setMode(e.target.value)}>
              <SelectItem value="granite" text="Granite retrieval, stable" />
              <SelectItem value="agent" text="Agent trace, unavailable" disabled />
            </Select>
          </div>

          <div className="tracer__query-actions">
            <Button renderIcon={Search} onClick={handleTrace} disabled={!query.trim() || loading || mode !== 'granite'}>
              Run interrogation
            </Button>
            {loading && <InlineLoading description="Tracing retrieval, provenance, and evidence chain..." status="active" />}
          </div>
        </Tile>
      </Column>

      <Column>
        <InlineNotification
          lowContrast
          kind="info"
          title="Analytical output"
          subtitle="This view produces a retrieval trail / source stack. Generated answers are provisional until checked against retrieved source chunks and their provenance fields."
        />
      </Column>

      {!traceData && !loading && !error && (
        <Column>
          <InlineNotification
            lowContrast
            kind="info"
            title="Before interrogation"
            subtitle="Source interrogation turns a research question into a source-backed chain: prompt, model response, retrieved chunks, page ranges, source metadata, and DDR provenance where available."
          />
        </Column>
      )}

      {error && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Interrogation failed" subtitle={error} />
        </Column>
      )}

      {persistenceError && (
        <Column>
          <InlineNotification lowContrast kind="warning" title="Persistence unavailable" subtitle={persistenceError} />
        </Column>
      )}

      {traceData?.failed_or_partial && (
        <Column>
          <InlineNotification
            lowContrast
            kind="warning"
            title="Retrieval / provenance issue"
            subtitle={(traceData.caveats || []).join(' ') || 'The current interrogation completed with partial provenance or incomplete source coverage.'}
          />
        </Column>
      )}

      <Column>
        <Tile className="tracer__panel">
          <PanelHeader
            title="Answer"
            description="Granite-assisted response with explicit source-backing, caveats, and export controls. Generated answers remain provisional until checked against retrieved source chunks."
            actions={traceData && (
              <div className="tracer__answer-tags">
                <Tag type="blue">{traceData.model || 'Model unavailable'}</Tag>
                <Tag type="gray">{traceData.sources.length > 0 ? 'Source-backed' : 'No sources returned'}</Tag>
                {traceData.confidence !== null && <Tag type="teal">Confidence {traceData.confidence}</Tag>}
                {traceData.queryId && <Tag type="purple">{traceData.queryId}</Tag>}
              </div>
            )}
          />

          <div className="tracer__answer-body">
            {traceData ? (traceData.answer || 'No answer returned.') : 'No answer returned yet. Submit a query to begin evidence tracing.'}
          </div>

          {traceData && (
            <div className="tracer__structured-response">
              <section aria-label="Database authority context">
                <h4>Database authority context</h4>
                {traceData.authorityEvidence?.length > 0
                  ? traceData.authorityEvidence.map((item) => (
                    <p key={item.authority_id}>
                      {item.authority_type === 'ddr_projects'
                        ? `Job ${item.job_number} | ${item.title} | Funder: ${item.funder_name || 'unavailable'} | Duration: ${item.duration_text || 'unavailable'} | Project lead: ${item.project_lead_name || 'unavailable'}`
                        : item.authority_type !== 'agent_employment'
                          ? `${item.label} | ${item.authority_type} | ${item.authority_classification || 'database authority record'}${item.description ? ` | ${item.description}` : ''}`
                        : `${item.assertion} | ${item.role || 'Role unavailable'} | ${item.tenure?.start_date || 'start unavailable'} to ${item.tenure?.end_date || 'end unavailable'}`}
                    </p>
                  ))
                  : <p>No database authority assertion was used for this run.</p>}
              </section>
              <section aria-label="Documentary evidence">
                <h4>Documentary evidence</h4>
                {traceData.documentaryEvidence?.length > 0
                  ? traceData.documentaryEvidence.map((item) => <p key={item.chunk_id}>{item.claim} [PID {item.pid}, page {item.page ?? 'unavailable'}]</p>)
                  : <p>No documentary claim is asserted beyond the retrieved source stack.</p>}
              </section>
              <section aria-label="Generated inference">
                <h4>Generated inference</h4>
                {traceData.inferences?.length > 0
                  ? traceData.inferences.map((item, index) => <p key={`${item.inference}-${index}`}>{item.inference} ({item.confidence})</p>)
                  : <p>No generated inference is asserted.</p>}
              </section>
              <section aria-label="Scoped missingness">
                <h4>Scoped missingness</h4>
                {traceData.missingness?.length > 0
                  ? traceData.missingness.map((item, index) => <p key={`${item.category}-${index}`}>{item.explanation}</p>)
                  : <p>No scoped missingness was recorded.</p>}
              </section>
              <section aria-label="Provenance validation">
                <h4>Provenance validation</h4>
                <p>{traceData.inferenceProvenance?.valid ? 'Valid for supplied citations.' : 'Requires researcher review.'} Run status: {traceData.runStatus || 'unavailable'}; interpretative status: {traceData.interpretativeStatus || 'unassessed'}.</p>
              </section>
            </div>
          )}

          {traceData && (
            <div className="tracer__answer-controls">
              <EvidenceStatusControl
                id="overall-evidence-status"
                label="Overall claim status"
                value={validationStatuses.overall || defaultStatus}
                onChange={(value) => updateValidationStatus('overall', value)}
              />
              <Button kind="ghost" size="sm" renderIcon={Copy} onClick={handleCopyMemo}>Copy retrieval memo</Button>
              <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleDownloadMemo}>Download retrieval memo</Button>
              <Button kind="ghost" size="sm" renderIcon={Download} onClick={exportRetrievalTrail}>Export retrieval trail</Button>
            </div>
          )}
        </Tile>
      </Column>

      <Column>
        <Tile className="tracer__panel">
          <PanelHeader
            title="Retrieved source stack and evidence chain"
            description="Query → Granite model → retrieved chunks → documents → PIDs → DDR archive."
          />
          <EvidenceChain
            sources={traceData?.sources || []}
            showEmptyState={showNoSourcesReturned}
            validationStatuses={validationStatuses}
            onValidationChange={(source, value) => updateValidationStatus(source.chunkId || source.documentId || source.pid, value)}
            onCopyCitation={handleCopyCitation}
            onOpenCorpus={goToCorpus}
            onShowAnalytics={goToAnalytics}
            onToggleProvenance={handleToggleProvenance}
          />
        </Tile>
      </Column>

      <Column>
        <Tile className="tracer__visualization">
          <PanelHeader
            title="Retrieval trail"
            description="Visual cue for how the current answer traversed the local evidence surface."
          />
          <EvidenceGraph data={traceData} />
        </Tile>
      </Column>
    </PageGrid>
  )
}

export default EvidenceTracer
