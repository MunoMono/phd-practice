import { Button, InlineNotification, Select, SelectItem, Tag, TextInput, Tile } from '@carbon/react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSemanticNeighbourhood, getUmapProjection, runCriticalProbe } from '../../api/viz'
import PanelHeader from '../layout/PanelHeader'
import PageHeader from '../layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../layout/PageGrid'
import UmapPointDetail from './UmapPointDetail'
import UmapEvidenceTable from './UmapEvidenceTable'
import UmapProjection from './UmapProjection'

const configurations = {
  neighbourhoods: {
    title: 'Semantic neighbourhoods',
    description: 'Inspect passages nearest to a focal archival trace in the completed embedding space.',
    notice: 'Computational proximity identifies passages for archival investigation; it does not establish a historical relationship.',
  },
  comparative: {
    title: 'Comparative views',
    description: 'Compare the same semantic evidence surface through authoritative metadata categories.',
    notice: 'Visual groupings and metadata overlays are prompts for comparison, not historical conclusions.',
  },
  temporal: {
    title: 'Temporal and documentary change',
    description: 'Inspect changing documentary representation across the dated portion of the embedded corpus.',
    notice: 'Temporal distribution describes the digitised corpus, not an unmediated history of DDR activity.',
  },
  critical: {
    title: 'Critical inquiry',
    description: 'Use a researcher-supplied critical lens to locate archival material for inspection.',
    notice: 'Critical lens supplied by researcher. Computational proximity indicates material for investigation, not confirmation of the proposition.',
  },
}

const probeLenses = ['feminist inquiry', 'labour and authorship', 'marginalised voices', 'institutional hierarchy', 'teaching and care', 'centre and periphery', 'custom researcher-defined inquiry']

const normalizePoint = (point) => ({
  id: point.id,
  documentId: point.document_id,
  chunkId: point.chunk_id,
  pid: point.pid,
  title: point.title,
  x: point.x ?? 0,
  y: point.y ?? 0,
  year: point.year,
  sourceType: point.source_type,
  themes: point.themes || [],
  entities: point.entities || [],
  excerpt: point.excerpt,
  sourcePage: point.source_page,
  sourceSection: point.source_section,
  similarity: point.similarity,
})

