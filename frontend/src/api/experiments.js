import apiRequest from './client'

export const listExperimentRuns = () => apiRequest('/api/experiments')

export const interrogateTurin = (researchQuestion, options = {}) => apiRequest('/api/experiments/interrogate', {
	method: 'POST',
	body: {
		research_question: researchQuestion,
		...options
	}
})

export const interrogateExploratory = (query, options = {}) => apiRequest('/api/analysis/interrogate', {
	method: 'POST',
	timeoutMs: 1200000,
	body: {
		query,
		mode: 'exploratory',
		...options
	}
})

export const retrieveExploratoryV3 = (query, options = {}) => apiRequest('/api/analysis/retrieve?v=3', {
	method: 'POST',
	body: {
		query,
		mode: 'exploratory',
		...options
	}
})

export const getExperimentRun = (runId) => apiRequest(`/api/experiments/${runId}`)

export const getResearcherUiCapture = (captureId) => apiRequest(`/api/analysis/interrogate/captures/${captureId}`)

export const saveExperimentAssessment = (runId, assessment) => apiRequest(`/api/experiments/${runId}/assessment`, { method: 'POST', body: assessment })

export const exportExperimentRunJson = (runId) => apiRequest(`/api/experiments/${runId}/export`)