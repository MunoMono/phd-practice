import { Button, InlineNotification, Select, SelectItem, Tag, TextArea, TextInput, Tile } from '@carbon/react'
import { Download, Notebook, Save } from '@carbon/icons-react'
import { useEffect, useState } from 'react'
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

const engineeringRecordNotes = {
  'experiment-886cbe24b464': 'Granite runtime timeout boundary. This legacy immutable record did not retain a detailed runtime message.',
}

const ResearchRuns = () => {
  const [runs, setRuns] = useState([])
  const [runId, setRunId] = useState('')
  const [run, setRun] = useState(null)
  const [assessment, setAssessment] = useState(blankAssessment())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saveState, setSaveState] = useState('idle')

  useEffect(() => {
    let cancelled = false
    listExperimentRuns()
      .then((payload) => {
        if (!cancelled) {
          const records = payload.experiment_runs || []
          setRuns(records)
          setRunId(records[0]?.run_id || '')
        }
      })
      .catch((requestError) => !cancelled && setError(requestError.message || 'Unable to load saved research runs.'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!runId) { setRun(null); return undefined }
    let cancelled = false
    getExperimentRun(runId)
      .then((payload) => {
        if (cancelled) return
        setRun(payload)
        const stored = payload.assessment || {}
        setAssessment({
          ...blankAssessment(), ...stored,
          failure_categories: (stored.failure_categories || []).join(', '),
        })
      })
      .catch((requestError) => !cancelled && setError(requestError.message || 'Unable to load the selected research run.'))
    return () => { cancelled = true }
  }, [runId])

  const downloadJson = async () => {
    try {
      const payload = await exportExperimentRunJson(runId)
      downloadFile(`${runId}.json`, `${JSON.stringify(payload, null, 2)}\n`, 'application/json;charset=utf-8')
    } catch (requestError) { setError(requestError.message || 'Unable to export JSON.') }
  }

  const downloadReport = () => {
    window.open(`/api/experiments/${runId}/report`, '_blank', 'noopener,noreferrer')
  }

  const saveAssessment = async () => {
    if (!run) return
    setSaveState('saving')
    try {
      const payload = {
        ...Object.fromEntries(scoreFields.map(([key]) => [key, assessment[key] === '' ? null : Number(assessment[key])])),
        failure_categories: assessment.failure_categories.split(',').map((item) => item.trim()).filter(Boolean),
        notes: assessment.notes || null,
        authority_influence_note: assessment.authority_influence_note || null,
      }
      const saved = await saveExperimentAssessment(run.run_id, payload)
      setRun((current) => ({ ...current, assessment: saved.assessment }))
      setSaveState('saved')
    } catch (requestError) {
      setSaveState('error')
      setError(requestError.message || 'Unable to save researcher assessment.')
    }
  }

  const response = run?.structured_response || {}
  const budget = run?.context?.budget || {}
  const authority = run?.authority_context || {}
  const failureDetail = run?.error_message || engineeringRecordNotes[run?.run_id] || 'No detailed failure message was retained in this immutable record.'

  return (
    <PageGrid className="research-runs">
      <Column>
        <PageHeader title="Research runs" description="Inspect immutable archival experiment evidence, generated analysis, scoped missingness, and separate researcher assessment." actions={<Tag type="teal" size="md"><Notebook size={16} /> Immutable run records</Tag>} />
      </Column>
      {error && <Column><InlineNotification lowContrast kind="error" title="Research runs unavailable" subtitle={error} /></Column>}
      <Column>
        <Tile>
          <PanelHeader title="Saved runs" description="Each record preserves its query, corpus, prompt, model and immutable evidence snapshot." />
          <Select id="saved-run" labelText="Saved experiment run" value={runId} onChange={(event) => setRunId(event.target.value)}>
            <SelectItem value="" text={loading ? 'Loading saved runs...' : 'No saved runs available'} />
            {runs.map((item) => <SelectItem key={item.run_id} value={item.run_id} text={`${item.run_id} · ${item.research_case} · ${item.status}`} />)}
          </Select>
          {run && <div className="research-runs__summary"><Tag type={run.status === 'completed' ? 'green' : 'red'}>{run.status}</Tag><span>{run.created_at}</span><span>Corpus: {run.corpus_version || 'unrecorded'}</span><span>Model: {run.model?.name || 'not invoked'}</span><span>Assessment: {run.assessment ? 'recorded' : 'not assessed'}</span></div>}
          {run?.status === 'failed' && <InlineNotification lowContrast kind="warning" title={`Run failure: ${run.error_code || 'unclassified'}`} subtitle={failureDetail} />}
        </Tile>
      </Column>
      {run && <>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Research question and retrieval" description="Research prompt, PostgreSQL FTS query and ranking configuration." /><p className="research-runs__question">{run.prompt.question}</p><pre className="research-runs__config">{JSON.stringify(run.retrieval, null, 2)}</pre></Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Source evidence" description="Retrieved passages remain visible whether supplied to Granite or excluded by the deterministic budget." />{run.retrieved_evidence.map((item) => <div className="research-runs__evidence" key={item.chunk_id}><div><Tag type={item.included_in_context ? 'green' : 'gray'}>{item.included_in_context ? item.excerpted ? 'supplied excerpt' : 'supplied' : 'retrieved, not supplied'}</Tag><strong> Rank {item.rank} · {item.chunk_id}</strong></div><p>Document: {item.document_id} · PID: {item.pid} · Page: {item.page_start} · Score: {item.score}</p><p>{item.original_chars === null || item.original_chars === undefined ? 'Supplied length: unrecorded for this legacy run.' : `Supplied: ${item.supplied_chars || 0}/${item.original_chars} characters${item.exclusion_reason ? ` · ${item.exclusion_reason}` : ''}`}</p><p>{item.included_in_context ? item.supplied_excerpt || item.excerpt : item.excerpt}</p></div>)}</Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Archive and authority context" description="Catalogue/authority data is not source-document evidence." />{authority.used ? <pre className="research-runs__config">{JSON.stringify(authority, null, 2)}</pre> : <InlineNotification lowContrast kind="info" title="No authority context supplied" subtitle="This run used document evidence only." />}</Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Generated analysis" description="Structured output separates evidence-derived claims, inference, contradiction, missingness and follow-up searches." /><p>{response.answer || run.raw_model_response || 'No generated response was retained.'}</p><h4>Evidence-derived claims</h4><pre className="research-runs__config">{JSON.stringify(response.evidence || [], null, 2)}</pre><h4>Inference and contradiction</h4><pre className="research-runs__config">{JSON.stringify({ inferences: response.inferences || [], contradictions: response.contradictions || [] }, null, 2)}</pre></Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Scoped missingness" description="Missingness is limited to this query, supplied evidence and corpus; it is not a historical or archive-wide absence claim." /><pre className="research-runs__config">{JSON.stringify(response.missingness || [], null, 2)}</pre><h4>Follow-up searches</h4><pre className="research-runs__config">{JSON.stringify(response.follow_up_queries || [], null, 2)}</pre></Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Researcher assessment" description="Assessment is researcher-authored, mutable and separate from immutable experiment evidence." />{scoreFields.map(([key, label]) => <Select key={key} id={key} labelText={label} value={assessment[key]} onChange={(event) => setAssessment((current) => ({ ...current, [key]: event.target.value }))}><SelectItem value="" text="Not assessed" />{[0, 1, 2, 3].map((score) => <SelectItem key={score} value={String(score)} text={String(score)} />)}</Select>)}<TextInput id="failure-categories" labelText="Failure classifications" helperText="Comma-separated researcher classifications" value={assessment.failure_categories} onChange={(event) => setAssessment((current) => ({ ...current, failure_categories: event.target.value }))} /><TextArea id="assessment-notes" labelText="Qualitative notes" rows={4} value={assessment.notes || ''} onChange={(event) => setAssessment((current) => ({ ...current, notes: event.target.value }))} /><TextArea id="authority-influence" labelText="Authority influence" rows={3} value={assessment.authority_influence_note || ''} onChange={(event) => setAssessment((current) => ({ ...current, authority_influence_note: event.target.value }))} /><Button size="sm" renderIcon={Save} onClick={saveAssessment} disabled={saveState === 'saving'}>Save assessment</Button>{saveState === 'saved' && <span className="research-runs__saved">Saved</span>}</Tile></Column>
        <Column lg={8} md={8} sm={4}><Tile><PanelHeader title="Configuration and reproducibility" description="Run, corpus, prompt, context-builder, model and software identifiers." /><pre className="research-runs__config">{JSON.stringify({ run_id: run.run_id, corpus_version: run.corpus_version, prompt: run.prompt, context_budget: budget, model: run.model, git_commit: run.git_commit, provenance_validation: run.provenance_validation }, null, 2)}</pre><div className="app-actions-row"><Button kind="ghost" size="sm" renderIcon={Download} onClick={downloadJson}>Export raw JSON</Button><Button kind="ghost" size="sm" renderIcon={Download} onClick={downloadReport}>Open saved-run report</Button></div></Tile></Column>
      </>}
    </PageGrid>
  )
}

export default ResearchRuns
