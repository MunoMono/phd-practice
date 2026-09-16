import {
  Button,
  DataTable,
  InlineNotification,
  Select,
  SelectItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextArea,
  Tile
} from '@carbon/react'
import { WarningAlt, Download } from '@carbon/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader'
import PanelHeader from '../../components/layout/PanelHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import { getMissingnessEvents, getMissingnessSummary, updateMissingnessEvent } from '../../api/missingness'
import { getResearchStateTag } from '../../utils/researchState'
import { downloadCsv } from '../../utils/workbenchExport'

const typologyOptions = ['all', 'documentary', 'descriptive', 'retrieval', 'institutional', 'historiographic', 'computational']
const statusOptions = ['open', 'reviewing', 'triaged', 'resolved']

const headers = [
  { key: 'event_id', header: 'Event' },
  { key: 'type', header: 'Type' },
  { key: 'query_id', header: 'Source run' },
  { key: 'query_or_entity_or_field', header: 'Query / entity / field' },
  { key: 'evidence', header: 'Evidence' },
  { key: 'source_document_id', header: 'Source document' },
  { key: 'source_chunk_id', header: 'Source chunk' },
  { key: 'status', header: 'Status' },
  { key: 'reviewer_note', header: 'Reviewer note' },
    { key: 'follow_up_action', header: 'Follow-up action' },
  { key: 'created_at', header: 'Created' }
]

const getEventIdFromTableRow = (row) => {
  return row.cells.find((cell) => cell.info.header === 'event_id')?.value || ''
}

