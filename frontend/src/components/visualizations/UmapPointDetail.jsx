import { Button, Tag, Tile } from '@carbon/react'

const UmapPointDetail = ({ point, onOpenCorpus, onTraceEvidence, onOpenAbsences, onOpenCrossReadings, onCopyPid, onCopyExcerpt, onAddToMemo }) => {
  if (!point) {
    return (
      <Tile className="umap-point-detail">
        <h3>Point detail</h3>
        <p>Select a point in the atlas to inspect its PID, chunk, cluster, and excerpt-level metadata.</p>
      </Tile>
    )
  }

  return (
    <Tile className="umap-point-detail">
      <h3>{point.title || 'Untitled trace'}</h3>
      <div className="umap-point-detail__tags">
        <Tag type="blue">{point.pid || 'PID not yet exposed by endpoint'}</Tag>
        <Tag type="purple">{point.clusterLabel || 'Unlabelled cluster'}</Tag>
        <Tag type="teal">{point.sourceType || 'unknown'}</Tag>
      </div>

      <div className="umap-point-detail__grid">
        <p><strong>Document ID:</strong> {point.documentId || 'Not yet exposed by endpoint'}</p>
        <p><strong>Chunk ID:</strong> {point.chunkId || 'Not yet exposed by endpoint'}</p>
        <p><strong>Year:</strong> {point.year || 'Not yet exposed by endpoint'}</p>
        <p><strong>Confidence:</strong> {point.confidence ?? 'Not yet exposed by endpoint'}</p>
        <p><strong>Drift score:</strong> {point.driftScore ?? 'Not yet exposed by endpoint'}</p>
        <p><strong>Themes:</strong> {point.themes?.join(', ') || 'Not yet exposed by endpoint'}</p>
        <p><strong>Entities:</strong> {point.entities?.join(', ') || 'Not yet exposed by endpoint'}</p>
      </div>

      <div className="umap-point-detail__surface">
        <h4>Evidence surface</h4>
        <div className="umap-point-detail__grid">
          <p><strong>Is ingested:</strong> {point.evidenceSurface?.isIngested ? 'Yes' : 'No'}</p>
          <p><strong>Has embedding:</strong> {point.evidenceSurface?.hasEmbedding ? 'Yes' : 'No'}</p>
          <p><strong>Has extracted text:</strong> {point.evidenceSurface?.hasExtractedText ? 'Yes' : 'No'}</p>
          <p><strong>Has PDF:</strong> {point.evidenceSurface?.hasPdf ? 'Yes' : 'No'}</p>
          <p><strong>Has image assets:</strong> {point.evidenceSurface?.hasImageAssets ? 'Yes' : 'No'}</p>
          <p><strong>Has authority context:</strong> {point.evidenceSurface?.hasAuthorityContext ? 'Yes' : 'No'}</p>
          <p><strong>Visibility label:</strong> {point.evidenceSurface?.visibilityLabel || 'Not yet exposed by endpoint'}</p>
          <p><strong>Requires Docling/OCR:</strong> {point.evidenceSurface?.requiresDoclingOrOcr ? 'Yes' : 'No'}</p>
        </div>
        {point.evidenceSurface?.interpretationLimit && (
          <p className="umap-point-detail__limit"><strong>Interpretation limit:</strong> {point.evidenceSurface.interpretationLimit}</p>
        )}
      </div>

      <div className="umap-point-detail__surface">
        <h4>Scoped missingness</h4>
        <div className="umap-point-detail__grid">
          <p><strong>Item fields:</strong> {Object.keys(point.missingness?.itemFieldMissingness || {}).join(', ') || 'None flagged'}</p>
          <p><strong>Assets:</strong> {Object.keys(point.missingness?.assetMissingness || {}).join(', ') || 'None flagged'}</p>
          <p><strong>GraphQL exposure:</strong> {Object.keys(point.missingness?.graphqlExposureMissingness || {}).join(', ') || 'None flagged'}</p>
          <p><strong>LLM evidence:</strong> {Object.keys(point.missingness?.llmEvidenceMissingness || {}).join(', ') || 'None flagged'}</p>
        </div>
        {(point.missingness?.interpretationLimits || []).length > 0 && (
          <div className="umap-point-detail__limits">
            {point.missingness.interpretationLimits.map((limit) => (
              <p key={limit}>{limit}</p>
            ))}
          </div>
        )}
      </div>

      <div className="umap-point-detail__excerpt">
        {point.excerpt || 'No excerpt is available for this visual point.'}
      </div>

      <div className="umap-point-detail__actions">
        <Button kind="ghost" size="sm" onClick={onOpenCorpus}>Open in sources</Button>
        <Button kind="ghost" size="sm" onClick={onTraceEvidence}>Open in source interrogation</Button>
        <Button kind="ghost" size="sm" onClick={onOpenAbsences}>Open scoped absences</Button>
        <Button kind="ghost" size="sm" onClick={onOpenCrossReadings}>Open cross-readings</Button>
        <Button kind="ghost" size="sm" onClick={onCopyPid}>Copy PID</Button>
        <Button kind="ghost" size="sm" onClick={onCopyExcerpt}>Copy excerpt</Button>
        <Button kind="secondary" size="sm" onClick={onAddToMemo}>Add to research memo</Button>
      </div>
    </Tile>
  )
}

export default UmapPointDetail