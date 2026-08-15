import { Button, Tag, Tile } from '@carbon/react'
import EvidenceStatusControl from './EvidenceStatusControl'

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

const EvidenceSourceCard = ({
  source,
  index,
  validationStatus,
  onValidationChange,
  onCopyCitation,
  onOpenCorpus,
  onShowAnalytics,
  onToggleProvenance
}) => {
  const provenanceTagType = source.provenanceStatus === 'loaded'
    ? 'green'
    : source.provenanceStatus === 'error'
      ? 'red'
      : 'gray'

  return (
    <Tile className="evidence-source-card">
      <div className="evidence-source-card__header">
        <div>
          <h4>Source {index + 1}</h4>
          <p>{source.title || 'Document title not yet exposed by endpoint.'}</p>
        </div>
        <div className="evidence-source-card__tags">
          <Tag type="blue">{source.pid || 'PID not yet exposed by endpoint'}</Tag>
          <Tag type={provenanceTagType}>{source.provenanceStatus}</Tag>
        </div>
      </div>

      <div className="evidence-source-card__meta">
        <span>Chunk ID: {source.chunkId || 'Not yet exposed by endpoint'}</span>
        <span>Document ID: {source.documentId || 'Not yet exposed by endpoint'}</span>
        <span>Page/Section: {source.page || 'N/A'}{source.section ? ` / ${source.section}` : ''}</span>
        <span>Retrieval score: {source.score ?? 'Not yet exposed by endpoint'}</span>
      </div>

      <div className="evidence-source-card__excerpt">
        {source.excerpt || 'No excerpt returned by the current endpoint.'}
      </div>

      <div className="evidence-source-card__citation">
        <strong>Citation:</strong> {renderCitation(source.citation)}
      </div>

      <div className="evidence-source-card__controls">
        <EvidenceStatusControl
          id={`evidence-status-${source.chunkId || index}`}
          value={validationStatus}
          onChange={onValidationChange}
        />
      </div>

      <div className="evidence-source-card__actions">
        <Button size="sm" kind="ghost" onClick={onCopyCitation}>Copy citation</Button>
        <Button size="sm" kind="ghost" onClick={onOpenCorpus}>Open in sources</Button>
        <Button size="sm" kind="ghost" onClick={onShowAnalytics}>Locate in semantic atlas</Button>
        <Button size="sm" kind="secondary" onClick={onToggleProvenance}>View provenance</Button>
      </div>

      {source.provenanceExpanded && (
        <div className="evidence-source-card__provenance">
          {source.provenance ? (
            <>
              <p><strong>Archive URL:</strong> {source.provenance.document?.authorityUrl || source.provenance.record_public_uri || 'Not yet exposed by endpoint.'}</p>
              <p><strong>Influenced inferences:</strong> {source.provenance.inferencesInfluenced || 'Not exposed by this immutable run.'}</p>
              <p><strong>Training runs:</strong> {(source.provenance.trainingRuns || []).length > 0 ? source.provenance.trainingRuns.map((run) => run.model).join(', ') : 'None returned'}</p>
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