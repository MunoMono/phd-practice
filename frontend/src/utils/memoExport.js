const formatCitation = (source) => {
  if (!source.citation) {
    return 'Not available from current endpoint.'
  }

  if (typeof source.citation === 'string') {
    return source.citation
  }

  const parts = [
    source.citation.title,
    source.citation.pid ? `PID: ${source.citation.pid}` : null,
    source.citation.page ? `Page: ${source.citation.page}` : null,
    source.citation.section ? `Section: ${source.citation.section}` : null,
    source.citation.publicUrl || null
  ].filter(Boolean)

  return parts.join(' | ')
}

const systemDerivedMissingnessCategories = new Set([
  'zero_retrieval',
  'insufficient_temporally_valid_evidence',
  'no_matching_authority_record',
  'no_matching_job_numbers',
  'no_matching_job_number',
  'insufficient_project_temporal_authority',
  'no_projects_with_explicit_dates_for_year',
  'no_documentary_retrieval_for_resolved_project',
  'no_documentary_retrieval_for_authority',
  'no_temporally_valid_documentary_support'
])

const validationFailureCategories = new Set([
  'parse_failure',
  'provenance_validation_failure'
])

const formatScore = (score) => Number.isFinite(score) ? score.toFixed(3) : null

const formatAuthorityContext = (item) => {
  if (item.authority_type === 'ddr_projects') {
    return `Job ${item.job_number} | ${item.title} | Funder: ${item.funder_name || 'unrecorded'} | Duration: ${item.duration_text || 'unrecorded'} | Project lead: ${item.project_lead_name || 'unrecorded'}`
  }

  if (item.authority_type === 'agent_employment') {
    return `${item.assertion} | ${item.role || 'Role unrecorded'} | ${item.tenure?.start_date || 'start unrecorded'} to ${item.tenure?.end_date || 'end unrecorded'}`
  }

  return `${item.label} | ${item.authority_type} | ${item.authority_classification || 'database authority record'}${item.description ? ` | ${item.description}` : ''}`
}

const appendSection = (lines, heading, entries) => {
  if (entries.length === 0) {
    return
  }

  lines.push('', `## ${heading}`, '', ...entries)
}

const retrievalDiagnosticLines = (diagnostics) => {
  if (!diagnostics) {
    return []
  }

  const lines = []
  if (Number.isInteger(diagnostics.result_count)) lines.push(`- Retrieved passages: ${diagnostics.result_count}`)
  if (Number.isFinite(diagnostics.min_score) && Number.isFinite(diagnostics.max_score)) lines.push(`- Lexical score range: ${formatScore(diagnostics.min_score)} to ${formatScore(diagnostics.max_score)}`)
  if (diagnostics.possible_low_recall) lines.push('- Weak lexical match or no retrieved passage was detected for this query.')
  if (diagnostics.evidence_concentration) lines.push('- Retrieved passages are concentrated in one document.')
  if (diagnostics.retrieval_redundancy) lines.push('- Multiple retrieved passages come from the same document.')
  if (diagnostics.provenance_incomplete) lines.push('- Some retrieved passages have incomplete provenance.')
  if (diagnostics.requested_years?.length > 0) lines.push(`- Requested temporal scope: ${diagnostics.requested_years.join(', ')}`)
  if (Number.isInteger(diagnostics.temporally_valid_result_count)) lines.push(`- Temporally valid retrieved passages: ${diagnostics.temporally_valid_result_count}`)
  if (diagnostics.temporal_rejections?.length > 0) lines.push(`- Temporal filtering excluded ${diagnostics.temporal_rejections.length} retrieved passage${diagnostics.temporal_rejections.length === 1 ? '' : 's'}.`)
  diagnostics.notes?.forEach((note) => lines.push(`- ${note}`))
  return lines
}

