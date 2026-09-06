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
import { exportExperimentRunJson, getExperimentRun, getResearcherUiCapture, interrogateExploratory, retrieveExploratoryV3 } from '../../api/experiments'
import { getRuntimeModelInfo } from '../../api/runtime'
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

const missingnessOriginLabel = (item) => {
  if (item.origin === 'system_pipeline') return 'Pipeline-derived'
  if (item.origin === 'documentary') return 'Documentary'
  if (item.origin === 'authority') return 'Authority-derived'
  if (item.origin === 'model') return 'Model-generated'
  return systemDerivedMissingnessCategories.has(item.category) ? 'System-derived' : 'Model-generated'
}

const formatInference = (item) => {
  const inference = item?.claim_text || item?.inference || (typeof item === 'string' ? item : '')
  return item?.confidence ? `${inference} (${item.confidence})` : inference
}

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

const mapRetrievedSources = (retrievedEvidence = []) => retrievedEvidence.map((source) => {
  const provenanceFields = { ...(source.provenance || {}), ...(source.snapshot?.provenance || {}) }
  const provenance = Object.keys(provenanceFields).length > 0 ? provenanceFields : null
  const canonicalAssetPid = provenance?.asset_pid || source.asset_pid || source.pid

  return {
  sourceId: source.source_id,
  chunkId: source.chunk_id,
  documentId: source.document_id,
  pid: canonicalAssetPid,
  date: source.archive_nomination?.display_date || source.snapshot?.date || source.date || null,
  archiveRecordPid: provenance?.archive_record_pid || source.archive_record_pid,
  rank: source.rank,
  title: source.snapshot?.title || source.snapshot?.catalogue_metadata?.title || source.title || source.document_id,
  page: source.page_start,
  section: source.snapshot?.source_section || null,
  excerpt: source.excerpt || source.text,
  score: source.score,
  citation: `${source.snapshot?.title || source.document_id} | Asset PID: ${canonicalAssetPid || 'unavailable'} | Page: ${source.page_start || 'unavailable'}`,
  citationStatus: ['resolved_current', 'archive_resolved_current'].includes(source.archive_resolution_status) ? 'loaded' : 'unavailable',
  provenance,
  provenanceStatus: ['resolved_current', 'archive_resolved_current'].includes(source.archive_resolution_status) ? 'loaded' : 'unavailable',
  evidenceClassification: source.evidence_classification || null,
  retrievalChannels: source.retrieval_channels || [],
  metadataMatches: source.metadata_matches || [],
  combinedScore: source.combined_score,
  sourceNominationChannels: source.source_nomination_channels || [],
  sourceNominationScore: source.source_nomination_score,
  archiveNominationReasons: source.archive_nomination?.nomination_reasons || [],
  sourceType: source.source_type_projection?.value || source.snapshot?.source_type || source.source_type || null,
  temporalClass: source.temporal_class || source.snapshot?.temporal_class || null,
  classificationProjection: source.classification_projection || null,
  formulation: source.formulation_projection?.value || null,
  classificationAuditNote: source.classification_audit_note || null,
  unclassifiedStatus: source.unclassified_status || null,
  contributorStatus: source.contributor_status || null,
  sourceFamily: source.source_family_projection || null,
  passageEvidenceChannel: source.passage_evidence_channel || null,
  passageScore: source.passage_score,
  passageScoreComponents: source.passage_score_components || null,
  facetCoverage: source.facet_coverage || [],
  laneNominations: source.lane_nominations || [],
  authorityGraphSignals: source.authority_graph_signals || null,
  selectionReason: source.selection_reason || null,
  textScore: source.text_score,
  metadataScore: source.metadata_score,
  identity: {
    recordPid: provenance?.archive_record_pid || source.archive_record_pid,
    mediaPid: provenance?.attached_media_pid || source.pid,
    assetPid: canonicalAssetPid
  }
  }
})

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
    claimProvenanceResult: run.provenance_validation || null,
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
    pipelineFailure: response.pipeline_failure || null,
    persisted: true,
    retrievedChunkCount: sources.length,
    failureReason: run.error_message || null
  }
}

