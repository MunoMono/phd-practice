import { chartColors } from './carbonD3Theme'

const toNumber = (value, fallback = 0) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

const toArray = (value) => {
  if (Array.isArray(value)) {
    return value
  }

  if (value === undefined || value === null) {
    return []
  }

  return [value]
}

const firstDefined = (...values) => values.find((value) => value !== undefined && value !== null && value !== '')

const parseCitationString = (value) => {
  if (!value || typeof value !== 'string') {
    return { pid: null, page: null, text: value || null }
  }

  const [pidPart, pagePart] = value.split(',').map((part) => part?.trim())
  return {
    pid: pidPart || null,
    page: pagePart?.replace(/^p\.?/i, '').trim() || null,
    text: value
  }
}

export const normalizeDocumentNetwork = (raw = {}) => {
  const nodes = toArray(raw.nodes).map((node) => ({
    id: node.id,
    pid: node.pid || null,
    title: node.title || node.name || 'Untitled document',
    pdf_count: toNumber(node.pdf_count ?? node.pdfCount),
    year: node.year || node.publication_year || null,
    themes: toArray(node.themes),
    confidence: toNumber(node.confidence),
    group: node.group || toArray(node.themes)[0] || 'uncategorized'
  }))

  const nodeLookup = new Map(nodes.map((node) => [node.id, node]))
  const links = toArray(raw.links).map((link) => ({
    source: link.source,
    target: link.target,
    weight: toNumber(link.weight ?? link.strength ?? link.value, 0.1)
  }))

  const clusterSeed = toArray(raw.clusters).map((cluster) => ({
    id: cluster.id || cluster.name || cluster.theme || 'uncategorized',
    theme: cluster.theme || cluster.name || cluster.id || 'uncategorized',
    description: cluster.description || '',
    color: cluster.color || chartColors.query,
    documents: toArray(cluster.documents)
      .map((document) => nodeLookup.get(document.id) || document)
      .filter(Boolean)
  }))

  const groupedDocuments = nodes.reduce((accumulator, node) => {
    const key = node.group || 'uncategorized'
    accumulator[key] = accumulator[key] || []
    accumulator[key].push(node)
    return accumulator
  }, {})

  const fallbackClusters = Object.entries(groupedDocuments).map(([theme, documents]) => ({
    id: theme,
    theme,
    description: '',
    color: chartColors.query,
    documents
  }))

  const clusters = (clusterSeed.length > 0 ? clusterSeed : fallbackClusters).map((cluster) => ({
    ...cluster,
    documents: cluster.documents.length > 0
      ? cluster.documents
      : groupedDocuments[cluster.theme] || []
  }))

  return {
    nodes,
    links,
    clusters,
    metadata: {
      totalDocuments: toNumber(raw.metadata?.totalDocuments, nodes.length),
      totalLinks: toNumber(raw.metadata?.totalLinks, links.length),
      generatedAt: raw.metadata?.generatedAt || null
    }
  }
}

export const normalizeThemeDistribution = (raw = {}) => {
  const labels = toArray(raw.labels)
  const dataset = toArray(raw.datasets)[0] || {}
  const sourceThemes = toArray(raw.themes)

  const themes = sourceThemes.length > 0
    ? sourceThemes.map((theme, index) => ({
      theme: theme.theme || theme.label || `Theme ${index + 1}`,
      count: toNumber(theme.count ?? theme.value),
      color: theme.color || toArray(dataset.backgroundColor)[index] || chartColors.query
    }))
    : labels.map((label, index) => ({
      theme: label,
      count: toNumber(toArray(dataset.data)[index]),
      color: toArray(dataset.backgroundColor)[index] || chartColors.query
    }))

  return {
    themes,
    total: toNumber(raw.total, themes.reduce((sum, theme) => sum + theme.count, 0))
  }
}