export const buildEvidenceTraceMemo = ({ trace, generatedAt = new Date() }) => {
  const generatedAtValue = trace.timestamp || generatedAt.toISOString()
  const retrieval = trace.retrieval || {}
  const sourceLines = trace.sources.length > 0
    ? trace.sources.map((source, index) => {
        const lines = [
          `### Source ${index + 1}`,
        ]
        if (Number.isInteger(source.rank)) lines.push(`- Rank: ${source.rank}`)
        if (source.title) lines.push(`- Title: ${source.title}`)
        if (source.documentId) lines.push(`- Document ID: ${source.documentId}`)
        if (source.pid) lines.push(`- PID: ${source.pid}`)
        if (source.archiveRecordPid) lines.push(`- Archive record PID: ${source.archiveRecordPid}`)
        if (source.page !== null && source.page !== undefined) lines.push(`- Page: ${source.page}${source.section ? ` / ${source.section}` : ''}`)
        if (source.chunkId) lines.push(`- Chunk ID: ${source.chunkId}`)
        if (source.score !== null && source.score !== undefined) lines.push(`- Retrieval score: ${source.score}`)
        if (source.citation) lines.push(`- Citation: ${formatCitation(source)}`)
        if (source.excerpt) lines.push(`- Excerpt: ${source.excerpt}`)
        return lines.join('\n')
      }).join('\n\n')
    : ''

  const lines = [
    '# Turin retrieval memo',
    '',
    `- Generated: ${generatedAtValue}`,
    ...(trace.queryId ? [`- Run ID: ${trace.queryId}`] : []),
    ...(trace.runStatus ? [`- Status: ${trace.runStatus}${trace.interpretativeStatus ? ` / ${trace.interpretativeStatus}` : ''}`] : []),
    '- Scope: Current Source interrogation snapshot; not a substitute for the saved experiment-run export.'
  ]

  appendSection(lines, 'Research question', trace.prompt ? [trace.prompt] : [])

  const retrievalLines = [
    ...(trace.corpusVersion ? [`- Corpus: ${trace.corpusVersion}`] : []),
    ...(trace.retrievalMethod ? [`- Retrieval method: ${trace.retrievalMethod}`] : []),
    ...(retrieval.normalised_query ? [`- Normalized query: ${retrieval.normalised_query}`] : []),
    ...(retrieval.expanded_query ? [`- Expanded query: ${retrieval.expanded_query}`] : []),
    ...(retrieval.query_expansions?.length ? [`- Query expansions: ${retrieval.query_expansions.join(', ')}`] : [])
  ]
  appendSection(lines, 'Retrieval', retrievalLines)
  appendSection(lines, 'Retrieval diagnostics', retrievalDiagnosticLines(trace.retrievalDiagnostics))
  appendSection(lines, 'Retrieved source-document evidence', sourceLines ? [sourceLines] : [])
  appendSection(lines, 'Archive / database authority context', (trace.authorityEvidence || []).map((item) => `- ${formatAuthorityContext(item)}`))

  const generatedInterpretation = [
    ...(trace.answer ? [`### Answer\n\n${trace.answer}`] : []),
    ...(trace.documentaryEvidence?.length ? ['### Documentary evidence claims', ...trace.documentaryEvidence.map((item) => `- ${item.claim} [PID ${item.pid || 'unrecorded'}, page ${item.page ?? 'unrecorded'}]`)] : []),
    ...(trace.inferences?.length ? ['### Inferences', ...trace.inferences.map((item) => `- ${item.inference}${item.confidence ? ` (${item.confidence})` : ''}`)] : []),
    ...(trace.contradictions?.length ? ['### Contradictions', ...trace.contradictions.map((item) => `- ${item.contradiction || item}`)] : [])
  ]
  appendSection(lines, 'Generated interpretation', generatedInterpretation)

  const limits = (trace.missingness || [])
    .filter((item) => !validationFailureCategories.has(item.category))
    .map((item) => [
      `- ${systemDerivedMissingnessCategories.has(item.category) ? 'System-derived' : 'Model-generated'} | Scope: ${item.scope} | Category: ${item.category}`,
      `  ${item.explanation}`,
      ...(item.follow_up_action ? [`  Follow-up action: ${item.follow_up_action}`] : [])
    ].join('\n'))
  appendSection(lines, 'Scoped evidential limits', limits)

  if (trace.inferenceProvenance) {
    const provenanceLines = [trace.inferenceProvenance.valid ? '- Valid for supplied citations; this does not establish historical truth.' : '- Requires researcher review; provenance validation does not establish historical truth.']
    if (trace.inferenceProvenance.issues?.length) provenanceLines.push(...trace.inferenceProvenance.issues.map((issue) => `- ${issue}`))
    appendSection(lines, 'Provenance validation', provenanceLines)
  }

  const validationFailure = (trace.missingness || []).find((item) => validationFailureCategories.has(item.category))
  if (validationFailure || trace.errorCode) {
    const failureLabel = trace.errorCode === 'granite_failure'
      ? 'Model runtime failure'
      : 'Generated-response validation failure'
    appendSection(lines, 'Model/output failure', [
      `- ${failureLabel}`,
      ...(validationFailure?.explanation ? [`- ${validationFailure.explanation}`] : []),
      ...(trace.errorMessage ? [`- ${trace.errorMessage}`] : [])
    ])
  }

  lines.push('', '## Methodological note', '', 'Generated interpretation is provisional and must be reviewed against the retrieved source-document evidence. Authority context is separately labelled and is not source-document evidence.')
  return lines.join('\n')
}

