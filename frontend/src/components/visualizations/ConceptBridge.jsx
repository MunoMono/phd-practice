import { Button, InlineNotification, TextInput, Tile } from '@carbon/react'
import { useState } from 'react'
import { semanticSearch } from '../../api/search'

const ConceptBridge = () => {
  const [term, setTerm] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSearch = async () => {
    if (!term.trim()) {
      return
    }

    setLoading(true)
    setError('')

    try {
      const payload = await semanticSearch({ query: term, limit: 5 })
      setResults(payload || [])
    } catch (searchError) {
      setError(searchError.message || 'Concept bridge search failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Tile className="concept-bridge">
      <div className="concept-bridge__header">
        <div>
          <h3>Concept bridge</h3>
          <p>Explore tentative resonances between DDR-era traces and contemporary design research terms.</p>
        </div>
      </div>

      <InlineNotification
        lowContrast
        kind="warning"
        title="Interpretive scaffold"
        subtitle="Concept bridge requires semantic search over embedded DDR traces. Current search endpoint may be placeholder text matching."
      />

      <div className="concept-bridge__controls">
        <TextInput
          id="concept-bridge-term"
          labelText="Contemporary or DDR term"
          placeholder="e.g. participatory design"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
        />
        <Button onClick={handleSearch} disabled={!term.trim() || loading}>Find resonances</Button>
      </div>

      {error && <p>{error}</p>}

      {results.length > 0 && (
        <div className="concept-bridge__results">
          {results.map((result, index) => (
            <div key={`${result.document_id || result.pid || index}`} className="concept-bridge__result">
              <strong>{result.title || 'Untitled trace'}</strong>
              <div>PID: {result.pid || 'Unavailable'}</div>
              <div>Possible resonance: interpretive and source-backed only to the extent returned by the current endpoint.</div>
              <div>Highlights: {result.highlights?.join(' ') || 'No highlight excerpt returned.'}</div>
            </div>
          ))}
        </div>
      )}
    </Tile>
  )
}

export default ConceptBridge