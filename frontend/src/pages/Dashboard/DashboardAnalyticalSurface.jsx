import * as d3 from 'd3'
import { Checkmark, InProgress, WarningAlt } from '@carbon/icons-react'
import { createElement, useEffect, useRef } from 'react'
import { carbonColors } from '../../utils/carbonD3Theme'
import { createVisualizationTooltip, hideVisualizationTooltip, removeVisualizationTooltip, showVisualizationTooltip } from '../../utils/d3Tooltip'

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

const AnalyticalState = ({ children }) => <p className="dashboard__analytical-state">{children}</p>

const useAnalyticalTooltip = (className) => {
  const tooltipRef = useRef(null)

  useEffect(() => {
    const tooltip = createVisualizationTooltip(className)
    tooltipRef.current = tooltip

    return () => {
      removeVisualizationTooltip(tooltip)
      tooltipRef.current = null
    }
  }, [className])

  return tooltipRef
}

const CorpusComposition = ({ composition }) => {
  const tooltipRef = useAnalyticalTooltip('dashboard-composition-tooltip')
  const hasData = composition && Number(composition.current_assets) > 0

  if (!hasData) {
    return (
      <ChartPanel title="Corpus composition" subtitle="Current archive assets, classified by controlled ingestion status.">
        <AnalyticalState>No corpus-composition data are available for the current analytical surface.</AnalyticalState>
      </ChartPanel>
    )
  }

  const segments = [
    { label: 'Controlled-ingestible sources', value: composition.controlled_ingestible_sources, color: carbonColors.primary.teal, swatch: 'controlled' },
    { label: 'Source-format anomalies', value: composition.source_format_anomalies, color: carbonColors.status.warning, swatch: 'anomaly' },
    { label: 'ML-excluded assets', value: composition.ml_excluded_assets, color: carbonColors.gray[50], swatch: 'excluded' },
  ]
  const pie = d3.pie().value((segment) => segment.value).sort(null)(segments)
  const arc = d3.arc().innerRadius(57).outerRadius(82).cornerRadius(2)

  return (
    <ChartPanel title="Corpus composition" subtitle="Current archive assets, classified by controlled ingestion status.">
      <div className="dashboard__composition">
        <svg viewBox="0 0 200 200" role="img" aria-label={`${composition.current_assets} current archive assets`}>
          <g transform="translate(100 100)">
            {pie.map((segment) => (
              <path
                key={segment.data.label}
                data-testid={`composition-segment-${segment.data.swatch}`}
                d={arc(segment)}
                fill={segment.data.color}
                onMouseEnter={(event) => showVisualizationTooltip(tooltipRef.current, `<strong>${segment.data.label}</strong><br/>Assets: ${segment.data.value}`, event.nativeEvent)}
                onMouseLeave={() => hideVisualizationTooltip(tooltipRef.current)}
              >
                <title>{`${segment.data.label}: ${segment.data.value} assets`}</title>
              </path>
            ))}
            <text textAnchor="middle" dy="-3" className="dashboard__donut-value">{composition.current_assets}</text>
            <text textAnchor="middle" dy="17" className="dashboard__donut-label">current assets</text>
          </g>
        </svg>
        <ul className="dashboard__chart-key">
          {segments.map((segment) => <li key={segment.label}><span className={`dashboard__chart-key-swatch dashboard__chart-key-swatch--${segment.swatch}`} /><span>{segment.label}</span><strong>{segment.value}</strong></li>)}
        </ul>
      </div>
    </ChartPanel>
  )
}