export const downloadMarkdown = (filename, content) => {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export const buildVisualAnalyticsMemo = ({
  filters,
  projection,
  selectedPoint,
  selectedCluster,
  generatedAt = new Date()
}) => {
  const points = projection?.points || []
  const visiblePids = [...new Set(points.map((point) => point.pid).filter(Boolean))]

  if (points.length === 0) {
    return [
      '# Visual Analytics Capability State',
      '',
      `- Date: ${generatedAt.toISOString()}`,
      `- Point type: ${filters.pointType}`,
      `- Colour by: ${filters.colorBy}`,
      `- Year range: ${filters.yearMin || 'Any'} to ${filters.yearMax || 'Any'}`,
      `- Theme filter: ${filters.theme || 'Any'}`,
      `- Source type filter: ${filters.sourceType || 'Any'}`,
      '',
      'No approved embedding/projection was available for the current filter state.',
      'No coordinates were exported.',
      'No clusters were exported.',
      'This document records capability state and filter state only; it is not an analytical interpretation.'
    ].join('\n')
  }

  const pointSection = selectedPoint
    ? [
        `## Selected point`,
        '',
        `- Title: ${selectedPoint.title || 'Unavailable'}`,
        `- PID: ${selectedPoint.pid || 'Unavailable'}`,
        `- Document ID: ${selectedPoint.documentId || 'Unavailable'}`,
        `- Chunk ID: ${selectedPoint.chunkId || 'Unavailable'}`,
        `- Cluster: ${selectedPoint.clusterLabel || 'Unavailable'}`,
        `- Year: ${selectedPoint.year || 'Unavailable'}`,
        `- Source type: ${selectedPoint.sourceType || 'unknown'}`,
        `- Excerpt: ${selectedPoint.excerpt || 'Unavailable'}`
      ].join('\n')
    : '## Selected point\n\nNo point selected.'

  const clusterSection = selectedCluster
    ? [
        `## Selected cluster`,
        '',
        `- Label: ${selectedCluster.label}`,
        `- Size: ${selectedCluster.size}`,
        `- Top terms: ${selectedCluster.topTerms?.join(', ') || 'Unavailable'}`,
        `- Year range: ${selectedCluster.yearRange?.join(' - ') || 'Unavailable'}`,
        `- Representative PIDs: ${selectedCluster.representativePids?.join(', ') || 'Unavailable'}`
      ].join('\n')
    : '## Selected cluster\n\nNo cluster selected.'

  return [
    '# Visual Analytics Memo',
    '',
    `- Date: ${generatedAt.toISOString()}`,
    `- Point type: ${filters.pointType}`,
    `- Colour by: ${filters.colorBy}`,
    `- Year range: ${filters.yearMin || 'Any'} to ${filters.yearMax || 'Any'}`,
    `- Theme filter: ${filters.theme || 'Any'}`,
    `- Source type filter: ${filters.sourceType || 'Any'}`,
    `- Visible point count: ${(projection?.points || []).length}`,
    `- Source PIDs: ${visiblePids.length > 0 ? visiblePids.join(', ') : 'None returned'}`,
    '',
    pointSection,
    '',
    clusterSection,
    '',
    '## Methodological note',
    '',
    'This memo records a visual-analytic reading of DDR archival traces. Spatial proximity should be interpreted as a prompt for archival investigation, not as proof of historical relation.'
  ].join('\n')
}

export const buildClusterMemo = ({ cluster, visiblePoints = [], generatedAt = new Date() }) => {
  return [
    '# Cluster Memo',
    '',
    `- Date: ${generatedAt.toISOString()}`,
    `- Cluster label: ${cluster?.label || 'Unavailable'}`,
    `- Size: ${cluster?.size ?? 'Unavailable'}`,
    `- Top terms: ${cluster?.topTerms?.join(', ') || 'Unavailable'}`,
    `- Year range: ${cluster?.yearRange?.join(' - ') || 'Unavailable'}`,
    `- Representative PIDs: ${cluster?.representativePids?.join(', ') || 'Unavailable'}`,
    '',
    '## Visible points',
    '',
    visiblePoints.length > 0
      ? visiblePoints.map((point) => `- ${point.title || point.id} | PID: ${point.pid || 'Unavailable'}`).join('\n')
      : 'No visible points are associated with the current cluster selection.',
    '',
    '## Methodological note',
    '',
    'This memo records a cluster-oriented visual reading of DDR archival traces and should be reviewed alongside the original archival materials.'
  ].join('\n')
}