const mapCaptureToTrace = (capture) => {
  const sources = mapRetrievedSources(capture.retrieved_sources).map((source) => ({
    ...source,
    classificationScope: source.classificationProjection?.reason || (source.evidenceClassification?.classification === 'DIRECT_SUPPORT'
      ? 'Direct support for a component of the query; it does not alone establish every part of the registered question.'
      : null),
    personNameStatus: capture.question_id === 'Q12' ? 'Henrietta Ryott explicitly named: NO' : null,
    temporalAuditStatus: capture.question_id === 'Q12'
      ? source.sourceId === 'S2'
        ? 'Within 1973–77, but does not name Ryott or establish a role.'
        : `Outside the 1973–77 scope: ${source.date || 'date not retained'}; this generic DDR material cannot establish Ryott’s in-period role.`
      : null,
    unclassifiedStatus: capture.question_id === 'Q12' && source.evidenceClassification?.classification === 'UNCLASSIFIED'
      ? 'UNCLASSIFIED — model did not classify'
      : source.unclassifiedStatus
  }))
  const claims = capture.claim_provenance || []
  const claimsFor = (section) => claims.filter((claim) => claim.section === section && claim.provenance_status !== 'FORMAT_VIOLATION')

  return {
    queryId: capture.capture_id,
    questionId: capture.question_id || null,
    prompt: capture.exact_question || '',
    corpusVersion: capture.corpus_version || null,
    retrievalMethod: 'turin-archive-first-retrieval-v1',
    answer: capture.answer || '',
    response: capture.answer || '',
    model: capture.model_config?.display_name || capture.model_config?.model || 'Qwen researcher capture',
    retrievedChunkIds: sources.map((source) => source.chunkId).filter(Boolean),
    citations: sources.map((source) => source.citation).filter(Boolean),
    pageRanges: sources.map((source) => source.page).filter(Boolean),
    timestamp: capture.created_at || null,
    sources,
    sourceProvenance: capture.source_provenance || null,
    claimProvenance: claims,
    claimProvenanceResult: capture.claim_provenance_result || null,
    documentaryEvidence: claimsFor('DIRECT DOCUMENTARY EVIDENCE'),
    inferences: claimsFor('CROSS-SOURCE INFERENCE'),
    evidentialLimits: claimsFor('WHAT THE EVIDENCE DOES NOT ESTABLISH'),
    formatViolations: claims.filter((claim) => claim.provenance_status === 'FORMAT_VIOLATION'),
    captureDerivedLimits: capture.question_id === 'Q03'
      ? [
          'No selected passage directly co-names Ken Baynes and Phil Roberts.',
          'The retained documentary passages do not establish their interpersonal relationship, collaboration, division of responsibility, joint authorship, joint leadership, or causal significance.'
        ]
      : capture.question_id === 'Q04'
        ? [
            'No selected passage directly evidences John Wood in console-design activity.',
            'The selected passages do not establish the precise scope or continuity of Wood’s role, leadership or responsibility, project-wide significance, or fully complementary source-type evidence.'
          ]
        : capture.question_id === 'Q05'
          ? [
              'The selected passages do not establish a formally agreed DDR definition of design research or contributor-wide agreement.',
              'They do not establish whether the recorded differences amount to genuine disagreement rather than variation, provide a retrospective comparison, or establish that the surviving digitised corpus is complete enough for an institution-wide conclusion.'
            ]
          : capture.question_id === 'Q06'
            ? [
                'The selected passages do not establish actual contributor disagreement, influence between contributors, contributor-wide consensus, or a DDR-wide institutional position.',
                'They do not establish whether shared disciplinary references imply shared epistemic commitments, represent all relevant voices, or establish whether later accounts accurately reflect contemporary positions.',
                'Four of five retained sources are from the Job 171 source family; the capture does not represent the whole DDR merely because several formulations are present.'
              ]
            : capture.question_id === 'Q08'
              ? [
                  'The selected passages do not establish direct disagreement, explicit contributor opposition, a single DDR systematic-design doctrine, or change over time.',
                  'They do not establish full coverage of methodological positions or whether later interpretation shaped these positions.',
                  'S4 and S5 contain methodological formulations not substantively developed by Qwen; the available plurality exceeds the generated synthesis.'
                ]
              : capture.question_id === 'Q09'
                ? [
                    'Closure decision: NOT ESTABLISHED BY RETAINED PASSAGES. Cause of closure: NOT ESTABLISHED BY RETAINED PASSAGES.',
                    'Known relevant archive source not retained in this capture: the Senate resolution of 21 November 1984 records closure and merger of the Department of Design Research and Department of Environmental Design into the Department of Architectural and Design Studies. This is a retrieval diagnostic, not evidence supplied to Qwen.',
                    'Missingness layer: RETRIEVAL_FAILURE. This run alone does not justify an ARCHIVAL_ABSENCE, DOCUMENTARY_INSUFFICIENCY, or corpus-wide absence conclusion.',
                    'Selected evidence does not establish the cause. Qwen’s corpus-level negative is broader than the retained evidence supports because the known closure anchor was omitted.'
                  ]
                : capture.question_id === 'Q11'
                  ? [
                      'Intended purpose is evidenced: design awareness, capability, epistemological development, and interdisciplinary curriculum contribution. Intended audiences are only broadly evidenced; no user testimony is retained.',
                      'Implementation is evidenced by S5, which describes classroom implementation as half-hearted and confused. This is implementation evidence only, not user feedback.',
                      'NO DIRECT USER-RECEPTION EVIDENCE RETAINED: no selected passage records feedback, adoption, rejection, reported experience, user testimony, or evaluation by intended users.',
                      'Programme intention does not establish user reception. Implementation does not establish user reception. Classroom difficulty does not establish user feedback.',
                      'Missingness classification: DOCUMENTARY_INSUFFICIENCY. Relevant programme and implementation evidence is present, but no retained passage records actual user response.'
                    ]
                  : capture.question_id === 'Q12'
                    ? [
                        'No retained passage names Henrietta Ryott. No direct role evidence or partial person-specific evidence is present in this capture.',
                        'Only S2 is within the 1973–77 scope (November 1975); it is generic DDR context and does not name Ryott or establish a role. The 1978, 1979, and circa-1984 sources cannot establish her in-period role.',
                        'Missingness classification: RETRIEVAL_FAILURE. The Henrietta Ryott authority/entity anchor resolved, but no retained passage explicitly names her. This capture cannot establish ARCHIVAL_ABSENCE or DOCUMENTARY_INSUFFICIENCY.',
                        'Supported by this capture: no supplied passage establishes Henrietta Ryott’s role. Too broad for this capture: the current digitised corpus does not establish her role.'
                      ]
      : [],
    captureAuditSummary: capture.question_id === 'Q08'
      ? 'False unity avoided. Contestation only partially developed: Qwen preserved some plurality and avoided a unified doctrine, but underused methodological differences already available in S4 and S5.'
      : capture.question_id === 'Q09'
        ? 'Cautious but over-broad corpus-level negative: Qwen did not invent a cause, but the retained passages cannot support its conclusion about the whole digitised corpus.'
        : capture.question_id === 'Q11'
          ? 'ACTIVITY_WITHOUT_RECEPTION: the retained evidence establishes programme purpose and some implementation context, but not how intended users received it.'
          : capture.question_id === 'Q12'
            ? 'Qwen restraint retained: it does not invent a staff position, project responsibility, teaching role, research role, administrative responsibility, or continuity across 1973–77. Its corpus-wide negative remains broader than the failed person-specific retrieval supports.'
      : null,
    retrievalDiagnostics: capture.retrieval_diagnostics || null,
    rawModelResponse: capture.raw_model_response,
    runStatus: 'completed',
    interpretativeStatus: 'researcher review required',
    persisted: true,
    exportable: false,
    retrievedChunkCount: sources.length,
    capture: true
  }
}

