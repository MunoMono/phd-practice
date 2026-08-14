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
import './MissingnessWorkbench.scss'

const typologyOptions = ['all', 'documentary', 'descriptive', 'retrieval', 'institutional', 'historiographic', 'computational']
const statusOptions = ['open', 'reviewing', 'triaged', 'resolved']

const headers = [
  { key: 'event_id', header: 'Event' },
  { key: 'type', header: 'Type' },
  { key: 'query_id', header: 'Source run' },
  { key: 'query_or_entity_or_field', header: 'Query / entity / field' },
  { key: 'evidence', header: 'Evidence' },
  { key: 'source_document_id', header: 'Source document' },
  { key: 'status', header: 'Status' },
  { key: 'reviewer_note', header: 'Reviewer note' },
  { key: 'created_at', header: 'Created' }
]

const MissingnessWorkbench = () => {
  const [searchParams] = useSearchParams()
  const [filter, setFilter] = useState('all')
  const [summary, setSummary] = useState(null)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [saveState, setSaveState] = useState('idle')
  const [error, setError] = useState('')
  const [selectedEventId, setSelectedEventId] = useState('')
  const [draftStatus, setDraftStatus] = useState('open')
  const [draftReviewerNote, setDraftReviewerNote] = useState('')

  useEffect(() => {
    let isCancelled = false
    const seededEventId = searchParams.get('eventId') || ''

    const loadMissingness = async () => {
      setLoading(true)
      setError('')

      try {
        const [summaryPayload, eventsPayload] = await Promise.all([
          getMissingnessSummary(),
          getMissingnessEvents(filter === 'all' ? {} : { type: filter })
        ])

        if (isCancelled) {
          return
        }

        setSummary(summaryPayload)
        setEvents(eventsPayload.events || [])
        setSelectedEventId((current) => current || seededEventId || eventsPayload.events?.[0]?.event_id || '')
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError.message || 'Failed to load persisted missingness data.')
          setSummary(null)
          setEvents([])
          setSelectedEventId('')
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
  }, [filter, searchParams])

  const rows = useMemo(() => {
    return events.map((event) => ({ id: event.event_id, ...event }))
  }, [events])

  const selectedEvent = useMemo(
    () => events.find((event) => event.event_id === selectedEventId) || null,
    [events, selectedEventId]
  )

  useEffect(() => {
    if (!selectedEvent) {
      setDraftStatus('open')
      setDraftReviewerNote('')
      return
    }

    setDraftStatus(selectedEvent.status)
    setDraftReviewerNote(selectedEvent.reviewer_note || '')
  }, [selectedEvent])

  const exportRows = rows.map((row) => ({
    event_id: row.event_id,
    type: row.type,
    query_id: row.query_id,
    query_or_entity_or_field: row.query_or_entity_or_field,
    evidence: row.evidence,
    source_document_id: row.source_document_id,
    status: row.status,
    reviewer_note: row.reviewer_note,
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
    if (!selectedEvent) {
      return
    }

    setSaveState('saving')
    try {
      const updated = await updateMissingnessEvent(selectedEvent.event_id, {
        status: draftStatus,
        reviewer_note: draftReviewerNote
      })

      setEvents((current) => current.map((event) => event.event_id === updated.event_id ? updated : event))
      setSaveState('saved')
    } catch (saveError) {
      setSaveState('error')
      setError(saveError.message || 'Failed to update missingness event.')
    }
  }

  return (
    <PageGrid className="missingness-workbench">
      <Column>
        <PageHeader
          title="Absences"
          description="Make failed retrieval, sparse metadata, absent entities, access limits, and description gaps available as analytical evidence."
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
          subtitle="This view produces an absences / missingness report: explicit gap events, typology assignments, reviewer notes, and exportable evidence of what the current archive and retrieval stack cannot yet support. Missingness is treated as a candidate analytical condition, not proof of historical absence."
        />
      </Column>

      {error && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Absences unavailable" subtitle={error} />
        </Column>
      )}

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
              <p className="app-text-muted missingness-workbench__review-note">Use status and reviewer note fields to distinguish genuine archival absence from ingestion, retrieval, or description limits.</p>
            </div>
          </div>
        </Tile>
      </Column>

      {(summary?.completeness_cards || []).map((card) => (
        <Column key={card.label} lg={4} md={4} sm={4}>
          <Tile>
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
              <p><strong>{selectedEvent.query_or_entity_or_field}</strong></p>
              {selectedEvent.query_id && <p className="app-list-item__meta">Source run: {selectedEvent.query_id}</p>}
              <p className="app-text-muted">{selectedEvent.evidence}</p>
              <Select id="selected-missingness-status" labelText="Status" value={draftStatus} onChange={(event) => setDraftStatus(event.target.value)}>
                {statusOptions.map((option) => (
                  <SelectItem key={option} value={option} text={option} />
                ))}
              </Select>
              <TextArea
                id="selected-missingness-reviewer-note"
                labelText="Reviewer note"
                rows={5}
                value={draftReviewerNote}
                onChange={(event) => setDraftReviewerNote(event.target.value)}
              />
              <div className="app-actions-row app-actions-row--comfortable missingness-workbench__detail-actions">
                <Button size="sm" onClick={handleSaveEvent} disabled={saveState === 'saving'}>Save review state</Button>
                {saveState === 'saved' && <span>Saved</span>}
              </div>
            </>
          ) : (
            <p className="app-copy-reset">{loading ? 'Loading events...' : 'Select a missingness event from the table to review it.'}</p>
          )}
        </Tile>
      </Column>

      <Column lg={10} md={8} sm={4}>
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
                    return (
                      <TableRow
                        key={key || row.id}
                        {...rowProps}
                        onClick={() => setSelectedEventId(row.id)}
                        className={row.id === selectedEventId ? 'app-table-row--interactive app-table-row--selected' : 'app-table-row--interactive'}
                      >
                        {row.cells.map((cell) => {
                          if (cell.info.header === 'event_id') {
                            const event = events.find((item) => item.event_id === row.id)
                            const stateTag = getResearchStateTag(event)

                            return (
                              <TableCell key={cell.id}>
                                <div className="app-tag-row">
                                  <span>{cell.value}</span>
                                  {stateTag ? <Tag type={stateTag.type} size="sm">{stateTag.label}</Tag> : null}
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
      </Column>
    </PageGrid>
  )
}

export default MissingnessWorkbench
