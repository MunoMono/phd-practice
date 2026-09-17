import { Button, InlineNotification, Select, SelectItem, Tag, TextArea, TextInput, Tile } from '@carbon/react'
import { Download, Notebook, Save } from '@carbon/icons-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader'
import PanelHeader from '../../components/layout/PanelHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import { exportExperimentRunJson, getExperimentRun, listExperimentRuns, saveExperimentAssessment } from '../../api/experiments'
import { downloadFile } from '../../utils/workbenchExport'

const scoreFields = [
  ['retrieval_relevance', 'Retrieval relevance'],
  ['provenance_accuracy', 'Provenance accuracy'],
  ['interpretative_restraint', 'Interpretative restraint'],
  ['preservation_of_contestation', 'Preservation of contestation'],
  ['missingness_handling', 'Missingness handling'],
]

const blankAssessment = () => ({
  retrieval_relevance: '', provenance_accuracy: '', interpretative_restraint: '',
  preservation_of_contestation: '', missingness_handling: '', failure_categories: '', notes: '', authority_influence_note: '',
})

const normalizeAssessment = (assessment) => {
  const stored = assessment || {}
  return {
  ...blankAssessment(),
  ...Object.fromEntries(scoreFields.map(([key]) => [key, stored[key] === null || stored[key] === undefined ? '' : String(stored[key])])),
  failure_categories: (stored.failure_categories || []).join(', '),
  notes: stored.notes || '',
  authority_influence_note: stored.authority_influence_note || '',
  }
}

const assessmentPayload = (assessment) => ({
  ...Object.fromEntries(scoreFields.map(([key]) => [key, assessment[key] === '' ? null : Number(assessment[key])])),
  failure_categories: assessment.failure_categories.split(',').map((item) => item.trim()).filter(Boolean),
  notes: assessment.notes || null,
  authority_influence_note: assessment.authority_influence_note || null,
})

const engineeringRecordNotes = {
  'experiment-886cbe24b464': 'Granite runtime timeout boundary. This legacy immutable record did not retain a detailed runtime message.',
}

