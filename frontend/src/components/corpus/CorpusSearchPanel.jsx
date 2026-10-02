import { Button, Select, SelectItem, Tag, TextInput, Tile } from '@carbon/react'

const CorpusSearchPanel = ({ filters, suggestions, authorityRecords, onChange, onReset }) => {
  const updateField = (field, value) => {
    onChange((current) => ({
      ...current,
      [field]: value
    }))
  }

  const suggestionGroups = [
    { label: 'Documents', items: suggestions.documents || [] },
    { label: 'Themes', items: suggestions.themes || [] },
    { label: 'Entities', items: suggestions.entities || [] }
  ].filter((group) => group.items.length > 0)

  return (
    <Tile>
      <h3>Search and filter</h3>
      <p className="corpus-panel__intro">
        Use the current document index to narrow the DDR corpus by title text, publication year, and processing state.
      </p>

      <div className="corpus-panel__stack">
        <TextInput
          id="corpus-keyword"
          labelText="Keyword or document ID"
          placeholder="Search titles, IDs, or known PID text"
          value={filters.keyword}
          onChange={(event) => updateField('keyword', event.target.value)}
        />

        <TextInput
          id="corpus-year"
          labelText="Publication year"
          placeholder="e.g. 1974"
          value={filters.year}
          onChange={(event) => updateField('year', event.target.value.replace(/[^0-9]/g, ''))}
        />

        <Select
          id="corpus-status"
          labelText="Processing status"
          value={filters.status}
          onChange={(event) => updateField('status', event.target.value)}
        >
          <SelectItem text="All statuses" value="" />
          <SelectItem text="Pending" value="pending" />
          <SelectItem text="Completed" value="completed" />
          <SelectItem text="Failed" value="failed" />
        </Select>

        <Select
          id="corpus-authority"
          labelText="Linked authority"
          value={filters.authorityId}
          onChange={(event) => updateField('authorityId', event.target.value)}
        >
          <SelectItem text="All linked authorities" value="" />
          {authorityRecords.map((authority) => (
            <SelectItem key={authority.authority_id} value={authority.authority_id} text={authority.label || authority.authority_id} />
          ))}
        </Select>

        <div className="app-actions-row app-actions-row--comfortable">
          <Button kind="secondary" onClick={onReset}>Reset filters</Button>
        </div>

        <div>
          <h4 className="corpus-panel__section-title">Autocomplete cues</h4>
          {suggestionGroups.length === 0 ? (
            <p className="corpus-panel__empty">Start typing two or more characters to see document, theme, and entity suggestions.</p>
          ) : (
            <div className="app-card-grid app-card-grid--dense">
              {suggestionGroups.map((group) => (
                <div key={group.label}>
                  <div className="corpus-panel__suggestion-label">{group.label}</div>
                  <div className="app-tag-row">
                    {group.items.map((item, index) => (
                      <Tag
                        key={`${group.label}-${item.text}-${index}`}
                        type="blue"
                        size="md"
                        onClick={() => updateField('keyword', item.text)}
                      >
                        {item.text}
                      </Tag>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <h4 className="corpus-panel__section-title">Authority context</h4>
          <p className="corpus-panel__empty">
            This filter uses exact authority links held by local source records. Authority terms provide archival context and navigation; they are not source-document evidence.
          </p>
        </div>
      </div>
    </Tile>
  )
}

export default CorpusSearchPanel