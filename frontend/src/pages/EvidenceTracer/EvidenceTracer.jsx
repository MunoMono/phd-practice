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
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { exportExperimentRunJson, getExperimentRun, interrogateTurin } from '../../api/experiments'
import EvidenceChain from '../../components/evidence/EvidenceChain'
import PanelHeader from '../../components/layout/PanelHeader'
import PageHeader from '../../components/layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import EvidenceGraph from '../../components/visualizations/EvidenceGraph'
import { buildEvidenceTraceMemo, downloadMarkdown } from '../../utils/memoExport'
import { downloadJson } from '../../utils/workbenchExport'

const systemDerivedMissingnessCategories = new Set([
  'zero_retrieval',
  'insufficient_temporally_valid_evidence',
  'no_matching_authority_record',
  'no_matching_job_numbers',
  'no_matching_job_number',
  'insufficient_project_temporal_authority',
  'no_projects_with_explicit_dates_for_year',
  'no_documentary_retrieval_for_resolved_project',
  'no_documentary_retrieval_for_authority',
  'no_temporally_valid_documentary_support'
])

const validationFailureCategories = new Set([
  'parse_failure',
  'provenance_validation_failure'
])

const formatScore = (score) => Number.isFinite(score) ? score.toFixed(3) : null

const getRetrievalMemoFilename = (runId) => {
  const safeRunId = typeof runId === 'string'
    ? runId.replace(/[^A-Za-z0-9._-]/g, '')
    : ''

  return safeRunId
    ? `turin-retrieval-memo-${safeRunId}.md`
    : 'turin-retrieval-memo.md'
}

const getRetrievalTrailFilename = (runId) => {
  const safeRunId = typeof runId === 'string'
    ? runId.replace(/[^A-Za-z0-9._-]/g, '')
    : ''

  return `turin-retrieval-trail-${safeRunId}.json`
}

