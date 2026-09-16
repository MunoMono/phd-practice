import apiRequest from './client'
import { normalizeRuntimeAnalysis } from '../utils/normalizers'

export const analyzeRuntime = async (query, options = {}) => {
  const payload = await apiRequest('/api/runtime/analyze', {
    method: 'POST',
    body: {
      query,
      ...options
    }
  })

  return normalizeRuntimeAnalysis(payload)
}

export const analyzeWithRuntime = (payload) => apiRequest('/api/runtime/analyze', {
  method: 'POST',
  body: payload
})

export const getRuntimeModelInfo = () => apiRequest('/api/runtime/model-info')

export const getRuntimeLoadStatus = () => apiRequest('/api/runtime/load-status')

export const loadRuntimeModel = (payload = {}) => apiRequest('/api/runtime/load-model', {
  method: 'POST',
  body: payload
})

export const unloadRuntimeModel = (payload = {}) => apiRequest('/api/runtime/unload-model', {
  method: 'POST',
  body: payload
})

export const getRuntimeHealth = () => apiRequest('/api/runtime/health')

export const getRetrievalHealth = () => apiRequest('/api/metrics/health')