import { Button, InlineNotification, Tile } from '@carbon/react'

const ConceptBridge = () => {
  return (
    <Tile className="concept-bridge">
      <div className="concept-bridge__header">
        <div>
          <h3>Concept bridge</h3>
          <p>Experimental resonance search is not active in the Turin v1 research workflow.</p>
        </div>
      </div>

      <InlineNotification
        lowContrast
        kind="warning"
        title="Inactive experimental capability"
        subtitle="This scaffold requires approved embedded traces, frozen-corpus binding, and provenance-bound retrieval. The current placeholder endpoint is not approved Turin retrieval."
      />

      <div className="concept-bridge__controls">
        <Button disabled>Experimental resonance search unavailable</Button>
      </div>
    </Tile>
  )
}

export default ConceptBridge