export const normalizeTemporalTrends = (raw = {}) => {
  const labels = toArray(raw.labels)
  const datasets = toArray(raw.datasets)
  const sourceTrends = toArray(raw.trends)
  const documentsDataset = datasets.find((dataset) => dataset.label?.toLowerCase().includes('document')) || datasets[0] || {}
  const pdfDataset = datasets.find((dataset) => dataset.label?.toLowerCase().includes('pdf')) || datasets[1] || {}

  const trends = labels.map((label, index) => {
    const trend = sourceTrends[index] || sourceTrends.find((item) => `${item.year}` === `${label}`) || {}
    return {
      year: toNumber(trend.year ?? label, label),
      document_count: toNumber(trend.document_count ?? trend.documentCount ?? toArray(documentsDataset.data)[index]),
      pdf_count: toNumber(trend.pdf_count ?? trend.total_pdfs ?? trend.totalPdfs ?? toArray(pdfDataset.data)[index]),
      avg_confidence: toNumber(trend.avg_confidence ?? trend.avgConfidence, 0),
      themes: toArray(trend.themes)
    }
  }).filter((trend) => trend.year !== '' && trend.year !== null)

  return { trends }
}

export const normalizeEntityNetwork = (raw = {}) => ({
  nodes: toArray(raw.nodes).map((node) => ({
    id: node.id,
    entity_text: node.entity_text || node.name || 'Unknown entity',
    entity_type: node.entity_type || node.type || 'UNKNOWN',
    frequency: toNumber(node.frequency, 1),
    document_count: toNumber(node.document_count ?? node.documentCount)
  })),
  links: toArray(raw.links).map((link) => ({
    source: link.source,
    target: link.target,
    weight: toNumber(link.weight ?? link.strength ?? link.value, 1)
  })),
  metadata: raw.metadata || {}
})

export const normalizeDashboardStats = (raw = {}) => ({
  overview: {
    totalDocuments: toNumber(raw.overview?.totalDocuments),
    corpusStatus: {
      persistedDocumentCount: toNumber(raw.overview?.corpusStatus?.persistedDocumentCount),
      archiveResolvedDocumentCount: toNumber(raw.overview?.corpusStatus?.archiveResolvedDocumentCount),
      unresolvedLegacyDocumentCount: toNumber(raw.overview?.corpusStatus?.unresolvedLegacyDocumentCount),
      invariantSatisfied: raw.overview?.corpusStatus?.invariantSatisfied === true
    },
    totalPdfs: toNumber(raw.overview?.totalPdfs),
    totalPdfAssets: toNumber(raw.overview?.totalPdfAssets),
    totalPages: toNumber(raw.overview?.totalPages),
    yearRange: raw.overview?.yearRange || 'N/A'
  },
  mlProcessing: {
    documentsWithEmbeddings: toNumber(raw.mlProcessing?.documentsWithEmbeddings),
    documentsWithSummaries: toNumber(raw.mlProcessing?.documentsWithSummaries),
    documentsWithEntities: toNumber(raw.mlProcessing?.documentsWithEntities),
    avgConfidence: toNumber(raw.mlProcessing?.avgConfidence),
    completionRate: toNumber(raw.mlProcessing?.completionRate)
  },
  themes: {
    uniqueThemes: toNumber(raw.themes?.uniqueThemes)
  },
  recentActivity: toArray(raw.recentActivity).map((activity) => ({
    ...activity,
    count: toNumber(activity.count),
    avgDuration: toNumber(activity.avgDuration ?? activity.avg_duration, 0)
  })),
  lastUpdated: raw.lastUpdated || null
})

export const normalizeTrainingRun = (raw = {}) => ({
  id: raw.id || raw.run_id || raw.runId || null,
  model_name: raw.model_name || raw.modelName || 'Unknown model',
  model_type: raw.model_type || raw.modelType || null,
  base_model: raw.base_model || raw.baseModel || null,
  training_date: raw.training_date || raw.trainingDate || null,
  corpus_snapshot_id: raw.corpus_snapshot_id || raw.corpusSnapshotId || null,
  chunk_ids_used: toArray(raw.chunk_ids_used || raw.chunkIdsUsed),
  pid_distribution: raw.pid_distribution || raw.pidDistribution || {},
  temporal_distribution: raw.temporal_distribution || raw.temporalDistribution || {},
  hyperparameters: raw.hyperparameters || {},
  embedding_model_version: raw.embedding_model_version || raw.embeddingModelVersion || null,
  framework_versions: raw.framework_versions || raw.frameworkVersions || {},
  final_loss: toNumber(raw.final_loss ?? raw.finalLoss, null),
  metrics: raw.metrics || {}
})

