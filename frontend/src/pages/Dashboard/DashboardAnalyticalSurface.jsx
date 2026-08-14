import * as d3 from 'd3'
import { Checkmark, InProgress, WarningAlt } from '@carbon/icons-react'
import { carbonColors } from '../../utils/carbonD3Theme'

const numberFormat = new Intl.NumberFormat('en-GB')

const ChartPanel = ({ title, subtitle, children }) => (
  <section className="dashboard__chart-panel">
    <header className="dashboard__chart-panel-header">
      <h3>{title}</h3>
      <p>{subtitle}</p>
    </header>
    {children}
  </section>
)

const CorpusComposition = ({ composition }) => {
  const segments = [
    { label: 'Controlled-ingestible sources', value: composition.controlled_ingestible_sources, color: carbonColors.primary.teal },
    { label: 'Source-format anomalies', value: composition.source_format_anomalies, color: carbonColors.status.warning },
    { label: 'ML-excluded assets', value: composition.ml_excluded_assets, color: carbonColors.gray[50] },
  ]
  const pie = d3.pie().value((segment) => segment.value).sort(null)(segments)
  const arc = d3.arc().innerRadius(57).outerRadius(82).cornerRadius(2)

  return (
    <ChartPanel title="Corpus composition" subtitle="Current archive assets, classified by controlled ingestion status.">
      <div className="dashboard__composition">
        <svg viewBox="0 0 200 200" role="img" aria-label={`${composition.current_assets} current archive assets`}>
          <g transform="translate(100 100)">
            {pie.map((segment) => <path key={segment.data.label} d={arc(segment)} fill={segment.data.color}><title>{`${segment.data.label}: ${segment.data.value}`}</title></path>)}
            <text textAnchor="middle" dy="-3" className="dashboard__donut-value">{composition.current_assets}</text>
            <text textAnchor="middle" dy="17" className="dashboard__donut-label">current assets</text>
          </g>
        </svg>
        <ul className="dashboard__chart-key">
          {segments.map((segment) => <li key={segment.label}><span style={{ backgroundColor: segment.color }} /><span>{segment.label}</span><strong>{segment.value}</strong></li>)}
        </ul>
      </div>
    </ChartPanel>
  )
}

const EvidenceDensity = ({ density, currentChunks }) => {
  const highestCount = Math.max(...density.map((document) => document.chunk_count), 1)

  return (
    <ChartPanel title="Evidence density" subtitle="Highest current searchable chunk counts by source document.">
      <div className="dashboard__density-total"><strong>{numberFormat.format(currentChunks)}</strong><span>current chunks across 95 controlled-ingestible sources</span></div>
      <div className="dashboard__density-list">
        {density.slice(0, 10).map((document) => (
          <div className="dashboard__density-row" key={document.document_id} title={document.title}>
            <span className="dashboard__density-label">{document.title}</span>
            <div className="dashboard__density-track"><span style={{ width: `${(document.chunk_count / highestCount) * 100}%` }} /></div>
            <strong>{numberFormat.format(document.chunk_count)}</strong>
          </div>
        ))}
      </div>
    </ChartPanel>
  )
}

const CorpusAcrossTime = ({ temporal }) => {
  const bins = temporal.bins
  const maxCount = Math.max(...bins.map((bin) => bin.document_count), 1)
  const width = 460
  const height = 190
  const padding = { top: 12, right: 8, bottom: 30, left: 8 }
  const scaleX = d3.scaleBand().domain(bins.map((bin) => bin.year)).range([padding.left, width - padding.right]).paddingInner(0.18)
  const scaleY = d3.scaleLinear().domain([0, maxCount]).range([height - padding.bottom, padding.top])
  const tickYears = bins.filter((bin, index) => index === 0 || index === bins.length - 1 || bin.year % 5 === 0)

  return (
    <ChartPanel title="Corpus across time" subtitle="Frozen current sources with an explicit publication year; no dates are inferred.">
      <div className="dashboard__timeline-summary"><strong>{bins.reduce((total, bin) => total + bin.document_count, 0)}</strong><span>dated current sources</span>{temporal.undated_documents > 0 && <em>{temporal.undated_documents} undated</em>}</div>
      <svg className="dashboard__timeline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Distribution of frozen corpus documents by publication year">
        <line x1={padding.left} x2={width - padding.right} y1={height - padding.bottom} y2={height - padding.bottom} className="dashboard__timeline-axis" />
        {bins.map((bin) => {
          const x = scaleX(bin.year)
          const y = scaleY(bin.document_count)
          return <rect key={bin.year} x={x} y={y} width={scaleX.bandwidth()} height={height - padding.bottom - y} className="dashboard__timeline-bar"><title>{`${bin.year}: ${bin.document_count} documents`}</title></rect>
        })}
        {tickYears.map((bin) => <text key={bin.year} x={(scaleX(bin.year) || 0) + scaleX.bandwidth() / 2} y={height - 10} textAnchor="middle" className="dashboard__timeline-label">{bin.year}</text>)}
      </svg>
    </ChartPanel>
  )
}

const ResearchEvidenceState = ({ runs, claims }) => {
  const claimStates = ['supported', 'partially_supported', 'unresolved'].map((state) => ({
    state,
    count: claims.filter((claim) => claim.support_level === state).length,
  }))
  const runStates = [
    { label: 'Completed runs', value: runs.completed_runs, icon: Checkmark, className: 'complete' },
    { label: 'Bounded runtime failures', value: runs.bounded_failures, icon: WarningAlt, className: 'bounded' },
    { label: 'Researcher assessments', value: runs.assessed_runs, icon: InProgress, className: 'assessed' },
  ]

  return (
    <ChartPanel title="Research evidence state" subtitle="Immutable run outcomes and human-authored claim positions are shown separately.">
      <div className="dashboard__run-states">
        {runStates.map(({ label, value, icon: Icon, className }) => <div className={`dashboard__run-state dashboard__run-state--${className}`} key={label}><Icon size={20} /><strong>{value}</strong><span>{label}</span></div>)}
      </div>
      <div className="dashboard__claim-states">
        <p>Claims and evidence</p>
        {claimStates.map(({ state, count }) => <div key={state}><span className={`dashboard__claim-state dashboard__claim-state--${state}`}>{state.replace('_', ' ')}</span><strong>{count}</strong></div>)}
      </div>
      <p className="dashboard__state-note">Unresolved claims and zero-result retrieval remain scoped research conditions, not historical absence.</p>
    </ChartPanel>
  )
}

const DashboardAnalyticalSurface = ({ data, claims }) => {
  if (!data) return null

  return (
    <div className="dashboard__analytical-grid">
      <CorpusComposition composition={data.composition} />
      <EvidenceDensity density={data.density} currentChunks={data.composition.current_chunks} />
      <CorpusAcrossTime temporal={data.temporal} />
      <ResearchEvidenceState runs={data.runs} claims={claims} />
    </div>
  )
}

export default DashboardAnalyticalSurface
