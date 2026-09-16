import apiRequest from './client'

export const listSessions = (params = {}) => apiRequest('/api/sessions/list', { params })

export const getSession = (sessionId) => apiRequest(`/api/sessions/${sessionId}`)

export const getSessionEvidenceFlow = (sessionId) => apiRequest(`/api/sessions/${sessionId}/evidence-flow`)