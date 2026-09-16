import apiRequest from './client'
import {
  normalizeChunkCitation,
  normalizeChunkProvenance
} from '../utils/normalizers'

export const getChunkCitation = async (chunkId) => {
  const payload = await apiRequest(`/api/provenance/chunk/${chunkId}/citation`)
  return normalizeChunkCitation(payload)
}

export const getChunkProvenance = async (chunkId) => {
  const payload = await apiRequest(`/api/provenance/chunk/${chunkId}/provenance`)
  return normalizeChunkProvenance(payload)
}

export const createProvenanceSnapshot = (payload = {}) => apiRequest('/api/provenance/snapshot/create', {
  method: 'POST',
  body: payload
})

export const getInferenceProvenance = async (inferenceId) => {
  const payload = await apiRequest(`/api/provenance/inference/${inferenceId}`)
  return payload
}

export const getTrainingProvenance = (runId) => apiRequest(`/api/provenance/training/${runId}`)