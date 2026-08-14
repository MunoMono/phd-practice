import apiRequest from './client'

export const listExperimentRuns = () => apiRequest('/api/experiments')

export const getExperimentRun = (runId) => apiRequest(`/api/experiments/${runId}`)

export const saveExperimentAssessment = (runId, assessment) => apiRequest(`/api/experiments/${runId}/assessment`, { method: 'POST', body: assessment })

export const exportExperimentRunJson = (runId) => apiRequest(`/api/experiments/${runId}/export`)