export const normalizeSession = (raw = {}) => ({
  id: raw.id || raw.session_id || raw.sessionId || null,
  query: raw.query || raw.question || '',
  answer: raw.answer || raw.response || '',
  confidence: toNumber(raw.confidence),
  model_version: raw.model_version || raw.modelVersion || null,
  status: raw.status || 'unknown',
  retrieved_chunks: toArray(raw.retrieved_chunks || raw.retrievedChunks),
  notes: raw.notes || '',
  related_pids: toArray(raw.related_pids || raw.relatedPids)
})

export const normalizeEvidenceSource = (raw = {}) => {
  const parsedCitation = typeof raw.citation === 'string' ? parseCitationString(raw.citation) : {}

  return {
    chunkId: firstDefined(raw.chunkId, raw.chunk_id, raw.id, raw.chunk?.chunk_id) || null,
    documentId: firstDefined(raw.documentId, raw.document_id, raw.document?.document_id) || null,
    pid: firstDefined(raw.pid, parsedCitation.pid, raw.citation?.pid, raw.document?.pid) || null,
    title: firstDefined(raw.title, raw.document_title, raw.document?.title, raw.citation?.title) || null,
    page: firstDefined(raw.page, raw.source_page, raw.sourcePage, raw.citation?.page, parsedCitation.page) || null,
    section: firstDefined(raw.section, raw.source_section, raw.sourceSection, raw.citation?.section) || null,
    excerpt: firstDefined(raw.excerpt, raw.chunk_text, raw.chunkText, raw.text, raw.chunk?.text) || null,
    score: firstDefined(toNumber(raw.score, null), toNumber(raw.similarity, null), toNumber(raw.rank, null), null),
    textScore: toNumber(raw.text_score ?? raw.textScore, null),
    metadataScore: toNumber(raw.metadata_score ?? raw.metadataScore, null),
    sourceNominationScore: toNumber(raw.source_nomination_score ?? raw.sourceNominationScore, null),
    passageScore: toNumber(raw.passage_score ?? raw.passageScore, null),
    sourceNominationChannels: toArray(raw.source_nomination_channels || raw.sourceNominationChannels),
    retrievalChannels: toArray(raw.retrieval_channels || raw.retrievalChannels),
    passageEvidenceChannel: raw.passage_evidence_channel || raw.passageEvidenceChannel || null,
    metadataMatches: toArray(raw.metadata_matches || raw.metadataMatches),
    evidenceClassification: raw.evidence_classification || raw.evidenceClassification || null,
    identity: {
      recordPid: raw.archive_record_pid || raw.provenance?.archive_record_pid || null,
      mediaPid: raw.attached_media_pid || raw.pid || null,
      assetPid: raw.asset_pid || raw.provenance?.asset_pid || null,
    },
    citation: raw.citation || parsedCitation.text || null,
    provenance: raw.provenance || null,
    provenanceStatus: raw.provenanceStatus || 'unavailable',
    citationStatus: raw.citationStatus || (raw.citation ? 'loaded' : 'unavailable'),
    raw
  }
}

export const normalizeRuntimeAnalysis = (raw = {}) => {
  const sources = toArray(raw.sources || raw.context_chunks || raw.contextChunks || raw.evidence)
    .map(normalizeEvidenceSource)

  return {
    query: raw.query || '',
    answer: raw.analysis || raw.answer || raw.response || '',
    confidence: firstDefined(toNumber(raw.confidence, null), toNumber(raw.score, null), null),
    model: raw.model || raw.model_name || null,
    modelVersion: raw.modelVersion || raw.model_version || raw.model || null,
    inferenceId: raw.inferenceId || raw.inference_id || null,
    sources,
    raw
  }
}

export const normalizeEvidenceTrace = (raw = {}) => ({
  ...normalizeRuntimeAnalysis(raw),
  sessionId: raw.sessionId || raw.session_id || null
})

export const normalizeChunkCitation = (raw = {}) => ({
  chunkId: raw.chunk_id || raw.chunkId || null,
  pid: raw.pid || null,
  title: raw.title || null,
  year: raw.year || null,
  creator: raw.creator || null,
  institution: raw.institution || null,
  page: raw.page || null,
  section: raw.section || null,
  publicUrl: raw.public_url || raw.publicUrl || null,
  rights: raw.rights || null,
  excerpt: raw.excerpt || null,
  extractionDate: raw.extraction_date || raw.extractionDate || null,
  raw
})

