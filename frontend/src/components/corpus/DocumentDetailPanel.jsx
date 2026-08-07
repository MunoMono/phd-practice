import { Button, SkeletonText, Tag, Tile } from '@carbon/react'
import './CorpusPanels.scss'

const hasValue = (value) => {
  if (value === null || value === undefined) {
    return false
  }

  if (Array.isArray(value)) {
    return value.some((item) => hasValue(item))
  }

  if (typeof value === 'string') {
    return value.trim().length > 0
  }

  return true
}

const renderValue = (value, fallback = 'Not available from the current endpoint.') => {
  if (!hasValue(value)) {
    return fallback
  }

  if (Array.isArray(value)) {
    const flattened = value.filter(Boolean).join(', ')
    return flattened || fallback
  }

  if (typeof value === 'string') {
    return value.trim() || fallback
  }

  return value
}

const renderTagValues = (values, emptyLabel = 'Not yet recorded') => {
  if (!hasValue(values)) {
    return <p className="corpus-panel__empty">{emptyLabel}</p>
  }

  return (
    <div className="app-tag-row corpus-panel__tag-row corpus-panel__tag-row--wrap">
      {values.map((value) => (
        <Tag key={value} type="cool-gray">{value}</Tag>
      ))}
    </div>
  )
}

const formatMlEligibility = (annotations) => {
  if (!annotations) {
    return 'Not available from the current endpoint.'
  }

  if (annotations.ml_policy_status === 'excluded_use_for_ml_false') {
    return 'Excluded'
  }

  if (annotations.used_for_ml === true || annotations.ml_policy_status?.startsWith('eligible')) {
    return 'Included'
  }

  return 'Policy unresolved'
}

const formatMlPageScope = (annotations) => {
  const scope = annotations?.ml_page_scope || annotations?.ml_pages || ''
  if (scope === 'all_pages') {
    return 'All pages'
  }

  if (scope) {
    return `pp. ${scope.replace(/-/g, '–')}`
  }

  if (annotations?.ml_policy_status === 'excluded_use_for_ml_false' || annotations?.used_for_ml === false) {
    return 'Not applicable'
  }

  if (annotations?.ml_policy_status === 'policy_unresolved' || annotations?.used_for_ml === null || annotations?.used_for_ml === undefined) {
    return 'Unresolved'
  }

  if (annotations?.used_for_ml === true) {
    return 'All pages'
  }

  return 'Not yet recorded'
}

const formatPolicyReason = (annotations) => {
  if (!annotations?.ml_exclusion_reason) {
    return null
  }

  if (annotations.ml_exclusion_reason === 'asset_marked_use_for_ml_false') {
    return 'Asset marked Use for ML = false'
  }

  if (annotations.ml_exclusion_reason.startsWith('invalid_ml_pages:')) {
    return 'Page-scope metadata could not be interpreted safely'
  }

  return annotations.ml_exclusion_reason.replaceAll('_', ' ')
}

const formatStatusLabel = (value) => {
  if (!value) {
    return 'Unknown'
  }

  return value.replaceAll('_', ' ')
}

const formatAccessRestriction = (value) => {
  if (!value) {
    return null
  }

  const normalized = value.toLowerCase()
  if (normalized === 'int') {
    return 'Internal'
  }

  return value
}

const formatExtent = (number, unit) => {
  if (!hasValue(number) && !hasValue(unit)) {
    return null
  }

  if (hasValue(number) && hasValue(unit)) {
    return `${number} ${unit}`
  }

  return number || unit
}

const formatMetadataList = (metadata) => Object.entries(metadata || {}).filter(([, value]) => {
  if (Array.isArray(value)) {
    return value.length > 0
  }

  return value !== null && value !== undefined && `${value}`.trim() !== ''
})

const buildFieldRows = (rows) => rows.filter((row) => hasValue(row.value))

const formatFieldLabel = (value) => value.replaceAll('_', ' ')

const formatAuthorityRole = (value) => value.replaceAll('_', ' ')

const HUMAN_FIELD_LABELS = {
  title: 'Object title',
  subjects: 'Subjects',
  scope_and_content: 'Scope and content',
  abstract: 'Abstract',
  project_theme: 'Project theme',
  project_title: 'Project title',
  methodology: 'Methodology',
  level: 'Archival level',
  fonds_code: 'Fonds code',
  series_id: 'Series',
  ddr_period: 'DDR period',
  parent_collection: 'Parent collection',
}

