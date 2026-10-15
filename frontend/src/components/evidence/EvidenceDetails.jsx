import { Accordion, AccordionItem } from '@carbon/react'

const meaningful = (value) => value !== null && value !== undefined && value !== ''
  && (typeof value !== 'object' || Object.values(value).some(meaningful))
const label = (key) => key.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2')
export const DiagnosticValue = ({ value }) => {
  if (Array.isArray(value)) return <ul>{value.filter(meaningful).map((item, index) => <li key={index}><DiagnosticValue value={item} /></li>)}</ul>
  if (value && typeof value === 'object') return <dl>{Object.entries(value).filter(([, item]) => meaningful(item)).map(([key, item]) => (
    <div key={key}><dt>{label(key)}</dt><dd><DiagnosticValue value={item} /></dd></div>
  ))}</dl>
  return <span>{typeof value === 'boolean' ? value ? 'Yes' : 'No' : String(value)}</span>
}

const EvidenceDetails = ({ trace, presentation, diagnosticItems = [] }) => {
  if (!trace) return null
  const sections = [
    ['Provenance details', {
      'Source provenance': trace.sourceProvenance,
      'Archival metadata associations': trace.archivalAssociations,
      'Typed evidence ledger': trace.evidenceLedger,
      'Authority provenance': trace.authorityProvenance,
      'Authority boundaries': trace.authorityBoundaries,
      'Role reconciliation': trace.roleReconciliation,
      'Diagnostic authority evidence': trace.diagnosticAuthorityEvidence,
      'Source groups': trace.sourceGroups?.map((group) => Object.fromEntries(Object.entries(group).filter(([key]) => key !== 'chunks'))),
    }],
    ['Retrieval diagnostics', {
      'Summary': diagnosticItems,
      'Diagnostics': trace.retrievalDiagnostics,
      'Retrieval': trace.retrieval,
      'Retrieval v3': trace.retrievalV3,
      'Comparison': trace.comparison && {
        convergences: trace.comparison.convergences,
        differences_or_tensions: trace.comparison.differences_or_tensions,
        evidence_limits: trace.comparison.evidence_limits,
        documents: [trace.comparison.document_a, trace.comparison.document_b].filter(Boolean).map((document) => Object.fromEntries(
          Object.entries(document).filter(([key]) => key !== 'evidence'),
        )),
      },
    }],
    ['Claim support and evidential limits', {
      'Citation warnings': presentation.warnings,
      'Model-claim provenance': trace.claimProvenanceResult,
      'Claim assessments': trace.claimValidation,
      'Individual claim provenance': trace.claimProvenance,
      'Documentary claims': trace.documentaryEvidence?.map((item) => Object.fromEntries(Object.entries(item).filter(([key]) => !['text', 'excerpt'].includes(key)))),
      'Testimony claims': trace.testimonyEvidence?.map((item) => Object.fromEntries(Object.entries(item).filter(([key]) => !['text', 'excerpt'].includes(key)))),
      'Diagnostic documentary claims': trace.diagnosticDocumentaryEvidence?.map((item) => Object.fromEntries(Object.entries(item).filter(([key]) => !['text', 'excerpt'].includes(key)))),
      'Model interpretation': trace.inferences,
      'Contradictions': trace.contradictions,
      'Evidential limits': trace.evidentialLimits,
      'Scoped missingness': trace.missingness,
      'Missingness decision': trace.missingnessDecision,
      'Capture-derived boundaries': trace.captureDerivedLimits,
      'Capture audit': trace.captureAuditSummary,
      'Caveats': trace.caveats,
    }],
    ['Research execution', {
      'Model': trace.model,
      'Actual inference execution': trace.stageExecution,
      'Answer origin': trace.answerOrigin,
      'Answer state': trace.answerState,
      'Run status': trace.runStatus,
      'Interpretative status': trace.interpretativeStatus,
      'Synthesis failure': trace.synthesisFailure,
      'Pipeline failure': trace.pipelineFailure,
      'Error': trace.errorMessage,
      'Error code': trace.errorCode,
      'Format violations': trace.formatViolations,
      'Authority roles': trace.authorityRoles,
      'Timestamp': trace.timestamp,
      'Run ID': trace.queryId,
    }],
  ]
  return (
    <div className="tracer__supporting-details">
      {trace.authorityEvidence?.length > 0 && (
        <details>
          <summary>Database authority context</summary>
          {trace.authorityEvidence.map((item, index) => (
            <div key={`${item.authority_id}-${index}`} id={`authority-${index + 1}`} tabIndex={-1}>
              <DiagnosticValue value={item} />
            </div>
          ))}
        </details>
      )}
      <Accordion>
        {sections.filter(([, value]) => meaningful(value)).map(([title, value]) => (
          <AccordionItem key={title} title={title}>
            <DiagnosticValue value={value} />
          </AccordionItem>
        ))}
        {trace.rawModelResponse && (
          <AccordionItem title="Original model output (immutable audit record)">
            <pre>{trace.rawModelResponse}</pre>
          </AccordionItem>
        )}
      </Accordion>
    </div>
  )
}

export default EvidenceDetails
