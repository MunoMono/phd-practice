import apiRequest from './client'

export const getQueryRuns = () => apiRequest('/api/query-runs')

export const getQueryRun = (queryId) => apiRequest(`/api/query-runs/${queryId}`)

export const createQueryRun = (body) => apiRequest('/api/query-runs', {
  method: 'POST',
  body
})

export const exportQueryRunJson = (queryId) => apiRequest(`/api/query-runs/${queryId}/export.json`)

export const exportQueryRunMarkdown = (queryId) => apiRequest(`/api/query-runs/${queryId}/export.md`)

export const getContentCredentialAssets = (queryId) => apiRequest(`/api/query-runs/${queryId}/content-credentials`)

export const downloadContentCredentialAsset = (queryId, assetId) => apiRequest(`/api/query-runs/${queryId}/content-credentials/${assetId}.svg`)

export const createClaimFromQueryRun = (queryId, body) => apiRequest(`/api/query-runs/${queryId}/create-claim`, {
  method: 'POST',
  body
})

export const createMissingnessEventFromQueryRun = (queryId, body = {}) => apiRequest(`/api/query-runs/${queryId}/create-missingness-event`, {
  method: 'POST',
  body
})