const copyCitation = async (detail) => {
  const document = detail?.document || {}
  const annotations = detail?.annotations || {}
  const citation = [
    document.title || 'Untitled document',
    annotations.archive_record_pid ? `Archive record PID: ${annotations.archive_record_pid}` : annotations.pid ? `PID: ${annotations.pid}` : null,
    annotations.asset_pid ? `Asset PID: ${annotations.asset_pid}` : annotations.asset_id ? `Asset ID: ${annotations.asset_id}` : null,
    document.publication_year ? `Year: ${document.publication_year}` : null,
    document.id ? `Document ID: ${document.id}` : null
  ].filter(Boolean).join(' | ')

  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(citation)
  }
}

const DocumentDetailPanel = ({ detail, loading, onTraceEvidence, onViewAnalytics, onInspectMissingness, authoritySummary = null }) => {
  if (loading) {
    return (
      <Tile>
        <SkeletonText paragraph lineCount={8} />
      </Tile>
    )
  }

  if (!detail) {
    return (
      <Tile>
        <h3>Source detail</h3>
        <p>Select a source to inspect metadata, ingestion status, ML annotations, and handoff paths into source interrogation, absences, and the semantic atlas.</p>
      </Tile>
    )
  }

  const { document, annotations, similarDocuments, error } = detail
  const catalogueMetadata = annotations?.catalogue_metadata || {}
  const provenanceMetadata = annotations?.retrieval_provenance || {}
  const rightsAccess = annotations?.rights_access || {}
  const policyReason = formatPolicyReason(annotations)
  const recordPublicUrl = annotations?.record_public_uri || provenanceMetadata.record_public_uri || null
  const policyStatusLabel = formatStatusLabel(annotations?.ml_policy_status)
  const policyExplanation = annotations?.ml_policy_status === 'policy_unresolved' || annotations?.used_for_ml === null || annotations?.used_for_ml === undefined
    ? policyReason || 'The current local record does not yet contain enough asset-level policy data to determine ML eligibility or page scope.'
    : null
  const retrievalRows = buildFieldRows([
    { label: 'Document ID', value: document.id, fallback: 'Not yet exposed by endpoint' },
    { label: 'Archive record PID', value: annotations?.archive_record_pid },
    { label: 'Attached-media PID', value: annotations?.attached_media_pid || document.attached_media_pid || document.pid },
    { label: 'Asset PID', value: annotations?.asset_pid },
    { label: 'Asset ID', value: annotations?.asset_id },
    { label: 'Source filename', value: annotations?.source_filename || document.filename },
    { label: 'Repository', value: provenanceMetadata.repository },
    { label: 'Accession / shelfmark', value: provenanceMetadata.accession_shelfmark },
    { label: 'Box / container', value: provenanceMetadata.box_number },
    { label: 'Container title', value: provenanceMetadata.container_title },
    { label: 'Location note', value: provenanceMetadata.location_note },
    { label: 'Reference code', value: provenanceMetadata.reference_code || provenanceMetadata.archive_reference },
    { label: 'Page count', value: annotations?.page_count ?? document.page_count ?? provenanceMetadata.page_count ?? null, fallback: 'Not yet recorded' },
    { label: 'Page-count source', value: annotations?.page_count_source || provenanceMetadata.page_count_source, fallback: 'Not yet recorded' },
    { label: 'Source URI', value: annotations?.source_uri || document.source_uri },
  ])
  const rightsRows = [
    { label: 'Copyright', value: rightsAccess.copyright },
    { label: 'Copyright holder', value: rightsAccess.copyright_holder },
    { label: 'Copyright holder (other)', value: rightsAccess.copyright_holder_other },
    { label: 'Data rights', value: rightsAccess.data_rights },
    { label: 'Data rights holder', value: rightsAccess.data_rights_holder },
    { label: 'Image rights', value: rightsAccess.image_rights },
    { label: 'Image rights holder', value: rightsAccess.image_rights_holder },
    { label: 'Rights owner', value: rightsAccess.rights_owner },
    { label: 'Rights holders', value: rightsAccess.rights_holders },
    { label: 'Access restriction', value: formatAccessRestriction(rightsAccess.access_restriction) },
    { label: 'Rights statement', value: rightsAccess.rights_statement_uri },
    { label: 'Consent status', value: rightsAccess.consent_status },
    { label: 'Consent scope', value: rightsAccess.consent_scope },
    { label: 'Consent evidence URI', value: rightsAccess.consent_evidence_uri },
    { label: 'Takedown contact', value: rightsAccess.takedown_contact },
  ]
  const catalogueRows = buildFieldRows([
    { label: 'Caption / asset title', value: catalogueMetadata.caption },
    { label: 'Creator', value: catalogueMetadata.creator },
    { label: 'Date', value: catalogueMetadata.date },
    { label: 'Date qualifier', value: catalogueMetadata.date_qualifier },
    { label: 'Language', value: catalogueMetadata.language },
    { label: 'Document / publication type', value: catalogueMetadata.document_type },
    { label: 'Extent', value: formatExtent(catalogueMetadata.extent_number, catalogueMetadata.extent_unit) },
  ])
  const extraCatalogueRows = formatMetadataList(catalogueMetadata).filter(([key]) => ![
    'caption',
    'creator',
    'date',
    'date_qualifier',
    'language',
    'document_type',
    'extent_number',
    'extent_unit',
    'keywords',
    'normalized_date',
    'date_unknown',
  ].includes(key))
  const persistence = annotations?.persistence || {}
  const persistenceRows = [
    { label: 'Local persistence status', value: document.processing_status || annotations?.processing_status, fallback: 'Unknown' },
    { label: 'Metadata roles version', value: persistence.metadata_roles_version || annotations?.metadata_roles_version, fallback: 'Not yet recorded' },
    { label: 'Ingestion version', value: persistence.ingestion_version || annotations?.ingestion_version, fallback: 'Not yet recorded' },
    { label: 'Corpus version', value: persistence.corpus_version || annotations?.corpus_version, fallback: 'Not yet recorded' }
  ]

  return (
    <Tile>
      <h3 className="corpus-panel__section-title">{document.title}</h3>
      <div className="app-tag-row corpus-panel__tag-row">
        <Tag type="blue">{annotations?.archive_record_pid || annotations?.pid || 'Record PID unavailable'}</Tag>
        <Tag type="gray">{document.publication_year || 'Year not yet exposed by endpoint'}</Tag>
        <Tag type={document.processing_status === 'completed' ? 'green' : 'blue'}>{document.processing_status || 'unknown'}</Tag>
      </div>

      {error && <p>{error}</p>}

      <div className="corpus-panel__stack">
        <div>
          <h4 className="corpus-panel__section-title">Corpus control</h4>
          <p className="corpus-panel__copy">ML eligibility: {formatMlEligibility(annotations)}</p>
          <p className="corpus-panel__copy">ML page scope: {formatMlPageScope(annotations)}</p>
          <p className="corpus-panel__copy">Policy status: {renderValue(policyStatusLabel, 'Policy unresolved')}</p>
          {policyReason ? <p className="corpus-panel__copy">Reason: {policyReason}</p> : null}
          {policyExplanation ? <p className="corpus-panel__meta">{policyExplanation}</p> : null}
        </div>

        <div>
          <h4 className="corpus-panel__section-title">Rights and access</h4>
          <div className="corpus-panel__list">
            {rightsRows.map((row) => (
              <div key={row.label} className="corpus-panel__field-row">
                <p className="corpus-panel__field-label">{row.label}</p>
                <p className="corpus-panel__field-value">{renderValue(row.value, 'Not recorded')}</p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h4 className="corpus-panel__section-title">Retrieval and provenance</h4>
          <div className="corpus-panel__list">
            {retrievalRows.map((row) => (
              <div key={row.label} className="corpus-panel__field-row">
                <p className="corpus-panel__field-label">{row.label}</p>
                <p className="corpus-panel__field-value">{renderValue(row.value, row.fallback || 'Not yet recorded')}</p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h4 className="corpus-panel__section-title">Archive / catalogue metadata</h4>
          {catalogueRows.length > 0 ? (
            <>
              <div className="corpus-panel__list">
                {catalogueRows.map((row) => (
                  <div key={row.label} className="corpus-panel__field-row">
                    <p className="corpus-panel__field-label">{row.label}</p>
                    <p className="corpus-panel__field-value">{renderValue(row.value, 'Not recorded')}</p>
                  </div>
                ))}
              </div>

              <div className="corpus-panel__catalogue-tags">
                <p className="corpus-panel__field-label">Keywords / controlled terms</p>
                {renderTagValues(catalogueMetadata.keywords, 'Not recorded')}
              </div>

              {extraCatalogueRows.length > 0 ? (
                <div className="corpus-panel__list">
                  {extraCatalogueRows.map(([key, value]) => (
                    <div key={key} className="corpus-panel__field-row">
                      <p className="corpus-panel__field-label">{HUMAN_FIELD_LABELS[key] || formatFieldLabel(key)}</p>
                      <p className="corpus-panel__field-value">{renderValue(value)}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <p className="corpus-panel__empty">No archive/catalogue metadata is currently attached to this local corpus record.</p>
          )}
          <p className="corpus-panel__meta">Archive / catalogue metadata is descriptive context about the archived object, not a transcription of the PDF source text.</p>
        </div>

        <div>
          <h4 className="corpus-panel__section-title">Persistence and handoff</h4>
          <div className="corpus-panel__list">
            {persistenceRows.map((row) => (
              <div key={row.label} className="corpus-panel__field-row">
                <p className="corpus-panel__field-label">{row.label}</p>
                <p className="corpus-panel__field-value">{renderValue(row.value, row.fallback)}</p>
              </div>
            ))}
          </div>
          <p className="corpus-panel__copy">Analytical handoff: source interrogation, absences, or semantic atlas, without collapsing policy metadata into source evidence.</p>
        </div>

        {authoritySummary ? (
          <div>
            <h4 className="corpus-panel__section-title">Archive authorities</h4>
            <div className="app-tag-row corpus-panel__tag-row">
              <Tag type="teal">{authoritySummary.totalRecords} authority records</Tag>
              <Tag type="blue">{authoritySummary.count} authority types</Tag>
              <Tag type="gray">{authoritySummary.coreRecords} core</Tag>
              <Tag type="purple">{authoritySummary.criticalRecords} critical</Tag>
            </div>
            <p className="corpus-panel__meta">Authorities support future entity resolution, filtering and controlled query expansion. They are not source-document evidence.</p>
            <div className="corpus-panel__list corpus-panel__list--compact">
              {authoritySummary.authorityTypes.slice(0, 4).map((item) => (
                <div key={item.authority_type} className="corpus-panel__field-row">
                  <p className="corpus-panel__field-label">{formatFieldLabel(item.authority_type)}</p>
                  <p className="corpus-panel__field-value">{item.count} records · {item.allowed_roles.map(formatAuthorityRole).join(', ')}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div>
          <h4 className="corpus-panel__section-title">Similar documents</h4>
          {similarDocuments?.length > 0 ? (
            <div className="corpus-panel__list">
              {similarDocuments.slice(0, 5).map((similar) => (
                <div key={similar.document_id}>
                  <strong>{similar.title}</strong>
                  <div className="corpus-panel__meta">PID: {similar.pid || 'Not yet exposed by endpoint'} | Similarity: {(similar.similarity * 100).toFixed(1)}%</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="corpus-panel__empty">No similar documents returned for this document.</p>
          )}
        </div>

        <div className="app-actions-row app-actions-row--comfortable">
          <Button kind="primary" onClick={onTraceEvidence}>Interrogate this source</Button>
          <Button kind="secondary" onClick={onInspectMissingness}>Inspect absences</Button>
          <Button kind="ghost" onClick={onViewAnalytics}>Locate in atlas</Button>
          <Button kind="ghost" onClick={() => copyCitation(detail)}>Copy citation</Button>
          <Button kind="ghost" disabled={!recordPublicUrl} onClick={() => recordPublicUrl && window.open(recordPublicUrl, '_blank', 'noopener,noreferrer')}>Open DDR source</Button>
        </div>
      </div>
    </Tile>
  )
}

export default DocumentDetailPanel