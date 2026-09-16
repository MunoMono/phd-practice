import { Select, SelectItem } from '@carbon/react'

export const EVIDENCE_STATUSES = [
  'Supported',
  'Partially supported',
  'Contradicted',
  'Speculative',
  'Needs review'
]

const EvidenceStatusControl = ({ id, label = 'Validation status', value, onChange }) => {
  return (
    <Select id={id} labelText={label} value={value} onChange={(event) => onChange(event.target.value)} size="sm">
      {EVIDENCE_STATUSES.map((status) => (
        <SelectItem key={status} value={status} text={status} />
      ))}
    </Select>
  )
}

export default EvidenceStatusControl