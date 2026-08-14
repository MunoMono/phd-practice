const DEVELOPMENT_SEED_PATTERN = /development seed/i

const hasValue = (value) => {
  if (value === null || value === undefined) {
    return false
  }

  if (typeof value === 'string') {
    return value.trim().length > 0
  }

  if (Array.isArray(value)) {
    return value.length > 0
  }

  return true
}

export const isDevelopmentSeedText = (value) => typeof value === 'string' && DEVELOPMENT_SEED_PATTERN.test(value)

export const isDevelopmentSeedRecord = (record = {}) => {
  if (!record || typeof record !== 'object') {
    return false
  }

  const idFields = [
    record.claim_id,
    record.event_id,
    record.passage_id,
    record.mapping_id,
    record.query_id
  ]

  if (idFields.some((value) => typeof value === 'string' && /^dev[-_]/i.test(value))) {
    return true
  }

  if (record.source_type === 'mock_dev') {
    return true
  }

  const textFields = [
    record.claim_text,
    record.caveats,
    record.evidence,
    record.reviewer_note,
    record.passage_text,
    record.passage_label,
    record.prompt,
    record.note,
    record.excerpt,
    record.title,
    record.speaker_or_source
  ]

  return textFields.some((value) => hasValue(value) && isDevelopmentSeedText(value))
}

export const getResearchStateTag = (record) => {
  if (isDevelopmentSeedRecord(record)) {
    return { label: 'Development seed', type: 'warm-gray' }
  }

  return null
}