const ResearchRuns = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const [runs, setRuns] = useState([])
  const [run, setRun] = useState(null)
  const [assessmentBases, setAssessmentBases] = useState({})
  const [assessmentDrafts, setAssessmentDrafts] = useState({})
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [operationError, setOperationError] = useState('')
  const [detailState, setDetailState] = useState('idle')
  const [savingAssessmentRunId, setSavingAssessmentRunId] = useState('')
  const [savedAssessmentRunIds, setSavedAssessmentRunIds] = useState({})
  const [assessmentSaveErrorRunIds, setAssessmentSaveErrorRunIds] = useState({})
  const requestedRunId = searchParams.get('runId') || ''
  const isSelectedRunLoaded = run?.run_id === requestedRunId
  const persistedAssessment = isSelectedRunLoaded
    ? (assessmentBases[requestedRunId] || normalizeAssessment(run.assessment))
    : blankAssessment()
  const assessment = isSelectedRunLoaded
    ? (Object.hasOwn(assessmentDrafts, requestedRunId) ? assessmentDrafts[requestedRunId] : persistedAssessment)
    : blankAssessment()
  const isAssessmentDirty = isSelectedRunLoaded && JSON.stringify(assessment) !== JSON.stringify(persistedAssessment)

  useEffect(() => {
    let cancelled = false
    listExperimentRuns()
      .then((payload) => {
        if (!cancelled) {
          setRuns(payload.experiment_runs || [])
        }
      })
      .catch(() => !cancelled && setListError('Unable to load saved research runs.'))
      .finally(() => !cancelled && setListLoading(false))
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!requestedRunId) {
      setRun(null)
      setDetailState('idle')
      return undefined
    }
    let cancelled = false
    setRun(null)
    setDetailState('loading')
    getExperimentRun(requestedRunId)
      .then((payload) => {
        if (cancelled) return
        if (payload.run_id !== requestedRunId) {
          throw new Error('Saved run identity did not match the requested run.')
        }
        setRun(payload)
        setAssessmentBases((current) => ({ ...current, [requestedRunId]: normalizeAssessment(payload.assessment) }))
        setDetailState('loaded')
      })
      .catch(() => !cancelled && setDetailState('error'))
    return () => { cancelled = true }
  }, [requestedRunId])

  const selectRun = (nextRunId) => {
    setRun(null)
    setOperationError('')
    setDetailState(nextRunId ? 'loading' : 'idle')
    const nextSearchParams = new URLSearchParams(searchParams)
    if (nextRunId) nextSearchParams.set('runId', nextRunId)
    else nextSearchParams.delete('runId')
    setSearchParams(nextSearchParams)
  }

  const downloadJson = async () => {
    try {
      const payload = await exportExperimentRunJson(requestedRunId)
      downloadFile(`${requestedRunId}.json`, `${JSON.stringify(payload, null, 2)}\n`, 'application/json;charset=utf-8')
    } catch (requestError) {
      setOperationError(requestError.message || 'Unable to export JSON.')
    }
  }

  const downloadReport = () => {
    window.open(`/api/experiments/${requestedRunId}/report`, '_blank', 'noopener,noreferrer')
  }

  const saveAssessment = async () => {
    if (!isSelectedRunLoaded || !isAssessmentDirty || savingAssessmentRunId) return
    const saveTargetRunId = run.run_id
    const savePayload = assessmentPayload(assessment)
    setSavingAssessmentRunId(saveTargetRunId)
    setSavedAssessmentRunIds((current) => {
      const { [saveTargetRunId]: _, ...remaining } = current
      return remaining
    })
    setAssessmentSaveErrorRunIds((current) => {
      const { [saveTargetRunId]: _, ...remaining } = current
      return remaining
    })
    try {
      const saved = await saveExperimentAssessment(saveTargetRunId, savePayload)
      if (saved.run_id !== saveTargetRunId) {
        throw new Error('Saved assessment identity did not match the requested run.')
      }
      const updatedAssessment = normalizeAssessment(saved.assessment)
      setAssessmentBases((current) => ({ ...current, [saveTargetRunId]: updatedAssessment }))
      setAssessmentDrafts((current) => {
        const { [saveTargetRunId]: _, ...remaining } = current
        return remaining
      })
      setRun((current) => current?.run_id === saveTargetRunId ? { ...current, assessment: saved.assessment } : current)
      setSavedAssessmentRunIds((current) => ({ ...current, [saveTargetRunId]: true }))
    } catch {
      setAssessmentSaveErrorRunIds((current) => ({ ...current, [saveTargetRunId]: true }))
    } finally {
      setSavingAssessmentRunId('')
    }
  }

  const updateAssessmentDraft = (field, value) => {
    setAssessmentDrafts((current) => ({
      ...current,
      [requestedRunId]: { ...assessment, [field]: value },
    }))
    setSavedAssessmentRunIds((current) => {
      const { [requestedRunId]: _, ...remaining } = current
      return remaining
    })
    setAssessmentSaveErrorRunIds((current) => {
      const { [requestedRunId]: _, ...remaining } = current
      return remaining
    })
  }

  const response = run?.structured_response || {}
  const budget = run?.context?.budget || {}
  const authority = run?.authority_context || {}
  const evidenceHashCount = run?.retrieved_evidence?.filter((item) => item.evidence_sha256).length || 0
  const failureDetail = run?.error_message || engineeringRecordNotes[run?.run_id] || 'No detailed failure message was retained in this immutable record.'

  return (
    <PageGrid className="research-runs">
      <Column>
        <PageHeader title="Research runs" description="Inspect immutable archival experiment evidence, generated analysis, scoped missingness, and separate researcher assessment." actions={<Tag type="teal" size="md"><Notebook size={16} /> Immutable run records</Tag>} />
      </Column>
      {listError && <Column><InlineNotification lowContrast kind="error" title="Research runs unavailable" subtitle={listError} /></Column>}
      {operationError && <Column><InlineNotification lowContrast kind="error" title="Research runs unavailable" subtitle={operationError} /></Column>}
      <Column>
        <Tile>
          <PanelHeader title="Saved runs" description="Each record retains its query, corpus, model and evidence snapshot." />
          <Select id="saved-run" labelText="Saved experiment run" value={requestedRunId} onChange={(event) => selectRun(event.target.value)}>
            <SelectItem value="" text={listLoading ? 'Loading saved runs...' : runs.length ? 'Select a saved run' : 'No saved runs available'} />
            {requestedRunId && !runs.some((item) => item.run_id === requestedRunId) && <SelectItem value={requestedRunId} text="Requested saved run unavailable" />}
            {runs.map((item) => <SelectItem key={item.run_id} value={item.run_id} text={`${item.run_id} · ${item.research_case} · ${item.status}`} />)}
          </Select>
          {isSelectedRunLoaded && <div className="research-runs__summary"><Tag type={run.status === 'completed' ? 'green' : 'red'}>{run.status}</Tag><span>Run {run.run_id}</span><span>{run.created_at}</span><span>Corpus {run.corpus_version || 'unrecorded'}</span><span>{run.model?.name || 'Model not invoked'}</span><span>{run.assessment ? 'Assessment recorded' : 'Assessment pending'}</span><Tag type={run.output_sha256 ? 'blue' : 'gray'} size="sm">{run.output_sha256 ? `Output bound · ${evidenceHashCount}/${run.retrieved_evidence.length} evidence hashes` : 'Legacy run · no output binding'}</Tag></div>}
          {isSelectedRunLoaded && run.status === 'failed' && <InlineNotification lowContrast kind="warning" title={`Run failure: ${run.error_code || 'unclassified'}`} subtitle={failureDetail} />}
        </Tile>
      </Column>
      {!requestedRunId && !listLoading && <Column><Tile><p>Select a saved run to inspect it.</p></Tile></Column>}
      {requestedRunId && !isSelectedRunLoaded && detailState === 'loading' && <Column><Tile><p>Loading saved run...</p></Tile></Column>}
      {requestedRunId && detailState === 'error' && <Column><InlineNotification lowContrast kind="error" title="Saved run could not be loaded." subtitle="The requested persisted run is not available in the current research database." /></Column>}
      {isSelectedRunLoaded && <>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Research question and retrieval" description="Research prompt, PostgreSQL FTS query and ranking configuration." /><p className="research-runs__question">{run.prompt.question}</p><pre className="research-runs__config">{JSON.stringify(run.retrieval, null, 2)}</pre></Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Source evidence" description="Retained passages remain visible whether supplied to the recorded model or excluded by the deterministic budget." />{run.retrieved_evidence.map((item) => <div className="research-runs__evidence" key={item.chunk_id}><div className="research-runs__evidence-head"><div><Tag type={item.included_in_context ? 'green' : 'gray'}>{item.included_in_context ? item.excerpted ? 'supplied excerpt' : 'supplied' : 'retrieved, not supplied'}</Tag><strong> Rank {item.rank} · {item.chunk_id}</strong></div><Tag type={item.evidence_sha256 ? 'blue' : 'gray'} size="sm">{item.evidence_sha256 ? 'Bound' : 'Legacy'}</Tag></div><p>Document ID: {item.document_id} · Source PID: {item.pid} · Page: {item.page_start} · Score: {item.score}</p><p>{item.original_chars === null || item.original_chars === undefined ? 'Supplied length: unrecorded for this legacy run.' : `Supplied: ${item.supplied_chars || 0}/${item.original_chars} characters${item.exclusion_reason ? ` · ${item.exclusion_reason}` : ''}`}</p><p>{item.included_in_context ? item.supplied_excerpt || item.excerpt : item.excerpt}</p></div>)}</Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Archive and authority context" description="Catalogue/authority data is not source-document evidence." />{authority.requested || authority.used ? <pre className="research-runs__config">{JSON.stringify(authority, null, 2)}</pre> : <InlineNotification lowContrast kind="info" title="No authority context requested" subtitle="This run used document evidence only." />}</Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Generated analysis" description="Structured output separates evidence-derived claims, inference, contradiction, missingness and follow-up searches." /><p>{response.answer || run.raw_model_response || 'No generated response was retained.'}</p><h4>Evidence-derived claims</h4><pre className="research-runs__config">{JSON.stringify(response.evidence || [], null, 2)}</pre><h4>Parsed model response</h4><pre className="research-runs__config">{JSON.stringify(run.parsed_response || null, null, 2)}</pre><h4>Raw model response</h4><pre className="research-runs__config">{run.raw_model_response || 'No model response was retained.'}</pre><h4>Inference and contradiction</h4><pre className="research-runs__config">{JSON.stringify({ inferences: response.inferences || [], contradictions: response.contradictions || [] }, null, 2)}</pre></Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Scoped missingness" description="Missingness is limited to this query, supplied evidence and corpus; it is not a historical or archive-wide absence claim." /><pre className="research-runs__config">{JSON.stringify(response.missingness || [], null, 2)}</pre><h4>Follow-up searches</h4><pre className="research-runs__config">{JSON.stringify(response.follow_up_queries || [], null, 2)}</pre></Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Researcher assessment" description="Assessment is researcher-authored, mutable and separate from immutable experiment evidence." />{scoreFields.map(([key, label]) => <Select key={key} id={key} labelText={label} value={assessment[key]} onChange={(event) => updateAssessmentDraft(key, event.target.value)}><SelectItem value="" text="Not assessed" />{[0, 1, 2, 3].map((score) => <SelectItem key={score} value={String(score)} text={String(score)} />)}</Select>)}<TextInput id="failure-categories" labelText="Failure classifications" helperText="Comma-separated researcher classifications" value={assessment.failure_categories} onChange={(event) => updateAssessmentDraft('failure_categories', event.target.value)} /><TextArea id="assessment-notes" labelText="Qualitative notes" rows={4} value={assessment.notes} onChange={(event) => updateAssessmentDraft('notes', event.target.value)} /><TextArea id="authority-influence" labelText="Authority influence" rows={3} value={assessment.authority_influence_note} onChange={(event) => updateAssessmentDraft('authority_influence_note', event.target.value)} /><Button size="sm" renderIcon={Save} onClick={saveAssessment} disabled={!isAssessmentDirty || Boolean(savingAssessmentRunId)}>Save assessment</Button>{savedAssessmentRunIds[requestedRunId] && <span className="research-runs__saved">Saved</span>}{assessmentSaveErrorRunIds[requestedRunId] && <InlineNotification lowContrast kind="error" title="Assessment could not be saved." subtitle="Your local changes have not been lost." />}</Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Configuration and reproducibility" description="Run, corpus, prompt, context-builder, model and software identifiers." /><pre className="research-runs__config">{JSON.stringify({ run_id: run.run_id, corpus_version: run.corpus_version, prompt: run.prompt, context_budget: budget, authority_context: authority, model: run.model, generation_metadata: run.generation_metadata, repair_generation_metadata: run.repair_generation_metadata, response_schema: run.response_schema, git_commit: run.git_commit, provenance_validation: run.provenance_validation }, null, 2)}</pre><div className="app-actions-row"><Button kind="ghost" size="sm" renderIcon={Download} onClick={downloadJson}>Export raw JSON</Button><Button kind="ghost" size="sm" renderIcon={Download} onClick={downloadReport}>Open saved-run report</Button></div></Tile></Column>
      </>}
    </PageGrid>
  )
}

export default ResearchRuns