const MissingnessWorkbench = () => {
  const [searchParams] = useSearchParams()
  const requestedEventId = searchParams.get('eventId') || ''
  const sourceDocumentId = searchParams.get('sourceDocumentId') || ''
  const sourceChunkId = searchParams.get('sourceChunkId') || ''
  const sourcePid = searchParams.get('pid') || ''
  const [filter, setFilter] = useState('all')
  const [summary, setSummary] = useState(null)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectionError, setSelectionError] = useState('')
  const [selectedEventId, setSelectedEventId] = useState('')
  const [typeDrafts, setTypeDrafts] = useState({})
  const [statusDrafts, setStatusDrafts] = useState({})
  const [reviewerNoteDrafts, setReviewerNoteDrafts] = useState({})
  const [followUpActionDrafts, setFollowUpActionDrafts] = useState({})
  const [savingEventId, setSavingEventId] = useState('')
  const [savedEventId, setSavedEventId] = useState('')
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    let isCancelled = false

    const loadMissingness = async () => {
      setLoading(true)
      setError('')

      try {
        const [summaryPayload, eventsPayload] = await Promise.all([
          getMissingnessSummary(),
          getMissingnessEvents({
            ...(filter === 'all' ? {} : { type: filter }),
            ...(sourceDocumentId ? { source_document_id: sourceDocumentId } : {})
          })
        ])

        if (isCancelled) {
          return
        }

        setSummary(summaryPayload)
        const loadedEvents = eventsPayload.events || []
        setEvents(loadedEvents)
        setSelectedEventId((current) => {
          if (current) {
            return loadedEvents.some((event) => event.event_id === current) ? current : ''
          }

          if (requestedEventId) {
            const requestedEventExists = loadedEvents.some((event) => event.event_id === requestedEventId)
            setSelectionError(requestedEventExists ? '' : 'Requested missingness event could not be loaded.')
            return requestedEventExists ? requestedEventId : ''
          }

          setSelectionError('')
          return ''
        })
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError.message || 'Failed to load persisted missingness data.')
          setSummary(null)
          setEvents([])
          setSelectedEventId('')
          setSelectionError('')
        }
      } finally {
        if (!isCancelled) {
          setLoading(false)
        }
      }
    }

    loadMissingness()

    return () => {
      isCancelled = true
    }
  }, [filter, requestedEventId, sourceDocumentId])

  const rows = useMemo(() => {
    return events.map((event) => ({ id: event.event_id, ...event }))
  }, [events])

  const selectedEvent = useMemo(
    () => events.find((event) => event.event_id === selectedEventId) || null,
    [events, selectedEventId]
  )

  const draftType = selectedEvent
    ? (Object.hasOwn(typeDrafts, selectedEvent.event_id)
        ? typeDrafts[selectedEvent.event_id]
        : selectedEvent.type)
    : 'retrieval'

  const draftStatus = selectedEvent
    ? (Object.hasOwn(statusDrafts, selectedEvent.event_id)
        ? statusDrafts[selectedEvent.event_id]
        : selectedEvent.status || 'open')
    : 'open'

  const draftReviewerNote = selectedEvent
    ? (Object.hasOwn(reviewerNoteDrafts, selectedEvent.event_id)
        ? reviewerNoteDrafts[selectedEvent.event_id]
        : selectedEvent.reviewer_note || '')
    : ''

  const draftFollowUpAction = selectedEvent
    ? (Object.hasOwn(followUpActionDrafts, selectedEvent.event_id)
        ? followUpActionDrafts[selectedEvent.event_id]
        : selectedEvent.follow_up_action || '')
    : ''

  const isReviewDirty = Boolean(selectedEvent) && (
    draftType !== selectedEvent.type
    || draftStatus !== (selectedEvent.status || 'open')
    || draftReviewerNote !== (selectedEvent.reviewer_note || '')
    || draftFollowUpAction !== (selectedEvent.follow_up_action || '')
  )

  const exportRows = rows.map((row) => ({
    event_id: row.event_id,
    type: row.type,
    query_id: row.query_id,
    query_or_entity_or_field: row.query_or_entity_or_field,
    evidence: row.evidence,
    source_document_id: row.source_document_id,
    source_chunk_id: row.source_chunk_id,
    source_document_ids: row.source_document_ids?.join(', ') || '',
    source_chunk_ids: row.source_chunk_ids?.join(', ') || '',
    status: row.status,
    reviewer_note: row.reviewer_note,
    follow_up_action: row.follow_up_action,
    created_at: row.created_at
  }))

  const negativeRetrievalLog = useMemo(() => {
    return events
      .filter((event) => event.type === 'retrieval')
      .map((event) => ({
        id: event.event_id,
        query: event.query_or_entity_or_field,
        outcome: event.status === 'resolved' ? 'Resolved retrieval issue' : 'Retrieval issue under review',
        note: event.evidence
      }))
  }, [events])

  const handleSaveEvent = async () => {
    if (!selectedEvent || !isReviewDirty || savingEventId) {
      return
    }

    const saveTargetEventId = selectedEvent.event_id
    const savePayload = {
      type: draftType,
      status: draftStatus,
      reviewer_note: draftReviewerNote,
      follow_up_action: draftFollowUpAction
    }

    setSavingEventId(saveTargetEventId)
    setSavedEventId('')
    setSaveError('')
    try {
      const updated = await updateMissingnessEvent(saveTargetEventId, savePayload)
      if (updated.event_id !== saveTargetEventId) {
        throw new Error('The saved review response did not match the selected event.')
      }

      setEvents((current) => current.map((event) => event.event_id === saveTargetEventId ? updated : event))
      setTypeDrafts((current) => {
        const { [saveTargetEventId]: _savedDraft, ...remaining } = current
        return remaining
      })
      setStatusDrafts((current) => {
        const { [saveTargetEventId]: _savedDraft, ...remaining } = current
        return remaining
      })
      setReviewerNoteDrafts((current) => {
        const { [saveTargetEventId]: _savedDraft, ...remaining } = current
        return remaining
      })
      setFollowUpActionDrafts((current) => {
        const { [saveTargetEventId]: _savedDraft, ...remaining } = current
        return remaining
      })
      setSavedEventId(saveTargetEventId)
    } catch (saveError) {
      setSaveError('Review state could not be saved. Your local changes have not been lost.')
    }
    setSavingEventId('')
  }

  return (
    <PageGrid className="missingness-workbench">
      <Column>
        <PageHeader
          title="Absences"
          description="Make scoped retrieval, metadata, registry, access, and description conditions available as analytical evidence."
          actions={(
            <Tag type="magenta" size="md">
              <WarningAlt size={16} /> Analytical gaps visible
            </Tag>
          )}
        />
      </Column>

      <Column>
        <InlineNotification
          lowContrast
          kind="info"
          title="Analytical output"
          subtitle="This view reports scoped missingness in the current corpus, metadata, and retrieval system. It records explicit events, typology assignments, reviewer notes, and exportable evidence; it is not proof of historical absence."
        />
      </Column>

      {error && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Absences unavailable" subtitle={error} />
        </Column>
      )}

      {selectionError && (
        <Column>
          <InlineNotification lowContrast kind="warning" title="Missingness event unavailable" subtitle={selectionError} />
        </Column>
      )}

      {(sourceDocumentId || sourceChunkId || sourcePid) && (
        <Column>
          <InlineNotification
            lowContrast
            kind="info"
            title="Atlas source context"
            subtitle={`Viewing scoped events for ${sourceDocumentId || 'a source without a document identifier'}${sourceChunkId ? `, chunk ${sourceChunkId}` : ''}${sourcePid ? `, PID ${sourcePid}` : ''}. This context records a technical or evidential limit; it is not proof of historical absence.`}
          />
        </Column>
      )}

      {saveError && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Review state could not be saved" subtitle="Your local changes have not been lost." />
        </Column>
      )}

      <Column>
        <Tile>
          <PanelHeader
            title="Scoped coverage and missingness diagnostics"
            description="Summary cards show global system state. Typology filters apply to the event log and events table below."
          />
        </Tile>
      </Column>

      <Column>
        <Tile>
          <PanelHeader
            title="Typology filter and export"
            description="Filter missingness by documentary, descriptive, retrieval, institutional, historiographic, or computational type."
            actions={<Button kind="ghost" size="sm" renderIcon={Download} onClick={() => downloadCsv('absences-missingness-report.csv', exportRows)}>Export absences / missingness report</Button>}
          />
          <div className="app-card-grid app-card-grid--responsive">
            <Select id="missingness-filter" labelText="Typology" value={filter} onChange={(event) => setFilter(event.target.value)}>
              {typologyOptions.map((option) => (
                <SelectItem key={option} value={option} text={option === 'all' ? 'All types' : option} />
              ))}
            </Select>
            <div>
              <strong>Reviewer workflow</strong>
              <p className="app-text-muted missingness-workbench__review-note">Use status and reviewer note fields to distinguish scoped system conditions from ingestion, retrieval, or description limits.</p>
            </div>
          </div>
        </Tile>
      </Column>

      {(summary?.completeness_cards || []).map((card) => (
        <Column key={card.label} lg={5} xlg={5} max={5} md={4} sm={4}>
          <Tile className="missingness-workbench__completeness-card">
            <h3 className="missingness-workbench__stat-title">{card.label}</h3>
            <p className="missingness-workbench__stat-value">{card.value}</p>
            <p className="app-copy-reset">{card.note}</p>
          </Tile>
        </Column>
      ))}

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader title="Negative retrieval log" description="Queries that returned no result, weak context, or unresolved retrieval evidence. Absence here is analytic evidence, not automatic historical proof." />
          <div className="app-card-grid app-card-grid--dense">
            {negativeRetrievalLog.length > 0 ? negativeRetrievalLog.map((entry) => (
              <div key={entry.id} className="app-list-item">
                <strong className="app-list-item__title">{entry.query}</strong>
                {getResearchStateTag(events.find((event) => event.event_id === entry.id)) ? <Tag type={getResearchStateTag(events.find((event) => event.event_id === entry.id)).type} size="sm">{getResearchStateTag(events.find((event) => event.event_id === entry.id)).label}</Tag> : null}
                {events.find((event) => event.event_id === entry.id)?.query_id && !getResearchStateTag(events.find((event) => event.event_id === entry.id)) ? <Tag type="blue" size="sm">Source interrogation</Tag> : null}
                <p className="app-list-item__body">{entry.outcome}</p>
                <p className="app-list-item__note">{entry.note}</p>
              </div>
            )) : <p className="app-copy-reset">{loading ? 'Loading retrieval issues...' : 'No persisted retrieval missingness events yet.'}</p>}
          </div>
        </Tile>
      </Column>

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader title="Selected event review" description="Persist reviewer status and notes for the selected missingness event." />
          {selectedEvent ? (
            <>
              {getResearchStateTag(selectedEvent) ? <Tag type={getResearchStateTag(selectedEvent).type}>{getResearchStateTag(selectedEvent).label}</Tag> : null}
              {selectedEvent.query_id && !getResearchStateTag(selectedEvent) ? <Tag type="blue">Source interrogation</Tag> : null}
              <p className="app-list-item__meta">Event ID: {selectedEvent.event_id}</p>
              <p className="app-list-item__meta">Typology: {selectedEvent.type}</p>
              <p><strong>{selectedEvent.query_or_entity_or_field}</strong></p>
              {selectedEvent.query_id && <p className="app-list-item__meta">Source run: {selectedEvent.query_id}</p>}
              {selectedEvent.source_document_id && <p className="app-list-item__meta">Source document: {selectedEvent.source_document_id}</p>}
              {selectedEvent.source_chunk_id && <p className="app-list-item__meta">Source chunk: {selectedEvent.source_chunk_id}</p>}
                            {selectedEvent.source_document_ids?.length > 1 && <p className="app-list-item__meta">All source documents: {selectedEvent.source_document_ids.join(', ')}</p>}
                            {selectedEvent.source_chunk_ids?.length > 1 && <p className="app-list-item__meta">All source chunks: {selectedEvent.source_chunk_ids.join(', ')}</p>}
              {selectedEvent.created_at && <p className="app-list-item__meta">Created: {selectedEvent.created_at}</p>}
              <p className="app-text-muted">{selectedEvent.evidence}</p>
              <Select
                id="selected-missingness-type"
                labelText="Analytical typology"
                helperText="Classify the condition under review; this does not change the underlying evidence."
                value={draftType}
                onChange={(event) => setTypeDrafts((current) => ({
                  ...current,
                  [selectedEvent.event_id]: event.target.value
                }))}
              >
                {typologyOptions.filter((option) => option !== 'all').map((option) => (
                  <SelectItem key={option} value={option} text={option} />
                ))}
              </Select>
              <Select
                id="selected-missingness-status"
                labelText="Researcher review status"
                helperText="Workflow state only; resolved means the review condition is resolved."
                value={draftStatus}
                onChange={(event) => setStatusDrafts((current) => ({
                  ...current,
                  [selectedEvent.event_id]: event.target.value
                }))}
              >
                {statusOptions.map((option) => (
                  <SelectItem key={option} value={option} text={option} />
                ))}
              </Select>
              <TextArea
                id="selected-missingness-reviewer-note"
                labelText="Researcher review note - changes remain local until saved"
                rows={5}
                value={draftReviewerNote}
                onChange={(event) => setReviewerNoteDrafts((current) => ({
                  ...current,
                  [selectedEvent.event_id]: event.target.value
                }))}
              />
              <TextArea
                id="selected-missingness-follow-up-action"
                labelText="Follow-up action - changes remain local until saved"
                rows={4}
                value={draftFollowUpAction}
                onChange={(event) => setFollowUpActionDrafts((current) => ({
                  ...current,
                  [selectedEvent.event_id]: event.target.value
                }))}
              />
              <div className="app-actions-row app-actions-row--comfortable missingness-workbench__detail-actions">
                <Button size="sm" onClick={handleSaveEvent} disabled={!isReviewDirty || Boolean(savingEventId)}>Save review state</Button>
                {savedEventId === selectedEvent.event_id && <span>Saved</span>}
              </div>
            </>
          ) : (
            <p className="app-copy-reset">{loading ? 'Loading events...' : 'Select a missingness event from the table to review it.'}</p>
          )}
        </Tile>
      </Column>

      <Column lg={10} md={8} sm={4}>
        {!loading && events.length === 0 ? (
          <Tile>
            <PanelHeader title="Missingness events table" />
            <p className="app-copy-reset">No missingness events are recorded for this typology.</p>
          </Tile>
        ) : (
          <DataTable rows={rows} headers={headers}>
          {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Missingness events table">
              <Table {...getTableProps()}>
                <TableHead>
                  <TableRow>
                    {headers.map((header) => {
                      const { key, ...headerProps } = getHeaderProps({ header })
                      return (
                        <TableHeader key={key || header.key} {...headerProps}>
                          {header.header}
                        </TableHeader>
                      )
                    })}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => {
                    const { key, ...rowProps } = getRowProps({ row })
                    const eventId = getEventIdFromTableRow(row)
                    return (
                      <TableRow
                        key={key || row.id}
                        {...rowProps}
                        onClick={() => {
                          setSelectionError('')
                          setSelectedEventId(eventId)
                        }}
                        className={eventId === selectedEventId ? 'app-table-row--interactive app-table-row--selected' : 'app-table-row--interactive'}
                      >
                        {row.cells.map((cell) => {
                          if (cell.info.header === 'event_id') {
                            const event = events.find((item) => item.event_id === eventId)
                            const stateTag = getResearchStateTag(event)

                            return (
                              <TableCell key={cell.id}>
                                <div className="app-tag-row">
                                  <span>{cell.value}</span>
                                  {stateTag ? <Tag type={stateTag.type} size="sm">{stateTag.label}</Tag> : null}
                                  {event?.query_id && !stateTag ? <Tag type="blue" size="sm">Source interrogation</Tag> : null}
                                </div>
                              </TableCell>
                            )
                          }

                          return <TableCell key={cell.id}>{cell.value}</TableCell>
                        })}
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
          </DataTable>
        )}
      </Column>
    </PageGrid>
  )
}

export default MissingnessWorkbench
