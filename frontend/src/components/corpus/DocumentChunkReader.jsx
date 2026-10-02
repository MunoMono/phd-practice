import { Button, Checkbox, InlineNotification, TextInput, Tile } from '@carbon/react'
import { ArrowRight, DocumentView } from '@carbon/icons-react'
import { useState } from 'react'

const MAX_SELECTED_CHUNKS = 20

const pageLabel = (chunk) => chunk.source_page ? `Page ${chunk.source_page}` : 'Page not recorded'

const DocumentChunkReader = ({ chunks, loading, error, access, selectedChunks, onToggleChunk, onSynthesize }) => {
  const [question, setQuestion] = useState('')
  const selectedCount = Object.keys(selectedChunks).length
  const textAvailable = access?.is_text_available !== false

  const submitSelection = () => {
    const selectedChunkIds = Object.keys(selectedChunks)
    if (!selectedChunkIds.length) return
    onSynthesize(question.trim() || 'What does the selected evidence establish?', selectedChunkIds)
  }

  return (
    <Tile className="corpus-reader">
      <div className="corpus-reader__heading">
        <div>
          <h3>Permitted passages</h3>
          <p>Browse the locally persisted Docling text that is available for research use under this source's page policy.</p>
        </div>
        <DocumentView size={24} aria-hidden="true" />
      </div>

      {!textAvailable && (
        <InlineNotification
          lowContrast
          kind="info"
          title="Passages unavailable"
          subtitle={access?.reason || 'This source is not available for model-assisted passage reading under its current policy.'}
        />
      )}

      {error && <InlineNotification lowContrast kind="error" title="Passage reader unavailable" subtitle={error} />}

      {loading && <p className="corpus-panel__meta">Loading permitted passages...</p>}

      {!loading && textAvailable && !error && chunks.length === 0 && (
        <p className="corpus-panel__empty">No permitted persisted passages are available for this source in the current corpus.</p>
      )}

      <div className="corpus-reader__list">
        {chunks.map((chunk) => {
          const isSelected = Boolean(selectedChunks[chunk.chunk_id])
          const selectionFull = selectedCount >= MAX_SELECTED_CHUNKS && !isSelected
          return (
            <article className="corpus-reader__passage" key={chunk.chunk_id}>
              <div className="corpus-reader__passage-meta">
                <span>{pageLabel(chunk)}</span>
                {chunk.source_section && <span>{chunk.source_section}</span>}
              </div>
              <p>{chunk.text}</p>
              <Checkbox
                id={`select-${chunk.chunk_id}`}
                labelText="Select for synthesis"
                checked={isSelected}
                disabled={selectionFull}
                onChange={() => onToggleChunk(chunk)}
              />
            </article>
          )
        })}
      </div>

      {selectedCount > 0 && (
        <div className="corpus-reader__selection">
          <strong>{selectedCount} selected passage{selectedCount === 1 ? '' : 's'}</strong>
          <TextInput
            id="selected-evidence-question"
            labelText="Question for selected evidence"
            placeholder="Ask a question about these passages"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <Button renderIcon={ArrowRight} onClick={submitSelection}>Synthesize selected evidence</Button>
        </div>
      )}
    </Tile>
  )
}

export default DocumentChunkReader