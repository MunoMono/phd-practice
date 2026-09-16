import apiRequest from './client'

export const getClaims = () => apiRequest('/api/claims')

export const createClaim = (payload) => apiRequest('/api/claims', {
  method: 'POST',
  body: payload
})

export const getClaimDetail = (claimId) => apiRequest(`/api/claims/${claimId}`)

export const updateClaim = (claimId, payload) => apiRequest(`/api/claims/${claimId}`, {
  method: 'PATCH',
  body: payload
})

export const attachClaimEvidence = (claimId, payload) => apiRequest(`/api/claims/${claimId}/evidence`, {
  method: 'POST',
  body: payload
})

export const removeClaimEvidence = (claimId, evidenceId) => apiRequest(`/api/claims/${claimId}/evidence/${evidenceId}`, {
  method: 'DELETE'
})

export const exportClaimsCsv = () => apiRequest('/api/claims/export.csv')

export const exportClaimsMarkdown = () => apiRequest('/api/claims/export.md')