const displayCaptureAnswer = (trace) => {
  if (!trace?.capture) return trace?.answer || ''
  return (trace.answer || '').replace(/\n\*{0,2}EXACT REGISTERED QUESTION\*{0,2}[\s\S]*$/, '')
}

const getRetrievalDiagnosticItems = (diagnostics) => {
  if (!diagnostics) {
    return []
  }

  const items = []
  if (Number.isInteger(diagnostics.result_count)) {
    items.push(`Retrieved passages: ${diagnostics.result_count}.`)
  }
  if (Number.isInteger(diagnostics.retained_source_count)) {
    items.push(`Retained capture sources: ${diagnostics.retained_source_count}.`)
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

  if (diagnostics.retrieval_adequacy) {
    items.push(`Retrieval adequacy: ${diagnostics.retrieval_adequacy.status}.`)
  }

  return items
}

const EvidenceTracer = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('runtime')
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
  const [runtimeInfo, setRuntimeInfo] = useState(null)
  const currentRunIdRef = useRef(null)
  const rehydrationRequestRef = useRef(null)

  useEffect(() => {
    const seededQuery = searchParams.get('query') || searchParams.get('pid') || searchParams.get('chunkId') || ''
    if (seededQuery && !query) {
      setQuery(seededQuery)
    }
  }, [query, searchParams])

  useEffect(() => {
    let cancelled = false
    getRuntimeModelInfo().then((info) => !cancelled && setRuntimeInfo(info)).catch(() => !cancelled && setRuntimeInfo(null))
    return () => { cancelled = true }
  }, [])

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

  useEffect(() => {
    const captureId = searchParams.get('captureId')
    if (!captureId || (currentRunIdRef.current === captureId && traceData?.queryId === captureId)) {
      return undefined
    }
    if (!/^researcher-ui-capture-[A-Za-z0-9._-]+$/.test(captureId)) {
      setSavedRunLoadError('The requested researcher capture identifier is invalid.')
      return undefined
    }

    let cancelled = false
    currentRunIdRef.current = captureId
    setSavedRunLoadError('')
    setLoading(true)
    getResearcherUiCapture(captureId)
      .then((capture) => {
        if (cancelled) return
        const restoredTrace = mapCaptureToTrace(capture)
        setTraceData(restoredTrace)
        setQuery(restoredTrace.prompt)
        setMode('archive-first-one-shot')
      })
      .catch((loadError) => {
        if (!cancelled) setSavedRunLoadError(loadError.message || 'The requested researcher capture could not be loaded.')
      })
      .finally(() => !cancelled && setLoading(false))

    return () => { cancelled = true }
  }, [searchParams, traceData?.queryId])

  const handleTrace = async () => {
    if (!query.trim() || loading || !['runtime', 'archive-first-one-shot', 'retrieval-v3'].includes(mode)) {
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
      const analysis = mode === 'retrieval-v3'
        ? await retrieveExploratoryV3(query, { top_k: 5 })
        : await interrogateExploratory(query, { top_k: 5, mode: mode === 'archive-first-one-shot' ? 'archive_first_one_shot' : 'exploratory' })
      const enrichedSources = mapRetrievedSources(analysis.retrieved_evidence || analysis.final_five)

      const nextTrace = {
        queryId: analysis.run_id || analysis.capture_id,
        prompt: query,
        researchCase: analysis.research_case || null,
        corpusVersion: analysis.corpus_version || null,
        retrievalMethod: analysis.retrieval_method || null,
        retrieval: analysis.retrieval || null,
        answer: analysis.answer || (mode === 'retrieval-v3' ? 'Retrieval-only diagnostic completed. No model inference was requested.' : ''),
        response: analysis.answer || '',
        model: analysis.model?.display_name || analysis.model?.name || (mode === 'retrieval-v3' ? 'Retrieval v3 (model-neutral)' : 'Active local runtime'),
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
        failed_or_partial: analysis.status !== 'completed',
        caveats: analysis.missingness?.map((item) => item.explanation) || [],
        sources: enrichedSources,
        inferenceProvenance: analysis.provenance_validation,
        sourceProvenance: { valid: enrichedSources.length > 0 && enrichedSources.every((source) => source.provenanceStatus === 'loaded'), source_count: enrichedSources.length },
        claimProvenance: analysis.provenance_validation?.claim_provenance || [],
        claimProvenanceResult: analysis.provenance_validation?.claim_provenance
          ? { valid: analysis.provenance_validation.valid, claim_count: analysis.provenance_validation.claim_count }
          : null,
        authorityEvidence: analysis.authority_evidence || [],
        documentaryEvidence: analysis.documentary_evidence || [],
        contextualEvidence: analysis.contextual_evidence || [],
        inferences: analysis.inferences || [],
        contradictions: analysis.contradictions || [],
        missingness: analysis.missingness || [],
        retrievalDiagnostics: analysis.retrieval_diagnostics || { ...(analysis.diagnostics || {}), retrieval_adequacy: analysis.retrieval_adequacy },
        retrievalV3: mode === 'retrieval-v3' ? analysis : null,
        followUpQueries: analysis.follow_up_queries || [],
        runStatus: analysis.status,
        interpretativeStatus: analysis.interpretative_status,
        rawModelResponse: analysis.raw_model_response,
        errorCode: analysis.error_code || null,
        errorMessage: analysis.error_message || null
      }

      setTraceData({
        ...nextTrace,
        persisted: Boolean(analysis.persisted),
        retrievedChunkCount: nextTrace.retrievedChunkIds.length,
        failureReason: analysis.error_message || null
      })

      if (analysis.run_id) {
        currentRunIdRef.current = analysis.run_id
        const params = new URLSearchParams(searchParams)
        params.set('runId', analysis.run_id)
        navigate(`/source-interrogation?${params.toString()}`, { replace: true })
      } else if (analysis.capture_id) {
        currentRunIdRef.current = analysis.capture_id
        const params = new URLSearchParams(searchParams)
        params.set('captureId', analysis.capture_id)
        navigate(`/source-interrogation?${params.toString()}`, { replace: true })
      }
    } catch (traceError) {
      const failedTrace = {
        query,
        answer: '',
        model: runtimeInfo?.display_name || 'Active Turin runtime',
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
      return runtimeInfo?.status === 'ready'
        ? { label: runtimeInfo?.display_name || 'Turin runtime ready', type: 'green' }
        : runtimeInfo ? { label: 'Retrieval only', type: 'gray' } : { label: 'Unavailable', type: 'red' }
    }

    const loaded = traceData.sources.filter((source) => source.provenanceStatus === 'loaded').length
    if (loaded === traceData.sources.length && loaded > 0) {
      return { label: 'Provenance enabled', type: 'green' }
    }

    if (loaded > 0 || traceData.sources.some((source) => source.citationStatus === 'loaded')) {
      return { label: 'Partial provenance', type: 'blue' }
    }

    return { label: 'Retrieval only', type: 'gray' }
  }, [runtimeInfo, traceData])

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
  const isModelRuntimeFailure = traceData?.errorCode === 'runtime_failure'
  const scopedLimits = traceData?.missingness?.filter((item) => !validationFailureCategories.has(item.category)) || []
  const retrievalDiagnosticItems = getRetrievalDiagnosticItems(traceData?.retrievalDiagnostics)
  const canUseRetrievalMemo = Boolean(traceData && !error)
  const canExportRetrievalTrail = Boolean(traceData?.persisted && traceData.queryId && traceData.exportable !== false)

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
            description="Use the active local inference path first. This view preserves provenance as mandatory, not optional."
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

            <Select id="trace-mode" labelText="Mode / model selector" value={mode} onChange={(e) => setMode(e.target.value)} disabled={Boolean(traceData?.capture)}>
              <SelectItem value="runtime" text={runtimeInfo?.display_name || 'Active Turin runtime'} />
              <SelectItem value="archive-first-one-shot" text="Archive-first · One-shot Qwen · Researcher capture" />
              <SelectItem value="retrieval-v3" text="Retrieval v3 diagnostic (no model)" />
              <SelectItem value="agent" text="Agent trace, unavailable" disabled />
            </Select>
          </div>

          <div className="tracer__query-actions">
            <Button renderIcon={Search} onClick={handleTrace} disabled={!query.trim() || loading || !['runtime', 'archive-first-one-shot', 'retrieval-v3'].includes(mode)}>
              {mode === 'retrieval-v3' ? 'Inspect retrieval' : 'Run interrogation'}
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
            description="Model-assisted response with explicit source-backing, caveats, and export controls. Generated answers remain provisional until checked against retrieved source chunks."
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
            {traceData ? (displayCaptureAnswer(traceData) || 'No answer returned.') : 'No answer returned yet. Submit a query to begin evidence tracing.'}
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
                  ? traceData.documentaryEvidence.map((item, index) => <p key={item.claim_id || item.chunk_id || index}>{item.claim_text || item.claim}</p>)
                  : <p>No documentary claim is asserted beyond the retrieved source stack.</p>}
              </section>
              <section aria-label="Retrieval diagnostics">
                <h4>Retrieval diagnostics</h4>
                {retrievalDiagnosticItems.length > 0
                  ? retrievalDiagnosticItems.map((item, index) => <p key={`diagnostic-${index}`}>{item}</p>)
                  : <p>Retrieval diagnostics were not calculated for this run.</p>}
              </section>
              {traceData.retrievalV3 && (
                <section aria-label="Retrieval v3 explanation">
                  <h4>Retrieval v3 explanation</h4>
                  <p>Template: {traceData.retrievalV3.retrieval_template}; adequacy: {traceData.retrievalV3.retrieval_adequacy?.status}.</p>
                  <p>{traceData.retrievalV3.retrieval_adequacy?.missingness_safety_message || 'Retrieval adequacy permits corpus-level missingness evaluation only after researcher review.'}</p>
                  {traceData.sources.map((source) => (
                    <div key={`v3-${source.chunkId}`}>
                      <p>Source {source.rank}: lanes {source.laneNominations.map((item) => item.lane).join(', ') || 'none'}.</p>
                      {source.authorityGraphSignals?.edges?.length > 0 && (
                        <p>Authority graph: {source.authorityGraphSignals.edges.map((edge) => `${edge.authority_label} (${edge.authority_id}; ${edge.relation_type}; ${edge.trigger_field}: ${edge.trigger_value_raw})`).join('; ')}.</p>
                      )}
                      <p>Passage: page {source.page || 'unavailable'}; chunk {source.chunkId}; facets {source.facetCoverage.join(', ') || 'none'}; score {formatScore(source.passageScore) || 'unavailable'}; components {source.passageScoreComponents ? Object.entries(source.passageScoreComponents).map(([key, value]) => `${key}=${value}`).join(', ') : 'unavailable'}.</p>
                    </div>
                  ))}
                </section>
              )}
              <section aria-label="Qwen interpretation">
                <h4>Qwen interpretation</h4>
                {traceData.pipelineFailure
                  ? <><p>Qwen interpretation unavailable</p><p>Formal run stopped at {traceData.pipelineFailure.stage === 'source_analysis' ? 'Stage A schema validation' : traceData.pipelineFailure.stage}.</p><p>{traceData.pipelineFailure.raw_output_preserved ? 'Raw Stage A model output is preserved with the immutable run.' : traceData.errorMessage || 'No final synthesis was produced.'}</p>{traceData.pipelineFailure.raw_output_preserved && traceData.rawModelResponse && <details className="tracer__raw-capture"><summary>Raw Stage A model output (immutable audit record)</summary><pre>{traceData.rawModelResponse}</pre></details>}</>
                  : traceData.inferences?.length > 0
                  ? traceData.inferences.map((item, index) => <p key={item?.claim_id || item?.inference || `inference-${index}`}>{formatInference(item)}</p>)
                  : <p>No generated inference is asserted.</p>}
              </section>
              <section aria-label="Evidential limits">
                <h4>Evidential limits</h4>
                {(traceData.evidentialLimits || scopedLimits).length > 0
                  ? (traceData.evidentialLimits || scopedLimits).map((item, index) => (
                    <p key={item.claim_id || `${item.category}-${index}`}>
                      <strong>{missingnessOriginLabel(item)}:</strong> {item.claim_text || item.explanation}
                    </p>
                  ))
                  : <p>No scoped evidential limits were recorded.</p>}
                {traceData.captureDerivedLimits?.map((limit, index) => <p key={`capture-limit-${index}`}><strong>Capture-derived documentary boundary:</strong> {limit}</p>)}
                {traceData.captureDerivedLimits?.length > 0 && <p>These are limits of the selected documentary passages in this immutable capture, not evidence of archival absence.</p>}
                {traceData.captureAuditSummary && <p><strong>Capture audit:</strong> {traceData.captureAuditSummary}</p>}
              </section>
              <section aria-label="Source provenance">
                <h4>Source provenance</h4>
                <p>{traceData.sourceProvenance?.valid ? 'PASS' : 'Requires researcher review.'} Documentary passage archival/document/page chain: {traceData.sourceProvenance?.source_count ?? traceData.sources.length} source{(traceData.sourceProvenance?.source_count ?? traceData.sources.length) === 1 ? '' : 's'}.</p>
              </section>
              <section aria-label="Model claim provenance">
                <h4>Model-claim provenance</h4>
                <p>{traceData.claimProvenanceResult?.valid ? 'PASS' : 'PARTIAL / requires researcher review.'} Generated substantive claims must cite valid supplied documentary sources.</p>
                {traceData.claimProvenance?.length > 0 && (
                  <div className="tracer__claim-provenance">
                    {traceData.claimProvenance.map((claim) => (
                      <div className="tracer__claim" key={claim.claim_id}>
                        <p><strong>{claim.section}</strong></p>
                        <p>{claim.claim_text}</p>
                        <p>Source IDs: {claim.source_ids?.join(', ') || 'None'} | Status: <strong>{claim.provenance_status}</strong></p>
                      </div>
                    ))}
                  </div>
                )}
                {traceData.formatViolations?.length > 0 && <InlineNotification lowContrast kind="warning" title="Model output contained unexpected structural/prompt-echo text." subtitle="The raw capture is preserved exactly; this text is recorded as FORMAT_VIOLATION, not as an evidential claim." />}
                {traceData.capture && <details className="tracer__raw-capture"><summary>Raw one-shot output (immutable audit record)</summary><pre>{traceData.rawModelResponse}</pre></details>}
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
            description={traceData?.questionId === 'Q03'
              ? 'Question → archive-first source nomination → Baynes / Roberts / DEU documentary sources → selected passages → evidence set → one-shot Qwen → generated response.'
              : traceData?.questionId === 'Q05'
                ? 'Question → archive-first source nomination → documentary sources → selected passages → plural evidence set → one-shot Qwen → qualified synthesis.'
                : traceData?.questionId === 'Q06'
                  ? 'Question → archive-first source nomination → documentary sources → selected passages → plural evidence set → one-shot Qwen → qualified synthesis.'
                  : traceData?.questionId === 'Q08'
                    ? 'Question → archive-first source nomination → documentary sources → selected passages → multiple methodological formulations → one-shot Qwen → partial contestation synthesis.'
                    : traceData?.questionId === 'Q09'
                      ? 'Question → archive-first source nomination → five retained DDR sources → all NO_RELEVANT_PASSAGE → known closure anchor not retained → one-shot Qwen → cautious but over-broad corpus-level negative.'
                      : traceData?.questionId === 'Q11'
                        ? 'Question → archive-first source nomination → Design in General Education sources → purpose / curriculum / implementation evidence → no user-reception evidence → one-shot Qwen → bounded ACTIVITY_WITHOUT_RECEPTION conclusion.'
                        : traceData?.questionId === 'Q12'
                          ? 'Question → Henrietta Ryott authority anchor → archive-first source nomination → five generic DDR sources → no Ryott-naming passage retained → one-shot Qwen → bounded negative answer → RETRIEVAL_FAILURE.'
                : 'Question → archive-first source nomination → documentary sources / passages → evidence set → one-shot Qwen → generated response.'}
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
