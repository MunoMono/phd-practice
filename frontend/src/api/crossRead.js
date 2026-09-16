import apiRequest from './client'

export const getCrossReadPassages = () => apiRequest('/api/cross-read/passages')

export const getCrossReadMap = () => apiRequest('/api/cross-read/map')

export const createCrossReadPassage = (payload) => apiRequest('/api/cross-read/passages', {
  method: 'POST',
  body: payload
})

export const getCrossReadPassage = (passageId) => apiRequest(`/api/cross-read/passages/${passageId}`)

export const updateCrossReadPassage = (passageId, payload) => apiRequest(`/api/cross-read/passages/${passageId}`, {
  method: 'PATCH',
  body: payload
})

export const runCrossReadPassage = (passageId, payload = {}) => apiRequest(`/api/cross-read/passages/${passageId}/run`, {
  method: 'POST',
  body: payload
})

export const updateCrossReadMapping = (mappingId, payload) => apiRequest(`/api/cross-read/mappings/${mappingId}`, {
  method: 'PATCH',
  body: payload
})

export const nominateCrossReadMappingForMissingness = (mappingId, payload) => apiRequest(`/api/cross-read/mappings/${mappingId}/nominate-missingness`, {
  method: 'POST',
  body: payload
})

export const exportCrossReadCsv = () => apiRequest('/api/cross-read/export.csv')

export const exportCrossReadMarkdown = () => apiRequest('/api/cross-read/export.md')