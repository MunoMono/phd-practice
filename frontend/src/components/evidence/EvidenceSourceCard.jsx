import { AILabel, AILabelActions, AILabelContent, Button, Link, Tile } from '@carbon/react'
import { Launch } from '@carbon/icons-react'

const renderCitation = (citation) => {
  if (!citation) {
    return 'Not yet exposed by endpoint.'
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

const SourceAiLabel = ({ source, classificationLabel }) => (
  <AILabel
    className="evidence-source-card__ai-label"
    size="xs"
    textLabel={`Explain source selection for ${source.pid || source.sourceId || 'this source'}`}
  >
    <AILabelContent>
      <div className="evidence-source-card__ai-explanation">
        <p className="evidence-source-card__ai-eyebrow">AI explained</p>
        <h4>Source selection</h4>
        <p>This archival record was selected for review against the current research question.</p>
        <hr />
        <h5>What this means</h5>
        <ol>
          <li>The archive identifier is {source.pid || 'not exposed'}.</li>
          <li>Its relation to this question is {classificationLabel || 'not classified'}.</li>
          <li>Its archive status is {source.provenanceStatus || 'not exposed'}.</li>
        </ol>
        <p className="evidence-source-card__ai-note">The archival passage and its descriptive information are source material. The AI label explains selection for review, not the historical record.</p>
      </div>
      <AILabelActions>
        <div className="evidence-source-card__ai-model">
          <span>AI model</span>
          <Link href="https://huggingface.co/Qwen/Qwen3-8B-GGUF" target="_blank" rel="noreferrer" renderIcon={Launch}>Qwen3-8B GGUF</Link>
        </div>
      </AILabelActions>
    </AILabelContent>
  </AILabel>
)

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
  onShowAnalytics,
  onToggleProvenance
}) => {
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

  return (
    <Tile id={id} className="evidence-source-card">
      <div className="evidence-source-card__header">
        <div>
          <h4>Source {source.sourceId || index + 1}</h4>
          <p>{source.title || 'Document title not yet exposed by endpoint.'}</p>
        </div>
        <div className="evidence-source-card__header-actions">
          <SourceAiLabel source={source} classificationLabel={classificationLabel} />
          <dl className="evidence-source-card__status" aria-label="Source retrieval status">
            <div><dt>Archive ID</dt><dd>{source.pid || 'Unavailable'}</dd></div>
            <div><dt>Relation</dt><dd>{classificationLabel || 'Not classified'}</dd></div>
            <div><dt>Status</dt><dd>{source.provenanceStatus || 'Unavailable'}</dd></div>
          </dl>
        </div>
      </div>

      <div className="evidence-source-card__meta">
        <span>Chunk ID: {source.chunkId || 'Not yet exposed by endpoint'}</span>
        <span>Document ID: {source.documentId || 'Not yet exposed by endpoint'}</span>
        <span>Date: {source.date || 'Not retained in capture'}</span>
        <span>Contributor: {source.contributorStatus || 'Contributor not retained in capture'}</span>
        <span>Source type: {source.sourceType || 'Not retained in capture'}</span>
        <span>Temporal class: {source.temporalClass || 'Not retained in capture'}</span>
        {source.personNameStatus && <span>{source.personNameStatus}</span>}
        {source.temporalAuditStatus && <span>Temporal audit: {source.temporalAuditStatus}</span>}
        <span>Page/Section: {source.page || 'N/A'}{source.section ? ` / ${source.section}` : ''}</span>
        <span>Archive identity: {source.identity?.recordPid || 'record unavailable'} → {source.identity?.mediaPid || 'media unavailable'} → {source.identity?.assetPid || 'asset unavailable'}</span>
        <span>Retrieval score: {source.score ?? 'Not yet exposed by endpoint'}</span>
      </div>

      {source.classificationScope && <p className="evidence-source-card__classification-scope">{source.classificationScope}</p>}
      {source.classificationProjection && <p className="evidence-source-card__classification-scope">Stored class: {source.classificationProjection.stored_classification}; read-only display projection: {source.classificationProjection.displayed_classification}.</p>}
      {source.classificationAuditNote && <p className="evidence-source-card__classification-scope">{source.classificationAuditNote}</p>}
      {source.unclassifiedStatus && <p className="evidence-source-card__classification-scope">{source.unclassifiedStatus}</p>}
      {source.formulation && <p className="evidence-source-card__classification-scope">Documentary formulation: {source.formulation}</p>}
      {source.sourceFamily && <p className="evidence-source-card__classification-scope">Source-family concentration: {source.sourceFamily}</p>}

      <div className="evidence-source-card__excerpt">
        {source.excerpt || 'No excerpt returned by the current endpoint.'}
      </div>

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
          <DetailRow label="Evidence channel">{source.passageEvidenceChannel || 'WINDOW_CONTEXT'}</DetailRow>
          {Number.isFinite(source.passageScore) && <DetailRow label="Passage score">{source.passageScore.toFixed(3)}</DetailRow>}
          <DetailRow label="Text relevance">{Number.isFinite(source.textScore) ? source.textScore.toFixed(3) : 'Not scored'}</DetailRow>
          <DetailRow label="Metadata score">{Number.isFinite(source.metadataScore) ? source.metadataScore.toFixed(3) : 'Source nomination only'}</DetailRow>
          <DetailRow label="Documentary window">Page {source.page || 'unavailable'}{source.section ? `, ${source.section}` : ''} | {source.chunkId || 'chunk unavailable'}</DetailRow>
        </dl>
      </details>

      <div className="evidence-source-card__citation">
        <strong>Citation:</strong> {renderCitation(source.citation)}
      </div>

      <div className="evidence-source-card__actions">
        <Button size="sm" kind="ghost" onClick={onCopyCitation}>Copy citation</Button>
        <Button size="sm" kind="ghost" onClick={onOpenCorpus}>Open in sources</Button>
        <Button size="sm" kind="ghost" onClick={onShowAnalytics}>Locate in semantic atlas</Button>
        <Button size="sm" kind="secondary" onClick={onToggleProvenance}>View provenance</Button>
      </div>

      {source.provenanceExpanded && (
        <div className="evidence-source-card__provenance">
          {(source.provenance || Object.keys(source.catalogueLocation || {}).length > 0 || Object.keys(source.rightsAccess || {}).length > 0) ? (
            <>
              {source.provenance && <>
                <p>Documentary passage provenance</p>
                <dl className="evidence-source-card__detail-list">
                <DetailRow label="Identity chain">{source.provenance.archive_record_pid || 'record unavailable'} → {source.provenance.attached_media_pid || 'media unavailable'} → {source.provenance.asset_pid || 'asset unavailable'} → page {source.provenance.page || source.page || 'unavailable'} → {source.provenance.chunk_id || source.chunkId || 'chunk unavailable'}</DetailRow>
                {source.provenance.source_uri && <DetailRow label="Source file"><a href={source.provenance.source_uri} target="_blank" rel="noreferrer">Open archival source file</a></DetailRow>}
                <DetailRow label="Influenced inferences">{source.provenance.inferencesInfluenced || 'Not exposed by this immutable run.'}</DetailRow>
                <DetailRow label="Training runs">{(source.provenance.trainingRuns || []).length > 0 ? source.provenance.trainingRuns.map((run) => run.model).join(', ') : 'None returned'}</DetailRow>
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
              {source.provenanceStatus !== 'loaded' && <p>Catalogue metadata was refreshed from DDR GraphQL. The retained document asset has changed, so current passages require re-ingestion and revalidation.</p>}
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