export const normalizeChunkProvenance = (raw = {}) => ({
  chunk: {
    chunkId: raw.chunk?.chunk_id || null,
    text: raw.chunk?.text || null,
    page: raw.chunk?.page || null,
    section: raw.chunk?.section || null,
    extractionDate: raw.chunk?.extraction_date || null
  },
  document: {
    pid: raw.document?.pid || null,
    title: raw.document?.title || null,
    year: raw.document?.year || null,
    authorityUrl: raw.document?.authority_url || null
  },
  citation: raw.citation ? normalizeChunkCitation(raw.citation) : null,
  trainingRuns: toArray(raw.training_runs).map((run) => ({
    runId: run.run_id || null,
    model: run.model || null,
    date: run.date || null
  })),
  inferencesInfluenced: toNumber(raw.inferences_influenced),
  sampleInferences: toArray(raw.sample_inferences).map((inference) => ({
    inferenceId: inference.inference_id || null,
    query: inference.query || '',
    date: inference.date || null
  })),
  raw
})

export const normalizeUmapProjection = (raw = {}) => ({
  points: toArray(raw.points).map((point, index) => ({
    id: firstDefined(point.id, point.chunkId, point.chunk_id, point.documentId, point.document_id, `point-${index}`),
    documentId: firstDefined(point.documentId, point.document_id, null),
    chunkId: firstDefined(point.chunkId, point.chunk_id, null),
    pid: firstDefined(point.pid, null),
    title: firstDefined(point.title, 'Untitled trace'),
    x: toNumber(firstDefined(point.x, point.umap_x), 0),
    y: toNumber(firstDefined(point.y, point.umap_y), 0),
    year: firstDefined(point.year, point.publication_year, null),
    sourceType: firstDefined(point.sourceType, point.source_type, 'unknown'),
    themes: toArray(firstDefined(point.themes, point.ml_themes, [])),
    entities: toArray(firstDefined(point.entities, point.ml_entities, [])),
    clusterId: firstDefined(point.clusterId, point.cluster_id, null),
    clusterLabel: firstDefined(point.clusterLabel, point.cluster_label, null),
    confidence: firstDefined(toNumber(point.confidence, null), toNumber(point.ml_confidence, null), null),
    driftScore: firstDefined(toNumber(point.driftScore, null), toNumber(point.drift_score, null), null),
    excerpt: firstDefined(point.excerpt, point.chunk_text, point.summary, null),
    evidenceSurface: {
      isIngested: Boolean(firstDefined(point.evidenceSurface?.isIngested, point.evidence_surface?.is_ingested, false)),
      hasEmbedding: Boolean(firstDefined(point.evidenceSurface?.hasEmbedding, point.evidence_surface?.has_embedding, false)),
      hasExtractedText: Boolean(firstDefined(point.evidenceSurface?.hasExtractedText, point.evidence_surface?.has_extracted_text, false)),
      hasPdf: Boolean(firstDefined(point.evidenceSurface?.hasPdf, point.evidence_surface?.has_pdf, false)),
      hasImageAssets: Boolean(firstDefined(point.evidenceSurface?.hasImageAssets, point.evidence_surface?.has_image_assets, false)),
      hasAuthorityContext: Boolean(firstDefined(point.evidenceSurface?.hasAuthorityContext, point.evidence_surface?.has_authority_context, false)),
      requiresDoclingOrOcr: Boolean(firstDefined(point.evidenceSurface?.requiresDoclingOrOcr, point.evidence_surface?.requires_docling_or_ocr, false)),
      visibilityLabel: firstDefined(point.evidenceSurface?.visibilityLabel, point.evidence_surface?.visibility_label, 'unknown_until_docling'),
      interpretationLimit: firstDefined(point.evidenceSurface?.interpretationLimit, point.evidence_surface?.interpretation_limit, null)
    },
    missingness: {
      itemFieldMissingness: firstDefined(point.missingness?.itemFieldMissingness, point.missingness?.item_field_missingness, {}),
      assetMissingness: firstDefined(point.missingness?.assetMissingness, point.missingness?.asset_missingness, {}),
      graphqlExposureMissingness: firstDefined(point.missingness?.graphqlExposureMissingness, point.missingness?.graphql_exposure_missingness, {}),
      llmEvidenceMissingness: firstDefined(point.missingness?.llmEvidenceMissingness, point.missingness?.llm_evidence_missingness, {}),
      interpretationLimits: toArray(firstDefined(point.missingness?.interpretationLimits, point.missingness?.interpretation_limits, []))
    }
  })),
  clusters: toArray(raw.clusters).map((cluster, index) => ({
    id: firstDefined(cluster.id, cluster.clusterId, cluster.cluster_id, `cluster-${index}`),
    label: firstDefined(cluster.label, cluster.clusterLabel, cluster.cluster_label, 'Unlabelled cluster'),
    size: toNumber(cluster.size, 0),
    topTerms: toArray(firstDefined(cluster.topTerms, cluster.top_terms, [])),
    yearRange: toArray(firstDefined(cluster.yearRange, cluster.year_range, [])).slice(0, 2),
    representativePids: toArray(firstDefined(cluster.representativePids, cluster.representative_pids, [])),
    evidenceSurfaceSummary: {
      embeddedPoints: toNumber(firstDefined(cluster.evidenceSurfaceSummary?.embeddedPoints, cluster.evidence_surface_summary?.embedded_points), 0),
      pids: toNumber(firstDefined(cluster.evidenceSurfaceSummary?.pids, cluster.evidence_surface_summary?.pids), 0),
      withExtractedText: toNumber(firstDefined(cluster.evidenceSurfaceSummary?.withExtractedText, cluster.evidence_surface_summary?.with_extracted_text), 0),
      unknownUntilDocling: toNumber(firstDefined(cluster.evidenceSurfaceSummary?.unknownUntilDocling, cluster.evidence_surface_summary?.unknown_until_docling), 0),
      authorityContextNotExposed: toNumber(firstDefined(cluster.evidenceSurfaceSummary?.authorityContextNotExposed, cluster.evidence_surface_summary?.authority_context_not_exposed), 0)
    }
  })),
  metadata: {
    embeddingModel: firstDefined(raw.metadata?.embeddingModel, raw.metadata?.embedding_model, null),
    umapModel: firstDefined(raw.metadata?.umapModel, raw.metadata?.umap_model, null),
    projectionMethod: firstDefined(raw.metadata?.projectionMethod, raw.metadata?.projection_method, 'none'),
    projectionId: firstDefined(raw.metadata?.projectionId, raw.metadata?.projection_id, null),
    generatedAt: firstDefined(raw.metadata?.generatedAt, raw.metadata?.generated_at, null),
    pointType: firstDefined(raw.metadata?.pointType, raw.metadata?.point_type, 'chunks'),
    isDemo: Boolean(firstDefined(raw.metadata?.isDemo, raw.metadata?.is_demo, false)),
    evidenceSurfaceScope: {
      label: firstDefined(raw.metadata?.evidenceSurfaceScope?.label, raw.metadata?.evidence_surface_scope?.label, null),
      ingestedGranitePdfs: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.ingestedGranitePdfs, raw.metadata?.evidence_surface_scope?.ingested_granite_pdfs), 0),
      archiveWideRecordsFromScopedMissingnessV02: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.archiveWideRecordsFromScopedMissingnessV02, raw.metadata?.evidence_surface_scope?.archive_wide_records_from_scoped_missingness_v02), 0),
      recordsWithPdfs: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.recordsWithPdfs, raw.metadata?.evidence_surface_scope?.records_with_pdfs), 0),
      imageOnlyRecords: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.imageOnlyRecords, raw.metadata?.evidence_surface_scope?.image_only_records), 0),
      noAssetRecords: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.noAssetRecords, raw.metadata?.evidence_surface_scope?.no_asset_records), 0),
      unknownUntilDoclingRecords: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.unknownUntilDoclingRecords, raw.metadata?.evidence_surface_scope?.unknown_until_docling_records), 0),
      totalDocumentsInDb: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.totalDocumentsInDb, raw.metadata?.evidence_surface_scope?.total_documents_in_db), 0),
      documentsWithExtractedText: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.documentsWithExtractedText, raw.metadata?.evidence_surface_scope?.documents_with_extracted_text), 0),
      documentsWithEmbeddings: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.documentsWithEmbeddings, raw.metadata?.evidence_surface_scope?.documents_with_embeddings), 0),
      embeddedChunks: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.embeddedChunks, raw.metadata?.evidence_surface_scope?.embedded_chunks), 0),
      documentsRepresentedByChunks: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.documentsRepresentedByChunks, raw.metadata?.evidence_surface_scope?.documents_represented_by_chunks), 0),
      distinctPidsRepresented: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.distinctPidsRepresented, raw.metadata?.evidence_surface_scope?.distinct_pids_represented), 0),
      totalCandidates: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.totalCandidates, raw.metadata?.evidence_surface_scope?.total_candidates), 0),
      returnedPoints: toNumber(firstDefined(raw.metadata?.evidenceSurfaceScope?.returnedPoints, raw.metadata?.evidence_surface_scope?.returned_points), 0),
      scopeNote: firstDefined(raw.metadata?.evidenceSurfaceScope?.scopeNote, raw.metadata?.evidence_surface_scope?.scope_note, null)
    },
    interpretationWarnings: toArray(firstDefined(raw.metadata?.interpretationWarnings, raw.metadata?.interpretation_warnings, []))
  },
  message: firstDefined(raw.message, null)
})

