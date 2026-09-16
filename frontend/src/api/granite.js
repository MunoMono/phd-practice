import apiRequest from './client'
import { normalizeGraniteAnalysis } from '../utils/normalizers'

export const analyzeGranite = async (query, options = {}) => {
  const payload = await apiRequest('/api/granite/analyze', {
    method: 'POST',
    body: {
      query,
      ...options
    }
  })

  return normalizeGraniteAnalysis(payload)
}

export const analyzeWithGranite = (payload) => apiRequest('/api/granite/analyze', {
  method: 'POST',
  body: payload
})

export const getGraniteModelInfo = () => apiRequest('/api/granite/model-info')

export const getGraniteLoadStatus = () => apiRequest('/api/granite/load-status')

export const loadGraniteModel = (payload = {}) => apiRequest('/api/granite/load-model', {
  method: 'POST',
  body: payload
})

export const unloadGraniteModel = (payload = {}) => apiRequest('/api/granite/unload-model', {
  method: 'POST',
  body: payload
})

export const getGraniteHealth = () => apiRequest('/api/granite/health')