import apiRequest from './client'
import {
  normalizeDashboardStats,
  normalizeDocumentNetwork,
  normalizeEntityNetwork,
  normalizeTemporalTrends,
  normalizeThemeDistribution,
  normalizeUmapProjection
} from '../utils/normalizers'

export const fetchDocumentNetwork = async (params = {}) => {
  const payload = await apiRequest('/api/viz/document-network', { params })
  return normalizeDocumentNetwork(payload)
}

export const fetchThemeDistribution = async () => {
  const payload = await apiRequest('/api/viz/theme-distribution')
  return normalizeThemeDistribution(payload)
}

export const fetchTemporalTrends = async (params = {}) => {
  const payload = await apiRequest('/api/viz/temporal-trends', { params })
  return normalizeTemporalTrends(payload)
}

export const fetchEntityNetwork = async (params = {}) => {
  const payload = await apiRequest('/api/viz/entity-network', { params })
  return normalizeEntityNetwork(payload)
}

export const fetchDashboardStats = async () => {
  const payload = await apiRequest('/api/viz/dashboard-stats')
  return normalizeDashboardStats(payload)
}

export const fetchDashboardAnalyticalSurface = () => apiRequest('/api/viz/dashboard-analytical-surface')

export const refreshDashboardStats = () => apiRequest('/api/viz/refresh-stats', {
  method: 'POST'
})

export const getUmapProjection = async (params = {}) => {
  const payload = await apiRequest('/api/viz/umap', { params })
  return normalizeUmapProjection(payload)
}

export const getEmbeddingReadiness = () => apiRequest('/api/viz/embedding-readiness')

export const createEmbeddingReadinessReview = (payload) => apiRequest('/api/viz/embedding-readiness', {
  method: 'POST',
  body: payload
})

export const createAtlasCoverageMissingness = (payload) => apiRequest('/api/viz/atlas-coverage-missingness', {
  method: 'POST',
  body: payload
})