const VisualInquiryWorkspace = ({ mode }) => {
  const navigate = useNavigate()
  const configuration = configurations[mode]
  const [projection, setProjection] = useState({ points: [], metadata: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedPoint, setSelectedPoint] = useState(null)
  const [neighbourhoodSize, setNeighbourhoodSize] = useState('25')
  const [neighbourhood, setNeighbourhood] = useState([])
  const [comparisonField, setComparisonField] = useState('year')
  const [yearBoundary, setYearBoundary] = useState('')
  const [lens, setLens] = useState(probeLenses[0])
  const [concept, setConcept] = useState('')
  const [probeResults, setProbeResults] = useState([])
  const [running, setRunning] = useState(false)

  useEffect(() => {
    let cancelled = false
    getUmapProjection({ point_type: 'chunks', include_missingness: true })
      .then((data) => {
        if (!cancelled) setProjection(data)
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message || 'The completed UMAP projection could not be loaded.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const datedPoints = useMemo(() => projection.points.filter((point) => Number.isFinite(Number(point.year))), [projection.points])
  const temporalPoints = useMemo(() => {
    const boundary = Number(yearBoundary)
    return Number.isFinite(boundary) && boundary > 0
      ? datedPoints.filter((point) => Number(point.year) <= boundary)
      : datedPoints
  }, [datedPoints, yearBoundary])
  const temporalCounts = useMemo(() => Object.values(temporalPoints.reduce((counts, point) => {
    const year = String(point.year)
    counts[year] = counts[year] || { year, passages: 0 }
    counts[year].passages += 1
    return counts
  }, {})).sort((left, right) => Number(left.year) - Number(right.year)), [temporalPoints])
  const visiblePoints = mode === 'neighbourhoods' && neighbourhood.length ? neighbourhood : mode === 'critical' && probeResults.length ? probeResults : mode === 'temporal' ? temporalPoints : projection.points

  const inspectPoint = (point) => {
    setSelectedPoint(point)
    if (mode === 'neighbourhoods') setNeighbourhood([])
  }

  const runNeighbourhood = async () => {
    if (!selectedPoint?.chunkId) return
    setRunning(true)
    setError('')
    try {
      const response = await getSemanticNeighbourhood({ focal_chunk_id: selectedPoint.chunkId, size: Number(neighbourhoodSize) })
      setNeighbourhood([selectedPoint, ...response.neighbours.map(normalizePoint)])
    } catch (requestError) {
      setError(requestError.message || 'Semantic neighbours could not be loaded.')
    } finally {
      setRunning(false)
    }
  }

  const runProbe = async () => {
    const requestedConcept = concept.trim() || lens
    setRunning(true)
    setError('')
    try {
      const response = await runCriticalProbe({ concept: requestedConcept, size: Number(neighbourhoodSize) })
      setProbeResults(response.passages.map(normalizePoint))
    } catch (requestError) {
      setError(requestError.message || 'The critical concept probe could not be run.')
    } finally {
      setRunning(false)
    }
  }

  const sourceActions = selectedPoint && {
    onOpenCorpus: () => navigate(`/sources?documentId=${encodeURIComponent(selectedPoint.documentId)}`),
    onTraceEvidence: () => navigate(`/source-interrogation?chunkId=${encodeURIComponent(selectedPoint.chunkId)}`),
    onOpenAbsences: () => navigate(`/absences?sourceDocumentId=${encodeURIComponent(selectedPoint.documentId)}&sourceChunkId=${encodeURIComponent(selectedPoint.chunkId)}`),
    onOpenCrossReadings: () => navigate(`/cross-readings?sourceDocumentId=${encodeURIComponent(selectedPoint.documentId)}&sourceChunkId=${encodeURIComponent(selectedPoint.chunkId)}`),
    onCopyPid: () => navigator.clipboard?.writeText(selectedPoint.pid || ''),
    onCopyExcerpt: () => navigator.clipboard?.writeText(selectedPoint.excerpt || ''),
    onAddToMemo: () => {},
  }

  return (
    <PageGrid className="visual-inquiry-page">
      <Column>
        <PageHeader title={configuration.title} description={configuration.description} actions={<Tag type="cyan">Exploratory visual inquiry</Tag>} />
      </Column>
      <Column>
        <InlineNotification lowContrast kind="warning" title="Interpretation boundary" subtitle={configuration.notice} />
      </Column>
      {error && <Column><InlineNotification lowContrast kind="error" title="Visual inquiry unavailable" subtitle={error} /></Column>}
      <Column>
        <Tile className="visual-inquiry-page__controls">
          {mode === 'neighbourhoods' && <>
            <PanelHeader title="Focal source and neighbourhood" description="Select an embedded archival passage from the map, then retrieve its closest passages in the evaluated vector space." />
            <div className="visual-inquiry-page__control-row">
              <Select id="neighbourhood-size" labelText="Nearest passages" value={neighbourhoodSize} onChange={(event) => setNeighbourhoodSize(event.target.value)}>
                <SelectItem value="10" text="10" /><SelectItem value="25" text="25" /><SelectItem value="50" text="50" />
              </Select>
              <Button onClick={runNeighbourhood} disabled={!selectedPoint?.chunkId || running}>{running ? 'Finding passages...' : 'Inspect semantic neighbourhood'}</Button>
            </div>
          </>}
          {mode === 'comparative' && <>
            <PanelHeader title="Metadata comparison" description="Colour the shared UMAP evidence surface through available archive metadata." />
            <Select id="comparison-field" labelText="Comparison overlay" value={comparisonField} onChange={(event) => setComparisonField(event.target.value)}>
              <SelectItem value="year" text="Year" /><SelectItem value="source_type" text="Source type" /><SelectItem value="theme" text="Theme" /><SelectItem value="cluster" text="Cluster" />
            </Select>
          </>}
          {mode === 'temporal' && <>
            <PanelHeader title="Temporal documentary window" description="Filter by the latest included year, then inspect the documentary passages represented in that window." />
            <TextInput id="temporal-boundary" labelText="Include records through year" value={yearBoundary} placeholder="All dated records" onChange={(event) => setYearBoundary(event.target.value.replace(/[^0-9]/g, ''))} />
          </>}
          {mode === 'critical' && <>
            <PanelHeader title="Researcher-supplied concept probe" description="The selected lens supplies a starting point; the phrase below is embedded against the completed BGE-M3 corpus representation." />
            <div className="visual-inquiry-page__control-row">
              <Select id="critical-lens" labelText="Critical lens" value={lens} onChange={(event) => setLens(event.target.value)}>{probeLenses.map((item) => <SelectItem key={item} value={item} text={item} />)}</Select>
              <TextInput id="critical-concept" labelText="Concept or proposition" value={concept} placeholder="e.g. unacknowledged technical labour" onChange={(event) => setConcept(event.target.value)} />
              <Select id="critical-probe-size" labelText="Passages" value={neighbourhoodSize} onChange={(event) => setNeighbourhoodSize(event.target.value)}><SelectItem value="10" text="10" /><SelectItem value="25" text="25" /><SelectItem value="50" text="50" /></Select>
              <Button onClick={runProbe} disabled={running}>{running ? 'Locating evidence...' : 'Run concept probe'}</Button>
            </div>
          </>}
        </Tile>
      </Column>
      {mode === 'temporal' && <Column><Tile className="visual-inquiry-page__chart"><PanelHeader title="Documentary representation by year" description="Counts reflect embedded passages with date metadata." /><ResponsiveContainer width="100%" height={280}><BarChart data={temporalCounts}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="year" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="passages" fill="#0f62fe" /></BarChart></ResponsiveContainer></Tile></Column>}
      <Column lg={10} md={8} sm={4}>
        <Tile className="visual-inquiry-page__projection"><PanelHeader title="Inspectable evidence surface" description="Select a point to inspect its source and return to the underlying archival record." actions={<Tag type="gray">Visible: {visiblePoints.length}</Tag>} /><UmapProjection points={visiblePoints} loading={loading} errorState={error} selectedPoint={selectedPoint} highlightedTrace={null} colorBy={mode === 'comparative' ? comparisonField : 'cluster'} onSelectPoint={inspectPoint} /></Tile>
      </Column>
      <Column lg={6} md={8} sm={4}><UmapPointDetail point={selectedPoint} {...sourceActions} /></Column>
      <Column>
        <Tile className="visual-inquiry-page__results"><PanelHeader title="Visible archival evidence" description="Sort the current evidence surface and select a row to inspect its archival source." /><UmapEvidenceTable points={visiblePoints} onInspect={inspectPoint} /></Tile>
      </Column>
      {(mode === 'neighbourhoods' || mode === 'critical') && <Column lg={10} md={8} sm={4}><Tile className="visual-inquiry-page__results"><PanelHeader title={mode === 'critical' ? 'Nearest archival passages' : 'Neighbourhood evidence list'} description="Open a passage to inspect its archival evidence; similarity is computational, not historical." />{visiblePoints.slice(mode === 'neighbourhoods' ? 1 : 0).map((point) => <button className="visual-inquiry-page__result" key={point.id} type="button" onClick={() => setSelectedPoint(point)}><span>{point.title}</span><span>{point.sourcePage ? `p. ${point.sourcePage}` : 'page unavailable'}</span><span>{point.similarity?.toFixed(3) ?? 'mapped point'}</span></button>)}</Tile></Column>}
    </PageGrid>
  )
}

export default VisualInquiryWorkspace