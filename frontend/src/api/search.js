import apiRequest from './client'

export const semanticSearch = (payload) => apiRequest('/api/search/semantic', {
  method: 'POST',
  body: payload
})

export const getArchiveRecordSiblings = async (documentId) => {
  const payload = await apiRequest(`/api/search/archive-record-siblings/${documentId}`)

  return {
    sourceDocument: payload?.sourceDocument || null,
    relatedDocuments: (payload?.relatedDocuments || []).map((document) => ({
      document_id: document.documentId,
      attached_media_pid: document.attachedMediaPid || null,
      archive_record_pid: document.archiveRecordPid || null,
      asset_pid: document.assetPid || null,
      source_uri: document.sourceUri || null,
      archive_record_title: document.archiveRecordTitle || null,
      title: document.title || 'Untitled document',
      year: document.year || null,
      used_for_ml: document.usedForMl ?? null,
      ml_policy_status: document.mlPolicyStatus || null,
    })),
    metadata: payload?.metadata || {}
  }
}

export const entitySearch = (params = {}) => apiRequest('/api/search/entity-search', { params })

export const autocompleteSearch = async (params = {}) => {
  const payload = await apiRequest('/api/search/autocomplete', { params })

  return {
    documents: payload?.documents || [],
    themes: payload?.themes || [],
    entities: payload?.entities || []
  }
}