const EvidenceDensity = ({ density, currentChunks }) => {
  const tooltipRef = useAnalyticalTooltip('dashboard-density-tooltip')

  if (!Array.isArray(density) || density.length === 0) {
    return (
      <ChartPanel title="Evidence density" subtitle="Highest current searchable chunk counts by source document.">
        <AnalyticalState>No evidence-density data are available for the current analytical surface.</AnalyticalState>
      </ChartPanel>
    )
  }

  const highestCount = Math.max(...density.map((document) => document.chunk_count), 1)

  return (
    <ChartPanel title="Evidence density" subtitle="Highest current searchable chunk counts by source document.">
      <div className="dashboard__density-total"><strong>{numberFormat.format(currentChunks)}</strong><span>current chunks across 95 controlled-ingestible sources</span></div>
      <div className="dashboard__density-list">
        {density.slice(0, 10).map((document) => (
          <div
            className="dashboard__density-row"
            key={document.document_id}
            data-testid="evidence-density-row"
            onMouseEnter={(event) => showVisualizationTooltip(tooltipRef.current, `<strong>${document.title}</strong><br/>Current frozen-corpus chunks: ${numberFormat.format(document.chunk_count)}`, event.nativeEvent)}
            onMouseLeave={() => hideVisualizationTooltip(tooltipRef.current)}
          >
            <span className="dashboard__density-label">{document.title}</span>
            <progress className="dashboard__density-track" value={document.chunk_count} max={highestCount}>{document.chunk_count}</progress>
            <strong>{numberFormat.format(document.chunk_count)}</strong>
          </div>
        ))}
      </div>
    </ChartPanel>
  )
}

const CorpusAcrossTime = ({ temporal }) => {
  const tooltipRef = useAnalyticalTooltip('dashboard-timeline-tooltip')
  const bins = temporal?.bins || []

  if (bins.length === 0) {
    return (
      <ChartPanel title="Corpus across time" subtitle="Frozen current sources with an explicit publication year; no dates are inferred.">
        <AnalyticalState>No temporal distribution data are available for the current analytical surface.</AnalyticalState>
      </ChartPanel>
    )
  }

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
          return (
            <rect
              key={bin.year}
              data-testid={`timeline-bar-${bin.year}`}
              x={x}
              y={y}
              width={scaleX.bandwidth()}
              height={height - padding.bottom - y}
              className="dashboard__timeline-bar"
              onMouseEnter={(event) => showVisualizationTooltip(tooltipRef.current, `<strong>${bin.year}</strong><br/>Current sources: ${bin.document_count}`, event.nativeEvent)}
              onMouseLeave={() => hideVisualizationTooltip(tooltipRef.current)}
            >
              <title>{`${bin.year}: ${bin.document_count} current sources`}</title>
            </rect>
          )
        })}
        {tickYears.map((bin) => <text key={bin.year} x={(scaleX(bin.year) || 0) + scaleX.bandwidth() / 2} y={height - 10} textAnchor="middle" className="dashboard__timeline-label">{bin.year}</text>)}
      </svg>
    </ChartPanel>
  )
}

const ResearchEvidenceState = ({ runs, claims, claimsAvailable }) => {
  if (!runs || !claimsAvailable) {
    return (
      <ChartPanel title="Research evidence state" subtitle="Immutable run outcomes and human-authored claim positions are shown separately.">
        <AnalyticalState>Research evidence-state data are unavailable for the current analytical surface.</AnalyticalState>
      </ChartPanel>
    )
  }

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
        {runStates.map(({ label, value, icon, className }) => <div className={`dashboard__run-state dashboard__run-state--${className}`} key={label}>{createElement(icon, { size: 20 })}<strong>{value}</strong><span>{label}</span></div>)}
      </div>
      <div className="dashboard__claim-states">
        <p>Claims and evidence</p>
        {claimStates.map(({ state, count }) => <div key={state}><span className={`dashboard__claim-state dashboard__claim-state--${state}`}>{state.replace('_', ' ')}</span><strong>{count}</strong></div>)}
      </div>
      <p className="dashboard__state-note">Unresolved claims and zero-result retrieval remain scoped research conditions, not historical absence.</p>
    </ChartPanel>
  )
}

const DashboardAnalyticalSurface = ({ data, claims, claimsAvailable, status }) => {
  if (status === 'loading') {
    return <AnalyticalState>Loading analytical surface.</AnalyticalState>
  }

  if (status === 'unavailable' || !data) {
    return <AnalyticalState>Analytical surface unavailable. Current corpus-status metrics remain available, but analytical summaries could not be loaded.</AnalyticalState>
  }

  const composition = data.composition || null

  return (
    <div className="dashboard__analytical-grid">
      <CorpusComposition composition={composition} />
      <EvidenceDensity density={data.density} currentChunks={composition?.current_chunks ?? 0} />
      <CorpusAcrossTime temporal={data.temporal} />
      <ResearchEvidenceState runs={data.runs} claims={claims || []} claimsAvailable={claimsAvailable} />
    </div>
  )
}

export default DashboardAnalyticalSurface