const mapRetrievedSources = (retrievedEvidence = []) => retrievedEvidence.map((source) => ({
  chunkId: source.chunk_id,
  documentId: source.document_id,
  pid: source.pid,
  archiveRecordPid: source.archive_record_pid,
  rank: source.rank,
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

const mapAuthorityEvidence = (authorityContext = {}) => (authorityContext.contexts || []).map((item) => {
  const fields = item.fields || {}
  if (item.authority_type === 'ddr_projects') {
    return {
      authority_type: item.authority_type,
      authority_id: item.authority_id,
      source: item.source,
      job_number: fields.job_number,
      title: fields.title,
      funder_name: fields.funder_name,
      duration_text: fields.duration_text,
      project_lead_name: fields.project_lead_name,
      start_year: fields.start_year,
      end_year: fields.end_year,
      filter: fields.authority_filter
    }
  }
  if (item.authority_type === 'agent_employment') {
    return {
      authority_type: item.authority_type,
      authority_id: item.authority_id,
      source: item.source,
      assertion: fields.name,
      role: fields.job_title_label,
      tenure: { start_date: fields.start_date, end_date: fields.end_date }
    }
  }
  return {
    authority_type: item.authority_type,
    authority_id: item.authority_id,
    source: item.source,
    label: fields.label,
    code: fields.code,
    description: fields.description,
    epistemic_type: fields.epistemic_type,
    authority_classification: fields.authority_classification
  }
})

const mapPersistedRunToTrace = (run) => {
  const sources = mapRetrievedSources(run.retrieved_evidence)
  const response = run.structured_response || {}

  return {
    queryId: run.run_id,
    prompt: run.prompt?.question || '',
    researchCase: run.research_case || null,
    corpusVersion: run.corpus_version || null,
    retrievalMethod: run.retrieval_method || null,
    retrieval: run.retrieval || null,
    answer: response.answer || '',
    response: response.answer || '',
    model: run.model?.name || 'Granite experiment',
    retrievedChunkIds: sources.map((source) => source.chunkId).filter(Boolean),
    citations: sources.map((source) => source.citation).filter(Boolean),
    pageRanges: sources.map((source) => source.page).filter(Boolean),
    sourceMetadata: sources.map((source) => ({ chunkId: source.chunkId, documentId: source.documentId, pid: source.pid, title: source.title, page: source.page, section: source.section, score: source.score })),
    timestamp: run.created_at || null,
    failed_or_partial: run.status !== 'completed' || run.interpretative_status !== 'unassessed',
    caveats: response.missingness?.map((item) => item.explanation) || [],
    sources,
    inferenceProvenance: run.provenance_validation || null,
    authorityEvidence: mapAuthorityEvidence(run.authority_context),
    documentaryEvidence: response.evidence || [],
    inferences: response.inferences || [],
    contradictions: response.contradictions || [],
    missingness: response.missingness || [],
    retrievalDiagnostics: run.retrieval_diagnostics || null,
    followUpQueries: response.follow_up_queries || [],
    runStatus: run.status,
    interpretativeStatus: run.interpretative_status,
    rawModelResponse: run.raw_model_response,
    errorCode: run.error_code || null,
    errorMessage: run.error_message || null,
    persisted: true,
    retrievedChunkCount: sources.length,
    failureReason: run.error_message || null
  }
}

const getRetrievalDiagnosticItems = (diagnostics) => {
  if (!diagnostics) {
    return []
  }

  const items = []
  if (Number.isInteger(diagnostics.result_count)) {
    items.push(`Retrieved passages: ${diagnostics.result_count}.`)
  }
  if (Number.isFinite(diagnostics.max_score) && Number.isFinite(diagnostics.min_score)) {
    items.push(`Lexical score range: ${formatScore(diagnostics.min_score)} to ${formatScore(diagnostics.max_score)}.`)
  }
  if (diagnostics.possible_low_recall) {
    items.push('Weak lexical match or no retrieved passage was detected for this query.')
  }
  if (diagnostics.evidence_concentration) {
    items.push('Retrieved passages are concentrated in one document.')
  }
  if (diagnostics.retrieval_redundancy) {
    items.push('Multiple retrieved passages come from the same document.')
  }
  if (diagnostics.provenance_incomplete) {
    items.push('Some retrieved passages have incomplete provenance.')
  }
  if (diagnostics.requested_years?.length > 0) {
    items.push(`Requested temporal scope: ${diagnostics.requested_years.join(', ')}.`)
  }
  if (Number.isInteger(diagnostics.temporally_valid_result_count)) {
    items.push(`Temporally valid retrieved passages: ${diagnostics.temporally_valid_result_count}.`)
  }
  if (diagnostics.temporal_rejections?.length > 0) {
    items.push(`Temporal filtering excluded ${diagnostics.temporal_rejections.length} retrieved passage${diagnostics.temporal_rejections.length === 1 ? '' : 's'}.`)
  }
  diagnostics.notes?.forEach((note) => items.push(note))

  return items
}

const EvidenceTracer = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('granite')
  const [traceData, setTraceData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [persistenceError, setPersistenceError] = useState('')
  const [memoCopyError, setMemoCopyError] = useState('')
  const [memoCopied, setMemoCopied] = useState(false)
  const [citationCopyFeedback, setCitationCopyFeedback] = useState(null)
  const [memoDownloadError, setMemoDownloadError] = useState('')
  const [retrievalTrailExportError, setRetrievalTrailExportError] = useState('')
  const [savedRunLoadError, setSavedRunLoadError] = useState('')
  const currentRunIdRef = useRef(null)
  const rehydrationRequestRef = useRef(null)

  useEffect(() => {
    const seededQuery = searchParams.get('query') || searchParams.get('pid') || searchParams.get('chunkId') || ''
    if (seededQuery && !query) {
      setQuery(seededQuery)
    }
  }, [query, searchParams])

  useEffect(() => {
    const runId = searchParams.get('runId')
    if (!runId || (currentRunIdRef.current === runId && traceData?.queryId === runId)) {
      return undefined
    }

    if (!/^experiment-[A-Za-z0-9._-]+$/.test(runId)) {
      setSavedRunLoadError('The requested saved interrogation identifier is invalid.')
      return undefined
    }

    let cancelled = false
    let rehydrationRequest = rehydrationRequestRef.current
    if (!rehydrationRequest || rehydrationRequest.runId !== runId) {
      currentRunIdRef.current = runId
      rehydrationRequest = { runId, promise: getExperimentRun(runId) }
      rehydrationRequestRef.current = rehydrationRequest
    }
    setSavedRunLoadError('')
    setLoading(true)
    rehydrationRequest.promise
      .then((run) => {
        if (cancelled) return
        const restoredTrace = mapPersistedRunToTrace(run)
        currentRunIdRef.current = runId
        setTraceData(restoredTrace)
        setQuery(restoredTrace.prompt)
      })
      .catch((loadError) => {
        if (cancelled) return
        currentRunIdRef.current = null
        if (rehydrationRequestRef.current === rehydrationRequest) {
          rehydrationRequestRef.current = null
        }
        setSavedRunLoadError(loadError.message || 'The requested saved interrogation could not be loaded.')
      })
      .finally(() => !cancelled && setLoading(false))

    return () => { cancelled = true }
  }, [searchParams, traceData?.queryId])

  const handleTrace = async () => {
    if (!query.trim() || loading || mode !== 'granite') {
      return
    }

    setLoading(true)
    setError('')
    setPersistenceError('')
    setMemoCopyError('')
    setMemoCopied(false)
    setMemoDownloadError('')
    setRetrievalTrailExportError('')
    setSavedRunLoadError('')

    try {
      const analysis = await interrogateTurin(query, { top_k: 5 })
      const enrichedSources = mapRetrievedSources(analysis.retrieved_evidence)

      const nextTrace = {
        queryId: analysis.run_id,
        prompt: query,
        researchCase: analysis.research_case || null,
        corpusVersion: analysis.corpus_version || null,
        retrievalMethod: analysis.retrieval_method || null,
        retrieval: analysis.retrieval || null,
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
        retrievalDiagnostics: analysis.retrieval_diagnostics || null,
        followUpQueries: analysis.follow_up_queries || [],
        runStatus: analysis.status,
        interpretativeStatus: analysis.interpretative_status,
        rawModelResponse: analysis.raw_model_response,
        errorCode: analysis.error_code || null,
        errorMessage: analysis.error_message || null
      }

      setTraceData({
        ...nextTrace,
        persisted: true,
        retrievedChunkCount: nextTrace.retrievedChunkIds.length,
        failureReason: analysis.error_message || null
      })

      if (analysis.run_id) {
        currentRunIdRef.current = analysis.run_id
        const params = new URLSearchParams(searchParams)
        params.set('runId', analysis.run_id)
        navigate(`/source-interrogation?${params.toString()}`, { replace: true })
      }
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

    setCitationCopyFeedback(null)
    try {
      if (!navigator?.clipboard?.writeText) {
        throw new Error('Clipboard access is unavailable.')
      }
      await navigator.clipboard.writeText(citationText)
      setCitationCopyFeedback({ kind: 'success', title: 'Citation copied', subtitle: 'The current retrieval result remains unchanged.' })
    } catch (copyError) {
      setCitationCopyFeedback({ kind: 'error', title: 'Citation could not be copied', subtitle: copyError.message || 'The current retrieval result remains unchanged.' })
    }
  }

  const handleCopyMemo = async () => {
    if (!traceData) {
      return
    }

    setMemoCopyError('')
    setMemoCopied(false)
    try {
      if (!navigator?.clipboard?.writeText) {
        throw new Error('Clipboard API is unavailable.')
      }
      const memo = buildEvidenceTraceMemo({ trace: traceData })
      await navigator.clipboard.writeText(memo)
      setMemoCopied(true)
    } catch (copyError) {
      setMemoCopyError(copyError.message || 'Retrieval memo could not be copied to the clipboard.')
    }
  }

  const handleDownloadMemo = () => {
    if (!canUseRetrievalMemo) {
      return
    }

    setMemoDownloadError('')
    try {
      const memo = buildEvidenceTraceMemo({ trace: traceData })
      downloadMarkdown(getRetrievalMemoFilename(traceData.queryId), memo)
    } catch (downloadError) {
      setMemoDownloadError(downloadError.message || 'Retrieval memo could not be downloaded.')
    }
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
    if (!canExportRetrievalTrail) {
      return
    }

    setRetrievalTrailExportError('')
    try {
      const payload = await exportExperimentRunJson(traceData.queryId)
      downloadJson(getRetrievalTrailFilename(traceData.queryId), payload)
    } catch (exportError) {
      setRetrievalTrailExportError(exportError.message || 'Retrieval trail could not be exported.')
    }
  }

  const showNoSourcesReturned = Boolean(
    traceData &&
    !loading &&
    (traceData.retrievedChunkCount ?? traceData.sources?.length ?? 0) === 0
  )

  const validationFailure = traceData?.missingness?.find((item) => validationFailureCategories.has(item.category))
  const isModelRuntimeFailure = traceData?.errorCode === 'granite_failure'
  const scopedLimits = traceData?.missingness?.filter((item) => !validationFailureCategories.has(item.category)) || []
  const retrievalDiagnosticItems = getRetrievalDiagnosticItems(traceData?.retrievalDiagnostics)
  const canUseRetrievalMemo = Boolean(traceData && !error)
  const canExportRetrievalTrail = Boolean(traceData?.persisted && traceData.queryId)

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

      {savedRunLoadError && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Saved interrogation could not be loaded" subtitle={savedRunLoadError} />
        </Column>
      )}

      {retrievalTrailExportError && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Retrieval trail could not be exported" subtitle="The current interrogation result remains unchanged." />
        </Column>
      )}

      {memoCopied && (
        <Column>
          <InlineNotification lowContrast kind="success" title="Retrieval memo copied" subtitle="The current result remains unchanged." />
        </Column>
      )}

      {memoCopyError && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Retrieval memo could not be copied to the clipboard" subtitle="The current result remains unchanged." />
        </Column>
      )}

      {citationCopyFeedback && (
        <Column>
          <InlineNotification lowContrast kind={citationCopyFeedback.kind} title={citationCopyFeedback.title} subtitle={citationCopyFeedback.subtitle} />
        </Column>
      )}

      {memoDownloadError && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Retrieval memo could not be downloaded" subtitle="The current result remains unchanged." />
        </Column>
      )}

      {validationFailure && (
        <Column>
          <InlineNotification
            lowContrast
            kind="warning"
            title="Generated-response validation failure"
            subtitle={`Documentary evidence may have been retrieved, but the generated response could not be validated. ${validationFailure.explanation}`}
          />
        </Column>
      )}

      {isModelRuntimeFailure && (
        <Column>
          <InlineNotification
            lowContrast
            kind="warning"
            title="Model runtime failure"
            subtitle="The generated response could not be completed. Any retrieved evidence remains available below; this does not indicate corpus or historical absence."
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
                          : `${item.assertion} | Staff code: ${item.authority_id || 'unavailable'} | ${item.role || 'Role unavailable'} | ${item.tenure?.start_date || 'start unavailable'} to ${item.tenure?.end_date || 'end unavailable'}`}
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
              <section aria-label="Retrieval diagnostics">
                <h4>Retrieval diagnostics</h4>
                {retrievalDiagnosticItems.length > 0
                  ? retrievalDiagnosticItems.map((item, index) => <p key={`diagnostic-${index}`}>{item}</p>)
                  : <p>Retrieval diagnostics were not calculated for this run.</p>}
              </section>
              <section aria-label="Generated inference">
                <h4>Generated inference</h4>
                {traceData.inferences?.length > 0
                  ? traceData.inferences.map((item, index) => <p key={`${item.inference}-${index}`}>{item.inference} ({item.confidence})</p>)
                  : <p>No generated inference is asserted.</p>}
              </section>
              <section aria-label="Scoped evidential limits">
                <h4>Scoped evidential limits</h4>
                {scopedLimits.length > 0
                  ? scopedLimits.map((item, index) => (
                    <p key={`${item.category}-${index}`}>
                      <strong>{systemDerivedMissingnessCategories.has(item.category) ? 'System-derived' : 'Model-generated'}:</strong> {item.explanation}
                    </p>
                  ))
                  : <p>No scoped evidential limits were recorded.</p>}
              </section>
              <section aria-label="Provenance validation">
                <h4>Provenance validation</h4>
                <p>{traceData.inferenceProvenance?.valid ? 'Valid for supplied citations.' : 'Requires researcher review.'} Run status: {traceData.runStatus || 'unavailable'}; interpretative status: {traceData.interpretativeStatus || 'unassessed'}.</p>
              </section>
            </div>
          )}

          {traceData && (
            <div className="tracer__answer-controls">
              {canUseRetrievalMemo && <Button kind="ghost" size="sm" renderIcon={Copy} onClick={handleCopyMemo}>Copy retrieval memo</Button>}
              {canUseRetrievalMemo && <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleDownloadMemo}>Download retrieval memo</Button>}
              {canExportRetrievalTrail && <Button kind="ghost" size="sm" renderIcon={Download} onClick={exportRetrievalTrail}>Export retrieval trail</Button>}
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
