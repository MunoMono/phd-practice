import {
  Button,
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
import { CheckmarkOutline, Download } from '@carbon/icons-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader'
import PanelHeader from '../../components/layout/PanelHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import { exportClaimsCsv, exportClaimsMarkdown, getClaimDetail, getClaims, updateClaim } from '../../api/claims'
import { getResearchStateTag } from '../../utils/researchState'
import { downloadFile } from '../../utils/workbenchExport'

const supportOptions = [
  { value: 'supported', text: 'supported' },
  { value: 'partially_supported', text: 'partially supported' },
  { value: 'unresolved', text: 'unresolved' },
  { value: 'unsupported', text: 'unsupported' }
]

const reviewerStatusOptions = [
  { value: 'draft', text: 'draft' },
  { value: 'in_review', text: 'in review' },
  { value: 'ready_for_supervisor_review', text: 'ready for supervisor review' },
  { value: 'needs_evidence', text: 'needs evidence' }
]

const ClaimsWorkbench = () => {
  const [searchParams] = useSearchParams()
  const [claims, setClaims] = useState([])
  const [selectedClaimId, setSelectedClaimId] = useState('')
  const [selectedClaim, setSelectedClaim] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saveState, setSaveState] = useState('idle')
  const [error, setError] = useState('')

  useEffect(() => {
    let isCancelled = false
    const seededClaimId = searchParams.get('claimId') || ''

    const loadClaims = async () => {
      setLoading(true)
      setError('')

      try {
        const payload = await getClaims()
        if (isCancelled) {
          return
        }

        setClaims(payload.claims || [])
        setSelectedClaimId((current) => current || seededClaimId || payload.claims?.[0]?.claim_id || '')
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError.message || 'Failed to load persisted claims.')
          setClaims([])
        }
      } finally {
        if (!isCancelled) {
          setLoading(false)
        }
      }
    }

    loadClaims()

    return () => {
      isCancelled = true
    }
  }, [searchParams])

  useEffect(() => {
    if (!selectedClaimId) {
      setSelectedClaim(null)
      return
    }

    let isCancelled = false

    const loadClaimDetail = async () => {
      try {
        const payload = await getClaimDetail(selectedClaimId)
        if (!isCancelled) {
          setSelectedClaim(payload)
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError.message || 'Failed to load claim detail.')
          setSelectedClaim(null)
        }
      }
    }

    loadClaimDetail()

    return () => {
      isCancelled = true
    }
  }, [selectedClaimId])

  const invalidSupportedClaims = claims.filter((claim) => claim.support_level === 'supported' && claim.evidence_chunk_ids.length === 0)

  const handleClaimChange = (field, value) => {
    setSelectedClaim((current) => current ? { ...current, [field]: value, updated_at: new Date().toISOString() } : current)
  }

  const saveClaim = async () => {
    if (!selectedClaim) {
      return
    }

    setSaveState('saving')
    try {
      const payload = await updateClaim(selectedClaim.claim_id, {
        claim_text: selectedClaim.claim_text,
        support_level: selectedClaim.support_level,
        caveats: selectedClaim.caveats,
        reviewer_status: selectedClaim.reviewer_status
      })

      setSelectedClaim(payload)
      setClaims((current) => current.map((claim) => claim.claim_id === payload.claim_id ? { ...claim, ...payload } : claim))
      setSaveState('saved')
    } catch (saveError) {
      setSaveState('error')
      setError(saveError.message || 'Failed to update claim.')
    }
  }

  const handleExportCsv = async () => {
    try {
      const content = await exportClaimsCsv()
      downloadFile('claim-evidence-matrix.csv', content, 'text/csv;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export claim-evidence CSV.')
    }
  }

  const handleExportMarkdown = async () => {
    try {
      const content = await exportClaimsMarkdown()
      downloadFile('claim-evidence-matrix.md', content, 'text/markdown;charset=utf-8')
    } catch (exportError) {
      setError(exportError.message || 'Failed to export claim-evidence Markdown.')
    }
  }

  return (
    <PageGrid className="claims-workbench">
      <Column>
        <PageHeader
          title="Claims and evidence"
          description="Tie interpretive claims to source chunks, support levels, caveats, and reviewer status before export."
          actions={(
            <Tag type="green" size="md">
              <CheckmarkOutline size={16} /> Evidence-gated
            </Tag>
          )}
        />
      </Column>

      <Column>
        <InlineNotification
          lowContrast
          kind="info"
          title="Analytical output"
          subtitle="This view produces a claim-evidence matrix. A claim cannot be exported as supported unless at least one evidence chunk is attached."
        />
      </Column>

      {error && (
        <Column>
          <InlineNotification lowContrast kind="error" title="Claims unavailable" subtitle={error} />
        </Column>
      )}

      {invalidSupportedClaims.length > 0 && (
        <Column>
          <InlineNotification
            lowContrast
            kind="warning"
            title="Support rule enforced"
            subtitle="A claim cannot be exported as supported unless at least one evidence chunk is attached. Claims without evidence chunks are downgraded to unresolved during export."
          />
        </Column>
      )}

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader
            title="Claim table"
            description="Select a claim to inspect evidence coverage, support level, caveats, and reviewer status."
            actions={(
              <div className="app-actions-row">
                <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportCsv}>Export claim-evidence CSV</Button>
                <Button kind="ghost" size="sm" renderIcon={Download} onClick={handleExportMarkdown}>Export claim-evidence Markdown</Button>
              </div>
            )}
          />
          <div className="claims-workbench__table-wrap">
            <TableContainer title="Claims">
              <Table>
              <colgroup>
                <col className="claims-workbench__claim-col" />
                <col className="claims-workbench__support-col" />
                <col className="claims-workbench__evidence-col" />
                <col className="claims-workbench__reviewer-col" />
              </colgroup>
              <TableHead>
                <TableRow>
                  <TableHeader>Claim</TableHeader>
                  <TableHeader>Support</TableHeader>
                  <TableHeader>Evidence chunks</TableHeader>
                  <TableHeader>Reviewer status</TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {claims.map((claim) => {
                  const stateTag = getResearchStateTag(claim)

                  return (
                    <TableRow key={claim.claim_id} onClick={() => setSelectedClaimId(claim.claim_id)} className={claim.claim_id === selectedClaimId ? 'app-table-row--interactive app-table-row--selected' : 'app-table-row--interactive'}>
                      <TableCell className="claims-workbench__claim-cell">
                        <div className="claims-workbench__claim-summary">
                          {stateTag ? <Tag type={stateTag.type} size="sm">{stateTag.label}</Tag> : null}
                          <span>{claim.claim_text}</span>
                        </div>
                      </TableCell>
                      <TableCell className="claims-workbench__compact-cell">{claim.support_level}</TableCell>
                      <TableCell className="claims-workbench__compact-cell">{claim.evidence_chunk_ids.length}</TableCell>
                      <TableCell className="claims-workbench__compact-cell">{claim.reviewer_status}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
              </Table>
            </TableContainer>
          </div>
          {loading && <InlineNotification lowContrast kind="info" title="Loading claims" subtitle="Fetching persisted claims and evidence coverage." />}
        </Tile>
      </Column>

      <Column lg={6} md={8} sm={4}>
        <Tile>
          <PanelHeader title="Claim detail" description="Update support level, caveats, and reviewer status while keeping evidence-chunk gating explicit." />
          {selectedClaim && (
            <>
              <div className="claims-workbench__detail-head">
                {getResearchStateTag(selectedClaim) ? <Tag type={getResearchStateTag(selectedClaim).type}>{getResearchStateTag(selectedClaim).label}</Tag> : null}
                <p className="claims-workbench__detail-copy"><strong>{selectedClaim.claim_text}</strong></p>
              </div>
              <div className="claims-workbench__tag-row">
                {selectedClaim.evidence_chunk_ids.length > 0 ? selectedClaim.evidence_chunk_ids.map((chunkId) => (
                  <Tag key={chunkId} type="blue">{chunkId}</Tag>
                )) : <Tag type="gray">No evidence chunks attached</Tag>}
              </div>
              {selectedClaim.support_level === 'supported' && selectedClaim.evidence_count === 0 && (
                <InlineNotification lowContrast kind="warning" title="Evidence required" subtitle="Supported claims without evidence will be downgraded to unresolved during export." />
              )}
              <Select id="claim-support-level" labelText="Support level" value={selectedClaim.support_level} onChange={(event) => handleClaimChange('support_level', event.target.value)}>
                {supportOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value} text={option.text} />
                ))}
              </Select>
              <InlineNotification lowContrast kind="info" title="Caveats" subtitle={selectedClaim.caveats || 'No caveats recorded yet.'} />
              <TextArea id="claim-caveats" labelText="Caveats" rows={5} value={selectedClaim.caveats || ''} onChange={(event) => handleClaimChange('caveats', event.target.value)} />
              <Select id="claim-reviewer-status" labelText="Reviewer status" value={selectedClaim.reviewer_status} onChange={(event) => handleClaimChange('reviewer_status', event.target.value)}>
                {reviewerStatusOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value} text={option.text} />
                ))}
              </Select>
              {(selectedClaim.evidence || []).length > 0 && (
                <div className="claims-workbench__evidence-list">
                  {(selectedClaim.evidence || []).map((evidence) => (
                    <div key={evidence.id} className="claims-workbench__evidence-item">
                      <strong>{evidence.chunk_id}</strong>
                      <p className="claims-workbench__evidence-copy">{evidence.citation_text || 'Citation not yet available for this evidence row.'}</p>
                      <p className="claims-workbench__evidence-meta">{evidence.page_range ? `Page range: ${evidence.page_range}` : 'Page range not yet recorded.'}</p>
                    </div>
                  ))}
                </div>
              )}
              <div className="claims-workbench__detail-actions">
                <Button size="sm" onClick={saveClaim} disabled={saveState === 'saving'}>Save claim updates</Button>
                {saveState === 'saved' && <span>Saved</span>}
              </div>
              <p className="claims-workbench__updated"><strong>Updated:</strong> {selectedClaim.updated_at}</p>
            </>
          )}
          {!selectedClaim && !loading && <p className="claims-workbench__updated">Select a persisted claim to inspect and update it.</p>}
        </Tile>
      </Column>
    </PageGrid>
  )
}

export default ClaimsWorkbench