export const normalizeDocument = (raw = {}) => ({
  id: raw.id || raw.document_id || raw.documentId || null,
  pid: raw.pid || null,
  attached_media_pid: raw.attached_media_pid || raw.attachedMediaPid || raw.pid || null,
  archive_record_pid: raw.archive_record_pid || raw.archiveRecordPid || null,
  asset_id: raw.asset_id || raw.assetId || null,
  asset_pid: raw.asset_pid || raw.assetPid || null,
  asset_id_or_asset_pid: raw.asset_id_or_asset_pid || raw.assetIdOrAssetPid || null,
  title: raw.title || 'Untitled document',
  authority: raw.authority || raw.authority_id || raw.authorityId || null,
  publication_year: raw.publication_year || raw.year || null,
  page_count: raw.page_count ?? raw.pageCount ?? null,
  chunk_count: toNumber(raw.chunk_count ?? raw.chunkCount, 0),
  processing_status: raw.processing_status || raw.processingStatus || raw.status || 'unknown',
  used_for_ml: raw.used_for_ml === null || raw.used_for_ml === undefined ? null : Boolean(raw.used_for_ml),
  ml_page_scope: raw.ml_page_scope || raw.mlPageScope || null,
  ml_policy_status: raw.ml_policy_status || raw.mlPolicyStatus || null,
  metadata_roles_version: raw.metadata_roles_version || raw.metadataRolesVersion || null,
  record_public_uri: raw.record_public_uri || raw.recordPublicUri || null,
  media_counts: raw.media_counts || raw.mediaCounts || {},
  ml_confidence: toNumber(raw.ml_confidence ?? raw.mlConfidence, 0),
  extracted_text: raw.extracted_text || raw.extractedText || '',
  ml_summary: raw.ml_summary || raw.mlSummary || '',
  ml_themes: toArray(raw.ml_themes || raw.mlThemes),
  ml_keywords: toArray(raw.ml_keywords || raw.mlKeywords),
  ml_entities: toArray(raw.ml_entities || raw.mlEntities)
})

export const normalizeChunk = (raw = {}) => ({
  id: raw.id || raw.chunk_id || raw.chunkId || null,
  document_id: raw.document_id || raw.documentId || null,
  pid: raw.pid || null,
  title: raw.title || raw.document_title || raw.documentTitle || 'Untitled document',
  chunk_text: raw.chunk_text || raw.chunkText || raw.excerpt || '',
  chunk_index: toNumber(raw.chunk_index ?? raw.chunkIndex, 0),
  source_page: raw.source_page || raw.page || null,
  source_section: raw.source_section || raw.section || null,
  citation: raw.citation || null,
  key_concepts: toArray(raw.key_concepts || raw.keyConcepts),
  score: toNumber(raw.score ?? raw.similarity ?? raw.relevance, 0),
  drift_score: toNumber(raw.drift_score ?? raw.driftScore, 0)
})