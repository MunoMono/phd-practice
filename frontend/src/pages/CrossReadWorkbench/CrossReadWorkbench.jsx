import {
  Button,
  InlineLoading,
  InlineNotification,
  Select,
  SelectItem,
  Tag,
  TextArea,
  TextInput,
  Tile
} from '@carbon/react'
import { ArrowsHorizontal, Download } from '@carbon/icons-react'
import { useEffect, useMemo, useState } from 'react'
import {
  createCrossReadPassage,
  exportCrossReadCsv,
  exportCrossReadMarkdown,
  getCrossReadPassage,
  getCrossReadPassages,
  runCrossReadPassage,
  updateCrossReadMapping,
  updateCrossReadPassage
} from '../../api/crossRead'
import PageHeader from '../../components/layout/PageHeader'
import PanelHeader from '../../components/layout/PanelHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import { downloadFile } from '../../utils/workbenchExport'
import { getResearchStateTag } from '../../utils/researchState'

const relationOptions = ['supports', 'complicates', 'contradicts', 'no-documentary-trace']
const sourceTypeOptions = ['oral_history', 'interview', 'field_note', 'researcher_note', 'mock_dev']
const statusOptions = ['draft', 'reviewing', 'mapped', 'unresolved']

const createEmptyPassageForm = () => ({
  passage_text: '',
  speaker_or_source: '',
  passage_label: '',
  source_type: 'researcher_note',
  memory_position_note: '',
  status: 'draft'
})

const createEmptyMappingForm = () => ({
  relation_type: relationOptions[1],
  reviewer_note: '',
  confidence_or_status: 'reviewing'
})

