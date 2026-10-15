import { Button, Tile } from '@carbon/react'
import { useState } from 'react'

const provenanceFields = (value, path = []) => {
  if (value === null || value === undefined || value === '') return []
  if (typeof value === 'object') return Object.entries(value).flatMap(([key, item]) => (
    provenanceFields(item, [...path, Array.isArray(value) ? `Item ${Number(key) + 1}` : key.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2')])
  ))
  return [{ path: path.join(' / '), value: typeof value === 'boolean' ? value ? 'Yes' : 'No' : String(value) }]
}

const ProvenanceFields = ({ value }) => (
  <dl className="evidence-source-card__provenance-grid">
    {provenanceFields(value).map((field) => (
      <div className="evidence-source-card__provenance-field" key={field.path}>
        <dt>{field.path}</dt>
        <dd tabIndex={field.value.length > 120 ? 0 : undefined}>{field.value}</dd>
      </div>
    ))}
  </dl>
)

const renderCitation = (citation, source) => {
  if (!citation) {
    return [source.title, source.date, source.page != null ? `p. ${source.page}` : null, source.pid, source.publicUrl].filter(Boolean).join(', ')
  }

  if (typeof citation === 'string') {
    return citation
  }

  return [
    citation.title,
    citation.pid ? `PID: ${citation.pid}` : null,
    citation.page ? `Page: ${citation.page}` : null,
    citation.section ? `Section: ${citation.section}` : null,
    citation.publicUrl || null
  ].filter(Boolean).join(' | ')
}

const DetailRow = ({ label, children }) => (
  <div className="evidence-source-card__detail-row">
    <dt>{label}</dt>
    <dd>{children}</dd>
  </div>
)

const EvidenceSourceCard = ({
  id,
  source,
  index,
  onCopyCitation,
  onOpenCorpus,
  onShowAnalytics
}) => {
  const [expanded, setExpanded] = useState(Boolean(source.provenanceExpanded))
  const classificationLabel = {
    DIRECT_SUPPORT: 'Direct support',
    PARTIAL_SUPPORT: 'Partial support',
    CONTEXTUAL: 'Contextual',
    CONTRADICTORY_OR_CONTESTING: 'Contesting',
    NO_RELEVANT_PASSAGE: 'No relevant passage',
    UNCLASSIFIED: 'Unclassified',
    CONTEXTUAL_ONLY: 'Context only',
    INFERENCE_ONLY: 'Inference only',
    NOT_RELEVANT: 'Not relevant'
  }[source.evidenceClassification?.relationship_to_question || source.evidenceClassification?.classification]
  const title = source.title || 'Document title not yet exposed by endpoint.'

  return (
    <Tile id={id} className="evidence-source-card" tabIndex={-1}>
      {(source.anchorAliases || source.aliases || []).filter((alias) => alias !== id).map((alias) => <span key={alias} id={alias} className="evidence-source-card__anchor" />)}
      <div className="evidence-source-card__header">
        <div>
          <h4>Source {index + 1} – {title}</h4>
          <p>{source.date || 'Date not recorded'} | Page {source.page ?? 'unavailable'}{source.section ? ` / ${source.section}` : ''}</p>
        </div>
      </div>
      <div className="evidence-source-card__excerpt">
        {source.excerpt || 'No excerpt returned by the current endpoint.'}
      </div>
      <details className="evidence-source-card__why" open={expanded} onToggle={(event) => setExpanded(event.currentTarget.open)}>
        <summary>Provenance details</summary>
        <div className="evidence-source-card__header-actions">
          <dl className="evidence-source-card__status" aria-label="Source retrieval status">
            {source.pid && <div><dt>Archive ID</dt><dd>{source.pid}</dd></div>}
            {source.evidenceState && <div><dt>Answer use</dt><dd>{source.evidenceState}</dd></div>}
            {classificationLabel && <div><dt>Relation</dt><dd>{classificationLabel}</dd></div>}
            {source.evidenceType && <div><dt>Evidence type</dt><dd>{source.evidenceType}</dd></div>}
            {source.provenanceStatus && <div><dt>Status</dt><dd>{source.provenanceStatus}</dd></div>}
          </dl>
        </div>
      <div className="evidence-source-card__meta">
        {source.chunkId && <span>Chunk ID: {source.chunkId}</span>}
        {source.documentId && <span>Document ID: {source.documentId}</span>}
      </div>
      <div className="evidence-source-card__retained-metadata">
        <ProvenanceFields value={Object.fromEntries(Object.entries(source).filter(([key]) => ![
          'title', 'excerpt', 'provenance', 'aliases', 'anchorAliases', 'anchor', 'detail',
          'chunkId', 'documentId', 'pid', 'date', 'page', 'evidenceState', 'evidenceType', 'provenanceStatus',
          'retrievalChannels', 'sourceNominationChannels', 'sourceNominationScore', 'metadataMatches',
          'archiveNominationReasons', 'passageEvidenceChannel', 'passageScore', 'textScore', 'metadataScore',
        ].includes(key)))} />
        {source.provenance && <ProvenanceFields value={Object.fromEntries(Object.entries(source.provenance).filter(([key]) => !['text', 'excerpt'].includes(key)))} />}
      </div>

      </details>

      {(source.sourceNominationChannels.length > 0 || source.retrievalChannels.length > 0 || source.metadataMatches.length > 0 || source.archiveNominationReasons.length > 0) && (
        <details className="evidence-source-card__why">
          <summary>Why this source?</summary>
          <dl className="evidence-source-card__detail-list">
            <DetailRow label="Nomination channel">{(source.sourceNominationChannels.length > 0 ? source.sourceNominationChannels : source.retrievalChannels).join(' + ') || 'Not exposed'}</DetailRow>
            {Number.isFinite(source.sourceNominationScore) && <DetailRow label="Nomination score">{source.sourceNominationScore.toFixed(3)}</DetailRow>}
            {source.metadataMatches.map((match, matchIndex) => <DetailRow key={`${match.field}-${matchIndex}`} label={`Metadata: ${match.field}`}>{match.value}</DetailRow>)}
            {source.archiveNominationReasons.map((reason, reasonIndex) => <DetailRow key={`${reason.field}-${reasonIndex}`} label={`Archive: ${reason.field}`}>{reason.value} ({reason.match})</DetailRow>)}
            <DetailRow label="Identity chain">{source.identity?.recordPid || 'record unavailable'} → {source.identity?.mediaPid || 'media unavailable'} → {source.identity?.assetPid || 'asset unavailable'} → page {source.page || 'unavailable'} → {source.chunkId || 'chunk unavailable'}</DetailRow>
          </dl>
        </details>
      )}

      <details className="evidence-source-card__why">
        <summary>Why this passage?</summary>
        <dl className="evidence-source-card__detail-list">
          {source.passageEvidenceChannel && <DetailRow label="Evidence channel">{source.passageEvidenceChannel}</DetailRow>}
          {Number.isFinite(source.passageScore) && <DetailRow label="Passage score">{source.passageScore.toFixed(3)}</DetailRow>}
          {Number.isFinite(source.textScore) && <DetailRow label="Text relevance">{source.textScore.toFixed(3)}</DetailRow>}
          {Number.isFinite(source.metadataScore) && <DetailRow label="Metadata score">{source.metadataScore.toFixed(3)}</DetailRow>}
          <DetailRow label="Documentary window">Page {source.page || 'unavailable'}{source.section ? `, ${source.section}` : ''} | {source.chunkId || 'chunk unavailable'}</DetailRow>
        </dl>
      </details>

      <div className="evidence-source-card__actions">
        <Button size="sm" kind="ghost" onClick={onCopyCitation}>Copy citation</Button>
        <Button size="sm" kind="ghost" onClick={onOpenCorpus}>Open in sources</Button>
        <Button size="sm" kind="ghost" onClick={onShowAnalytics}>Locate in semantic atlas</Button>
        <Button size="sm" kind="ghost" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>View provenance</Button>
        {source.publicUrl && <Button as="a" size="sm" kind="ghost" href={source.publicUrl} target="_blank" rel="noreferrer">Open original source</Button>}
      </div>

      {expanded && (
        <div className="evidence-source-card__provenance">
          <p><strong>Citation:</strong> {renderCitation(source.citation, source)}</p>
          {(source.provenance || Object.keys(source.catalogueLocation || {}).length > 0 || Object.keys(source.rightsAccess || {}).length > 0) ? (
            <>
              {source.provenance && <>
                <p>Documentary passage provenance</p>
                <dl className="evidence-source-card__detail-list">
                <DetailRow label="Identity chain">{source.provenance.archive_record_pid || 'record unavailable'} → {source.provenance.attached_media_pid || 'media unavailable'} → {source.provenance.asset_pid || 'asset unavailable'} → page {source.provenance.page || source.page || 'unavailable'} → {source.provenance.chunk_id || source.chunkId || 'chunk unavailable'}</DetailRow>
                {source.provenance.source_uri && <DetailRow label="Source file"><a href={source.provenance.source_uri} target="_blank" rel="noreferrer">Open archival source file</a></DetailRow>}
                </dl>
              </>}
              {Object.keys(source.catalogueLocation || {}).length > 0 && <>
                <p>Current catalogue metadata</p>
                <dl className="evidence-source-card__detail-list">
              {source.catalogueLocation?.repository && <DetailRow label="Repository">{source.catalogueLocation.repository}</DetailRow>}
              {source.catalogueLocation?.accession_shelfmark && <DetailRow label="Accession">{source.catalogueLocation.accession_shelfmark}</DetailRow>}
              {source.catalogueLocation?.location_note && <DetailRow label="Location note">{source.catalogueLocation.location_note}</DetailRow>}
                </dl>
              </>}
              {Object.keys(source.rightsAccess || {}).length > 0 && <>
                <p>Rights and access</p>
                <dl className="evidence-source-card__detail-list">
              {source.rightsAccess?.copyright_holder && <DetailRow label="Copyright holder">{source.rightsAccess.copyright_holder}</DetailRow>}
              {source.rightsAccess?.image_rights && <DetailRow label="Image rights">{source.rightsAccess.image_rights}</DetailRow>}
              {source.rightsAccess?.data_rights && <DetailRow label="Data rights">{source.rightsAccess.data_rights}</DetailRow>}
                </dl>
              </>}
            </>
          ) : (
            <p>Provenance details are not available from the current endpoint.</p>
          )}
        </div>
      )}
    </Tile>
  )
}

export default EvidenceSourceCard