const CrossReadWorkbench = () => {
  const [passages, setPassages] = useState([])
  const [selectedPassageId, setSelectedPassageId] = useState('')
  const [selectedPassage, setSelectedPassage] = useState(null)
  const [selectedMappingId, setSelectedMappingId] = useState('')
  const [passageForm, setPassageForm] = useState(createEmptyPassageForm())
  const [mappingForm, setMappingForm] = useState(createEmptyMappingForm())
  const [loading, setLoading] = useState(true)
  const [savingPassage, setSavingPassage] = useState(false)
  const [runningProbe, setRunningProbe] = useState(false)
  const [savingMapping, setSavingMapping] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [queryRunNotice, setQueryRunNotice] = useState('')

  useEffect(() => {
    let isCancelled = false

    const loadPassages = async () => {
      setLoading(true)
      setError('')

      try {
        const payload = await getCrossReadPassages()
        if (isCancelled) {
          return
        }

        const nextPassages = payload.passages || []
        setPassages(nextPassages)
        setSelectedPassageId((current) => current || nextPassages[0]?.passage_id || '')
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError.message || 'Failed to load cross-read passages.')
          setPassages([])
        }
      } finally {
        if (!isCancelled) {
          setLoading(false)
        }
      }
    }

    loadPassages()

    return () => {
      isCancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedPassageId) {
      setSelectedPassage(null)
      setSelectedMappingId('')
      setPassageForm(createEmptyPassageForm())
      setMappingForm(createEmptyMappingForm())
      return
    }

    let isCancelled = false

    const loadPassageDetail = async () => {
      try {
        const payload = await getCrossReadPassage(selectedPassageId)
        if (isCancelled) {
          return
        }

        setSelectedPassage(payload)
        setPassageForm({
          passage_text: payload.passage_text || '',
          speaker_or_source: payload.speaker_or_source || '',
          passage_label: payload.passage_label || '',
          source_type: payload.source_type || 'researcher_note',
          memory_position_note: payload.memory_position_note || '',
          status: payload.status || 'draft'
        })

        const firstMapping = payload.mappings?.[0] || null
        setSelectedMappingId((current) => current || firstMapping?.mapping_id || '')
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError.message || 'Failed to load cross-read passage detail.')
          setSelectedPassage(null)
        }
      }
    }

    loadPassageDetail()

    return () => {
      isCancelled = true
    }
  }, [selectedPassageId])

  const selectedMapping = useMemo(
    () => selectedPassage?.mappings?.find((mapping) => mapping.mapping_id === selectedMappingId) || selectedPassage?.mappings?.[0] || null,
    [selectedMappingId, selectedPassage]
  )

  useEffect(() => {
    if (!selectedMapping) {
      setMappingForm(createEmptyMappingForm())
      return
    }

    setSelectedMappingId(selectedMapping.mapping_id)
    setMappingForm({
      relation_type: selectedMapping.relation_type === 'no_documentary_trace' ? 'no-documentary-trace' : selectedMapping.relation_type,
      reviewer_note: selectedMapping.reviewer_note || '',
      confidence_or_status: selectedMapping.confidence_or_status || 'reviewing'
    })
  }, [selectedMapping])

  const candidateMappings = selectedPassage?.mappings || []

  const refreshPassageList = async (preferredPassageId) => {
    const payload = await getCrossReadPassages()
    const nextPassages = payload.passages || []
    setPassages(nextPassages)
    setSelectedPassageId(preferredPassageId || nextPassages[0]?.passage_id || '')
  }

  const handleCreatePassage = async () => {
    if (!passageForm.passage_text.trim()) {
      setError('Passage text is required before creating a passage.')
      return
    }

    setSavingPassage(true)
    setError('')
    setNotice('')

    try {
      const payload = await createCrossReadPassage({
        passage_text: passageForm.passage_text,
        speaker_or_source: passageForm.speaker_or_source || null,
        passage_label: passageForm.passage_label || null,
        source_type: passageForm.source_type,
        memory_position_note: passageForm.memory_position_note || null,
        status: passageForm.status
      })
      await refreshPassageList(payload.passage_id)
      setNotice(`Passage ${payload.passage_id} created.`)
    } catch (saveError) {
      setError(saveError.message || 'Failed to create cross-read passage.')
    } finally {
      setSavingPassage(false)
    }
  }

  const handleSavePassage = async () => {
    if (!selectedPassageId) {
      return
    }

    setSavingPassage(true)
    setError('')
    setNotice('')

    try {
      const payload = await updateCrossReadPassage(selectedPassageId, {
        passage_text: passageForm.passage_text,
        speaker_or_source: passageForm.speaker_or_source || null,
        passage_label: passageForm.passage_label || null,
        memory_position_note: passageForm.memory_position_note || null,
        status: passageForm.status
      })
      setSelectedPassage(payload)
      setPassages((current) => current.map((passage) => passage.passage_id === payload.passage_id ? { ...passage, ...payload } : passage))
      setNotice(`Passage ${payload.passage_id} updated.`)
    } catch (saveError) {
      setError(saveError.message || 'Failed to update cross-read passage.')
    } finally {
      setSavingPassage(false)
    }
  }

  const handleRunProbe = async () => {
    if (!selectedPassageId) {
      return
    }

    setRunningProbe(true)
    setError('')
    setNotice('')
    setQueryRunNotice('')

    try {
      const payload = await runCrossReadPassage(selectedPassageId)
      setSelectedPassage(payload.passage)
      setSelectedMappingId(payload.passage.mappings?.[0]?.mapping_id || '')
      setQueryRunNotice(`Retrieval probe persisted as ${payload.query_run.query_id}.`)
      setPassages((current) => current.map((passage) => passage.passage_id === payload.passage.passage_id ? { ...passage, ...payload.passage } : passage))
    } catch (runError) {
      setError(runError.message || 'Failed to run passage as retrieval probe.')
    } finally {
      setRunningProbe(false)
    }
  }

  const handleSaveMapping = async () => {
    if (!selectedMapping?.mapping_id) {
      return
    }

    setSavingMapping(true)
    setError('')
    setNotice('')

    try {
      const payload = await updateCrossReadMapping(selectedMapping.mapping_id, {
        relation_type: mappingForm.relation_type.replace(/-/g, '_'),
        reviewer_note: mappingForm.reviewer_note || null,
        confidence_or_status: mappingForm.confidence_or_status || null
      })
      setSelectedPassage((current) => current ? {
        ...current,
        mappings: current.mappings.map((mapping) => mapping.mapping_id === payload.mapping_id ? payload : mapping)
      } : current)
      setNotice(`Mapping ${payload.mapping_id} updated.`)
    } catch (saveError) {
      setError(saveError.message || 'Failed to update testimony-record mapping.')
    } finally {
      setSavingMapping(false)
    }
  }

  const handleExportCsv = async () => {
    try {
      const content = await exportCrossReadCsv()
      downloadFile('testimony-record-map.csv', content, 'text/csv;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export testimony-record CSV.')
    }
  }

  const handleExportMarkdown = async () => {
    try {
      const content = await exportCrossReadMarkdown()
      downloadFile('testimony-record-map.md', content, 'text/markdown;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export testimony-record Markdown.')
    }
  }

  return (
    <PageGrid className="cross-read-workbench">
      <Column>
        <PageHeader
          title="Cross-readings"
          description="Use testimony and interpretive passages as probes against archival records, then annotate convergence, contradiction, complication, or no trace."
          actions={(
            <Tag type="cyan" size="md">
              <ArrowsHorizontal size={16} /> Testimony to record mapping
            </Tag>
          )}
        />
      </Column>

      <Column>
        <Tile>
          <PanelHeader
            title="Analytical output"
            description="This view produces a testimony-record map with explicit relation annotations, interpretive notes, and exportable candidate chunk links."
            actions={(
              <div className="app-actions-row">
                <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportCsv}>Export testimony-record CSV</Button>
                <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportMarkdown}>Export testimony-record Markdown</Button>
              </div>
            )}
          />
        </Tile>
      </Column>

      <Column>
        <InlineNotification
          lowContrast
          kind="warning"
          title="Situated testimony"
          subtitle="Testimony is treated as situated recollection, not transparent fact. A passage probes the archive; it does not automatically become evidence."
        />
      </Column>

      {error && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Cross-readings unavailable" subtitle={error} />
        </Column>
      )}

      {notice && (
        <Column>
          <InlineNotification lowContrast kind="success" title="Cross-reading updated" subtitle={notice} />
        </Column>
      )}

      {queryRunNotice && (
        <Column>
          <InlineNotification lowContrast kind="info" title="Retrieval probe persisted" subtitle={queryRunNotice} />
        </Column>
      )}

      <Column lg={5} md={4} sm={4}>
        <Tile>
          <PanelHeader title="Passage input or list" description="Start from a persisted testimony passage or draft a new interpretive probe text." />
          <Select id="cross-read-passage" labelText="Passage list" value={selectedPassageId} onChange={(event) => setSelectedPassageId(event.target.value)}>
            <SelectItem value="" text={loading ? 'Loading passages...' : passages.length > 0 ? 'Select a passage' : 'No persisted testimony passages are available yet'} />
            {passages.map((passage) => (
              <SelectItem key={passage.passage_id} value={passage.passage_id} text={`${passage.speaker_or_source || 'Unlabelled source'} (${passage.passage_id})`} />
            ))}
          </Select>
          {!loading && passages.length === 0 ? <InlineNotification lowContrast kind="info" title="No passages yet" subtitle="No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested." /> : null}
          <TextInput
            id="cross-read-passage-label"
            labelText="Passage label"
            value={passageForm.passage_label}
            onChange={(event) => setPassageForm((current) => ({ ...current, passage_label: event.target.value }))}
          />
          <TextArea
            id="cross-read-passage-text"
            labelText="Passage text"
            rows={8}
            value={passageForm.passage_text}
            onChange={(event) => setPassageForm((current) => ({ ...current, passage_text: event.target.value }))}
          />
          <TextInput
            id="cross-read-source"
            labelText="Speaker or source"
            value={passageForm.speaker_or_source}
            onChange={(event) => setPassageForm((current) => ({ ...current, speaker_or_source: event.target.value }))}
          />
          <Select id="cross-read-source-type" labelText="Source type" value={passageForm.source_type} onChange={(event) => setPassageForm((current) => ({ ...current, source_type: event.target.value }))}>
            {sourceTypeOptions.map((option) => (
              <SelectItem key={option} value={option} text={option} />
            ))}
          </Select>
          <Select id="cross-read-status" labelText="Status" value={passageForm.status} onChange={(event) => setPassageForm((current) => ({ ...current, status: event.target.value }))}>
            {statusOptions.map((option) => (
              <SelectItem key={option} value={option} text={option} />
            ))}
          </Select>
          <TextArea
            id="cross-read-passage-memory-position"
            labelText="Memory-position note"
            rows={4}
            value={passageForm.memory_position_note}
            onChange={(event) => setPassageForm((current) => ({ ...current, memory_position_note: event.target.value }))}
          />
          <div className="app-actions-row app-actions-row--comfortable cross-read-workbench__action-group">
            <Button size="sm" onClick={handleCreatePassage} disabled={savingPassage || !passageForm.passage_text.trim()}>
              Create passage
            </Button>
            <Button kind="secondary" size="sm" onClick={handleSavePassage} disabled={!selectedPassageId || savingPassage}>
              Save passage
            </Button>
            <Button kind="ghost" size="sm" onClick={handleRunProbe} disabled={!selectedPassageId || runningProbe}>
              Run passage as retrieval probe
            </Button>
            {(savingPassage || runningProbe || loading) && (
              <InlineLoading description={runningProbe ? 'Running testimony-archive probe...' : 'Saving passage...'} status="active" />
            )}
          </div>
        </Tile>
      </Column>

      <Column lg={5} md={4} sm={4}>
        <Tile>
          <PanelHeader title="Passage-to-record retrieval results" description="Candidate archival chunks surfaced by the current testimony or interpretive probe." />
          <div className="app-card-grid app-card-grid--dense">
            {candidateMappings.length > 0 ? candidateMappings.map((mapping) => {
              const metadata = mapping.source_metadata_json || {}
              const title = metadata.title || (mapping.relation_type === 'no_documentary_trace' ? 'No documentary trace' : 'Archival record candidate')
              const excerpt = metadata.excerpt || (mapping.relation_type === 'no_documentary_trace'
                ? 'This passage retrieval probe did not return supporting archival chunks.'
                : 'No excerpt stored for this mapping.')

              return (
                <div
                  key={mapping.mapping_id}
                  onClick={() => setSelectedMappingId(mapping.mapping_id)}
                  className={mapping.mapping_id === selectedMappingId ? 'app-list-item app-list-item--interactive app-list-item--selected' : 'app-list-item app-list-item--interactive'}
                >
                  <strong className="app-list-item__title cross-read-workbench__mapping-title">{title}</strong>
                  {getResearchStateTag({ ...mapping, ...metadata }) ? <Tag type={getResearchStateTag({ ...mapping, ...metadata }).type} size="sm">{getResearchStateTag({ ...mapping, ...metadata }).label}</Tag> : null}
                  <p className="app-list-item__body">{excerpt}</p>
                  <div className="app-tag-row">
                    <Tag type="blue">{metadata.pid || 'PID unavailable'}</Tag>
                    <Tag type="gray">{mapping.chunk_id || 'No chunk returned'}</Tag>
                    <Tag type="purple">{mapping.relation_type === 'no_documentary_trace' ? 'no-documentary-trace' : mapping.relation_type}</Tag>
                  </div>
                  <p className="app-list-item__note">
                    Query run: {mapping.query_id || 'Unavailable'}
                  </p>
                </div>
              )
            }) : <p className="app-copy-reset">{loading ? 'Loading persisted mappings...' : 'No persisted testimony-record mappings are available yet. Run the selected passage as a retrieval probe.'}</p>}
          </div>
        </Tile>
      </Column>

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader title="Relation annotation controls" description="Record how the archival result relates to the testimony or interpretive passage." />
          <Select id="cross-read-relation" labelText="Relation type" value={mappingForm.relation_type} onChange={(event) => setMappingForm((current) => ({ ...current, relation_type: event.target.value }))}>
            {relationOptions.map((option) => (
              <SelectItem key={option} value={option} text={option} />
            ))}
          </Select>
          <TextInput
            id="cross-read-confidence-status"
            labelText="Confidence / status"
            value={mappingForm.confidence_or_status}
            onChange={(event) => setMappingForm((current) => ({ ...current, confidence_or_status: event.target.value }))}
          />
          <TextArea
            id="cross-read-memory-position"
            labelText="Reviewer / interpretive note"
            rows={6}
            value={mappingForm.reviewer_note}
            onChange={(event) => setMappingForm((current) => ({ ...current, reviewer_note: event.target.value }))}
            placeholder="Record how this passage sits in testimony, interpretation, contradiction, or documentary absence."
          />
          <div className="app-tag-row cross-read-workbench__action-group">
            {getResearchStateTag(selectedPassage) ? <Tag type={getResearchStateTag(selectedPassage).type}>{getResearchStateTag(selectedPassage).label}</Tag> : null}
            <Tag type="green">Passage status: {selectedPassage?.status || 'draft'}</Tag>
            <Tag type="purple">Candidate mappings: {candidateMappings.length}</Tag>
            {selectedMapping?.query_id && <Tag type="cyan">Run: {selectedMapping.query_id}</Tag>}
          </div>
          <div className="app-actions-row app-actions-row--comfortable cross-read-workbench__action-group">
            <Button size="sm" onClick={handleSaveMapping} disabled={!selectedMapping?.mapping_id || savingMapping}>Save mapping annotation</Button>
            {selectedMapping?.citation_text && <Tag type="gray">Citation stored</Tag>}
            {selectedMapping?.provenance_json ? <Tag type="green">Provenance stored</Tag> : <Tag type="gray">Provenance unavailable</Tag>}
          </div>
        </Tile>
      </Column>
    </PageGrid>
  )
}

export default CrossReadWorkbench
