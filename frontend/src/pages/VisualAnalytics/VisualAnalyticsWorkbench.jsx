import { Accordion, AccordionItem, Button, InlineNotification, Search, Select, SelectItem, Slider, Tag, TextArea, TextInput, Tile } from '@carbon/react'
import { Add, DataVis_4, Renew, Save, View, WarningAlt } from '@carbon/icons-react'
import * as d3 from 'd3'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createAtlasCoverageMissingness, getSemanticNeighbourhood, getUmapProjection } from '../../api/viz'

const VIEWS = [
  ['atlas', 'Semantic Atlas'],
  ['neighbourhoods', 'Semantic Neighbourhoods'],
  ['comparative', 'Comparative Views'],
  ['temporal', 'Temporal & Documentary Change'],
  ['critical', 'Critical Inquiry'],
]

const DEFAULT_FILTERS = { pointType: 'chunks', colorBy: 'cluster', labelBy: 'none', yearMin: '', yearMax: '', theme: '', sourceType: '' }
const WORKSPACE_STORAGE_KEY = 'ddr.visual-analytics.workspace'

const readWorkspace = () => {
  try {
    return JSON.parse(sessionStorage.getItem(WORKSPACE_STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

const pointLabel = (point) => point.title || point.pid || point.id
const normalizeNeighbour = (point) => ({
  ...point,
  id: point.id || point.chunk_id || point.document_id,
  documentId: point.documentId || point.document_id,
  chunkId: point.chunkId || point.chunk_id,
  sourceType: point.sourceType || point.source_type,
})
const matchesSearch = (point, term) => !term || [point.title, point.pid, point.documentId, point.chunkId, point.sourceType, point.year, ...(point.themes || []), point.excerpt].join(' ').toLowerCase().includes(term.toLowerCase())

const pointColour = (point, colorBy, colourScale) => {
  if (colorBy === 'none') return '#8d8d8d'
  if (colorBy === 'year') return d3.interpolateYlGnBu(colourScale(point.year || 0))
  const value = colorBy === 'source_type' ? point.sourceType : colorBy === 'theme' ? point.themes?.[0] : point.clusterLabel
  return colourScale(value || 'Unlabelled')
}

const EmbeddingCanvas = ({ points, emptyMessage, dimensions, azimuth, elevation, selectedIds, searchIds, anchorId, comparisonA, comparisonB, colorBy, labelBy, onSelect, onHover }) => {
  const canvasRef = useRef(null)
  const transformRef = useRef(d3.zoomIdentity)
  const [size, setSize] = useState({ width: 800, height: 620 })

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setSize({ width: entry.contentRect.width, height: Math.max(460, entry.contentRect.height) }))
    if (canvasRef.current?.parentElement) observer.observe(canvasRef.current.parentElement)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !points.length) return undefined
    const pixelRatio = window.devicePixelRatio || 1
    canvas.width = size.width * pixelRatio
    canvas.height = size.height * pixelRatio
    canvas.style.width = `${size.width}px`
    canvas.style.height = `${size.height}px`
    const context = canvas.getContext('2d')
    const azimuthRadians = azimuth * Math.PI / 180
    const elevationRadians = elevation * Math.PI / 180
    const renderedPoints = points.map((point) => {
      if (dimensions !== '3d') return { ...point, renderX: point.x, renderY: point.y, depth: 0 }
      const rotatedX = point.x * Math.cos(azimuthRadians) - point.z * Math.sin(azimuthRadians)
      const depth = point.x * Math.sin(azimuthRadians) + point.z * Math.cos(azimuthRadians)
      return { ...point, renderX: rotatedX, renderY: point.y * Math.cos(elevationRadians) - depth * Math.sin(elevationRadians), depth }
    })
    const xExtent = d3.extent(renderedPoints, (point) => point.renderX)
    const yExtent = d3.extent(renderedPoints, (point) => point.renderY)
    const xScale = d3.scaleLinear().domain(xExtent[0] === xExtent[1] ? [xExtent[0] - 1, xExtent[1] + 1] : xExtent).range([30, size.width - 30])
    const yScale = d3.scaleLinear().domain(yExtent[0] === yExtent[1] ? [yExtent[0] - 1, yExtent[1] + 1] : yExtent).range([size.height - 30, 30])
    const values = colorBy === 'year' ? points.map((point) => point.year).filter(Number.isFinite) : [...new Set(points.map((point) => colorBy === 'source_type' ? point.sourceType : colorBy === 'theme' ? point.themes?.[0] : point.clusterLabel))]
    const colourScale = colorBy === 'year'
      ? d3.scaleLinear().domain(d3.extent(values.length ? values : [0, 1])).range([0.15, 0.9])
      : d3.scaleOrdinal(d3.schemeTableau10).domain(values)

    const draw = () => {
      const transform = transformRef.current
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
      context.clearRect(0, 0, size.width, size.height)
      context.fillStyle = '#161616'
      context.fillRect(0, 0, size.width, size.height)
      context.save()
      context.translate(transform.x, transform.y)
      context.scale(transform.k, transform.k)
      renderedPoints.forEach((point) => {
        const selected = selectedIds.includes(point.id)
        const inA = comparisonA.includes(point.id)
        const inB = comparisonB.includes(point.id)
        const searched = searchIds.includes(point.id)
        const anchored = point.id === anchorId
        context.beginPath()
        context.arc(xScale(point.renderX), yScale(point.renderY), (selected || anchored ? 5.5 : 3) + (dimensions === '3d' ? Math.max(-1, Math.min(1, point.depth)) : 0), 0, Math.PI * 2)
        context.globalAlpha = selected || anchored || searched || inA || inB || selectedIds.length === 0 ? 0.9 : 0.18
        context.fillStyle = anchored ? '#ff832b' : inA && inB ? '#a56eff' : inA ? '#42be65' : inB ? '#78a9ff' : pointColour(point, colorBy, colourScale)
        context.fill()
        if (selected || searched || anchored) {
          context.lineWidth = 2 / transform.k
          context.strokeStyle = '#ffffff'
          context.stroke()
        }
      })
      if (labelBy !== 'none') {
        renderedPoints.filter((point) => selectedIds.includes(point.id) || point.id === anchorId).forEach((point) => {
          const label = labelBy === 'year' ? String(point.year || 'Unknown') : labelBy === 'theme' ? point.themes?.[0] : labelBy === 'source' ? point.title : point.clusterLabel
          context.globalAlpha = 1
          context.fillStyle = '#f4f4f4'
          context.font = `${11 / transform.k}px IBM Plex Sans, sans-serif`
          context.fillText(label || 'Unlabelled', xScale(point.renderX) + 7 / transform.k, yScale(point.renderY) - 7 / transform.k)
        })
      }
      context.restore()
    }
    draw()
    const zoom = d3.zoom().scaleExtent([0.75, 10]).on('zoom', (event) => { transformRef.current = event.transform; draw() })
    d3.select(canvas).call(zoom)
    const locate = (event, select) => {
      const [clientX, clientY] = d3.pointer(event, canvas)
      const transform = transformRef.current
      const threshold = 12 / transform.k
      const candidate = renderedPoints.reduce((closest, point) => {
        const distance = Math.hypot(xScale(point.renderX) * transform.k + transform.x - clientX, yScale(point.renderY) * transform.k + transform.y - clientY)
        return distance < closest.distance ? { point, distance } : closest
      }, { point: null, distance: Infinity })
      if (candidate.distance < threshold * transform.k) select(candidate.point, event)
      else if (event.type === 'click') select(null, event)
    }
    const onClick = (event) => locate(event, onSelect)
    const onMove = (event) => locate(event, (point) => onHover(point))
    canvas.addEventListener('click', onClick)
    canvas.addEventListener('mousemove', onMove)
    return () => {
      canvas.removeEventListener('click', onClick)
      canvas.removeEventListener('mousemove', onMove)
      d3.select(canvas).on('.zoom', null)
    }
  }, [points, size, dimensions, azimuth, elevation, selectedIds, searchIds, anchorId, comparisonA, comparisonB, colorBy, labelBy, onSelect, onHover])

  if (!points.length) return <div className="visual-analytics-workbench__empty-map">{emptyMessage || 'No points match the current corpus scope.'}</div>
  return <canvas ref={canvasRef} className="visual-analytics-workbench__canvas" aria-label="Interactive UMAP embedding map" />
}

const VisualAnalyticsWorkbench = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const savedWorkspace = useMemo(readWorkspace, [])
  const [view, setView] = useState(() => searchParams.get('view') || savedWorkspace.view || 'atlas')
  const [filters, setFilters] = useState(() => ({ ...DEFAULT_FILTERS, ...savedWorkspace.filters }))
  const [projection, setProjection] = useState({ points: [], metadata: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState(() => savedWorkspace.search || '')
  const [selectedIds, setSelectedIds] = useState(() => savedWorkspace.selectedIds || [])
  const [hovered, setHovered] = useState(null)
  const [anchorId, setAnchorId] = useState(() => savedWorkspace.anchorId || null)
  const [neighbourCount, setNeighbourCount] = useState(() => savedWorkspace.neighbourCount || '25')
  const [embeddingNeighbours, setEmbeddingNeighbours] = useState([])
  const [comparisonA, setComparisonA] = useState(() => savedWorkspace.comparisonA || [])
  const [comparisonB, setComparisonB] = useState(() => savedWorkspace.comparisonB || [])
  const [note, setNote] = useState(() => savedWorkspace.note || '')
  const [dimensions, setDimensions] = useState(() => savedWorkspace.dimensions || '3d')
  const [azimuth, setAzimuth] = useState(() => savedWorkspace.azimuth || 25)
  const [elevation, setElevation] = useState(() => savedWorkspace.elevation || 18)
  const [panels, setPanels] = useState({ controls: true, inspector: true })

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getUmapProjection({ point_type: filters.pointType, include_missingness: true, limit: 5000 })
      .then((payload) => { if (!cancelled) setProjection(payload) })
      .catch((requestError) => { if (!cancelled) setError(requestError.message || 'The embedding projection could not be loaded.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [filters.pointType])

  useEffect(() => {
    sessionStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify({ view, filters, search, selectedIds, anchorId, neighbourCount, comparisonA, comparisonB, note, dimensions, azimuth, elevation }))
  }, [view, filters, search, selectedIds, anchorId, neighbourCount, comparisonA, comparisonB, note, dimensions, azimuth, elevation])

  const visiblePoints = useMemo(() => projection.points.filter((point) => (
    matchesSearch(point, search)
    && (!filters.yearMin || Number(point.year) >= Number(filters.yearMin))
    && (!filters.yearMax || Number(point.year) <= Number(filters.yearMax))
    && (!filters.theme || point.themes?.some((theme) => theme.toLowerCase().includes(filters.theme.toLowerCase())))
    && (!filters.sourceType || point.sourceType === filters.sourceType)
  )), [projection.points, filters, search])
  const pointById = useMemo(() => new Map(projection.points.map((point) => [point.id, point])), [projection.points])
  const selectedPoints = selectedIds.map((id) => pointById.get(id)).filter(Boolean)
  const inspectorPoint = selectedPoints[selectedPoints.length - 1] || null
  const searchIds = useMemo(() => search ? visiblePoints.map((point) => point.id) : [], [search, visiblePoints])
  const projectedNeighbours = useMemo(() => !inspectorPoint ? [] : projection.points.filter((point) => point.id !== inspectorPoint.id).map((point) => ({ ...point, projectedDistance: Math.hypot(point.x - inspectorPoint.x, point.y - inspectorPoint.y) })).sort((left, right) => left.projectedDistance - right.projectedDistance).slice(0, 8), [projection.points, inspectorPoint])
  const sourceTypes = useMemo(() => [...new Set(projection.points.map((point) => point.sourceType).filter(Boolean))].sort(), [projection.points])
  const scope = projection.metadata.evidenceSurfaceScope || {}
  const has3dProjection = projection.points.some((point) => Number.isFinite(point.z))
  const activeDimensions = dimensions === '3d' && !has3dProjection ? '2d' : dimensions

  const updateFilter = (field, value) => setFilters((current) => ({ ...current, [field]: value }))
  const selectPoint = (point, event) => {
    if (!point) { if (!(event?.shiftKey || event?.metaKey)) setSelectedIds([]); return }
    setSelectedIds((current) => event?.shiftKey || event?.metaKey ? (current.includes(point.id) ? current.filter((id) => id !== point.id) : [...current, point.id]) : [point.id])
  }
  const loadNeighbours = async () => {
    const anchor = pointById.get(anchorId) || inspectorPoint
    if (!anchor?.chunkId) return
    setError('')
    try {
      const result = await getSemanticNeighbourhood({ focal_chunk_id: anchor.chunkId, size: Number(neighbourCount) })
      setEmbeddingNeighbours((result.neighbours || []).map(normalizeNeighbour))
      setAnchorId(anchor.id)
    } catch (requestError) { setError(requestError.message || 'Embedding neighbours could not be loaded.') }
  }
  const resetWorkspace = () => { sessionStorage.removeItem(WORKSPACE_STORAGE_KEY); setFilters(DEFAULT_FILTERS); setSearch(''); setSelectedIds([]); setAnchorId(null); setEmbeddingNeighbours([]); setComparisonA([]); setComparisonB([]); setNote(''); setDimensions('3d'); setAzimuth(25); setElevation(18); setView('atlas') }
  const handoff = (path) => {
    const params = new URLSearchParams()
    if (selectedPoints[0]?.documentId) params.set(path === '/absences' || path === '/cross-readings' ? 'sourceDocumentId' : 'documentId', selectedPoints[0].documentId)
    if (selectedPoints[0]?.chunkId) params.set('chunkId', selectedPoints[0].chunkId)
    if (selectedPoints[0]?.chunkId && (path === '/absences' || path === '/cross-readings')) params.set('sourceChunkId', selectedPoints[0].chunkId)
    if (selectedPoints[0]?.pid) params.set('pid', selectedPoints[0].pid)
    if (selectedPoints.length > 1) params.set('sourceDocumentIds', selectedPoints.map((point) => point.documentId).filter(Boolean).join(','))
    navigate(`${path}?${params.toString()}`)
  }
  const exportWorkspace = () => {
    const state = { exportedAt: new Date().toISOString(), view, filters, search, selectedPoints, comparisonA, comparisonB, anchorId, neighbourCount, note, projection: projection.metadata }
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' }))
    link.download = 'visual-analytics-workspace.json'
    link.click()
    URL.revokeObjectURL(link.href)
  }

  return <main className={`visual-analytics-workbench ${!panels.controls ? 'visual-analytics-workbench--controls-collapsed' : ''} ${!panels.inspector ? 'visual-analytics-workbench--inspector-collapsed' : ''}`}>
    <header className="visual-analytics-workbench__toolbar">
      <div className="visual-analytics-workbench__title"><DataVis_4 size={24} /><span>Visual Analytics</span></div>
      <Select id="analytics-view" labelText="View" hideLabel value={view} onChange={(event) => setView(event.target.value)}>{VIEWS.map(([value, label]) => <SelectItem key={value} value={value} text={label} />)}</Select>
      <Search id="atlas-search" labelText="Search corpus" placeholder="Search corpus..." value={search} onChange={(event) => setSearch(event.target.value)} />
      <span className="visual-analytics-workbench__scope">{scope.embeddedChunks || projection.points.length} chunks | {scope.documentsWithEmbeddings || 'Unknown'} documents</span>
      <Button kind="ghost" size="sm" renderIcon={Renew} onClick={resetWorkspace}>Reset</Button>
      <Button kind="secondary" size="sm" renderIcon={Save} onClick={exportWorkspace}>Export</Button>
    </header>
    {error && <InlineNotification className="visual-analytics-workbench__notification" lowContrast kind="error" title="Visual analytics unavailable" subtitle={error} />}
    <aside className="visual-analytics-workbench__controls">
      <Button kind="ghost" size="sm" renderIcon={View} onClick={() => setPanels((current) => ({ ...current, controls: false }))}>Collapse controls</Button>
      <Accordion align="start">
        <AccordionItem title="Data and filters" open>
          <Select id="point-type" labelText="Point type" value={filters.pointType} onChange={(event) => updateFilter('pointType', event.target.value)}><SelectItem value="chunks" text="Chunks" /><SelectItem value="documents" text="Documents" /></Select>
          <TextInput id="year-min" labelText="From year" value={filters.yearMin} onChange={(event) => updateFilter('yearMin', event.target.value.replace(/[^0-9]/g, ''))} />
          <TextInput id="year-max" labelText="To year" value={filters.yearMax} onChange={(event) => updateFilter('yearMax', event.target.value.replace(/[^0-9]/g, ''))} />
          <TextInput id="theme" labelText="Theme" value={filters.theme} onChange={(event) => updateFilter('theme', event.target.value)} />
          <Select id="source-type" labelText="Source type" value={filters.sourceType} onChange={(event) => updateFilter('sourceType', event.target.value)}><SelectItem value="" text="All source types" />{sourceTypes.map((type) => <SelectItem key={type} value={type} text={type} />)}</Select>
        </AccordionItem>
        <AccordionItem title="Display" open>
          <Select id="colour-by" labelText="Colour by" value={filters.colorBy} onChange={(event) => updateFilter('colorBy', event.target.value)}><SelectItem value="none" text="None" /><SelectItem value="cluster" text="Cluster" /><SelectItem value="year" text="Year" /><SelectItem value="source_type" text="Source type" /><SelectItem value="theme" text="Theme" /></Select>
          <Select id="label-by" labelText="Label selected points by" value={filters.labelBy} onChange={(event) => updateFilter('labelBy', event.target.value)}><SelectItem value="none" text="None" /><SelectItem value="source" text="Source" /><SelectItem value="theme" text="Theme" /><SelectItem value="year" text="Year" /><SelectItem value="cluster" text="Cluster" /></Select>
        </AccordionItem>
        <AccordionItem title="Projection">
          <p>UMAP coordinates are stored, versioned projections. Parameters cannot be changed here without recomputation.</p>
          <Tag type="gray">{projection.metadata.projectionMethod || 'UMAP'}</Tag>
          <Select id="projection-dimensions" labelText="Display dimensions" value={activeDimensions} onChange={(event) => setDimensions(event.target.value)}>
            <SelectItem value="2d" text="2D" />
            <SelectItem value="3d" text={has3dProjection ? '3D' : '3D (no stored coordinate)'} disabled={!has3dProjection} />
          </Select>
          {activeDimensions === '3d' && <><Slider id="projection-azimuth" labelText="Horizontal orbit" min={-180} max={180} value={azimuth} onChange={({ value }) => setAzimuth(value)} /><Slider id="projection-elevation" labelText="Vertical orbit" min={-80} max={80} value={elevation} onChange={({ value }) => setElevation(value)} /></>}
        </AccordionItem>
        {view === 'neighbourhoods' && <AccordionItem title="Semantic neighbourhood" open>
          <Select id="neighbour-count" labelText="Embedding neighbours" value={neighbourCount} onChange={(event) => setNeighbourCount(event.target.value)}>{['5', '10', '25', '50'].map((value) => <SelectItem key={value} value={value} text={value} />)}</Select>
          <Button size="sm" onClick={loadNeighbours} disabled={!inspectorPoint?.chunkId}>Explore neighbourhood</Button>
        </AccordionItem>}
        {view === 'comparative' && <AccordionItem title="Comparison groups" open>
          <Button size="sm" kind="secondary" onClick={() => setComparisonA(selectedIds)}>Set A from selection</Button>
          <Button size="sm" kind="secondary" onClick={() => setComparisonB(selectedIds)}>Set B from selection</Button>
          <p>A: {comparisonA.length} items | B: {comparisonB.length} items | Shared: {comparisonA.filter((id) => comparisonB.includes(id)).length}</p>
        </AccordionItem>}
        {view === 'temporal' && <AccordionItem title="Temporal scope" open><p>Filter known dates using the year controls. Unknown dates remain unknown and are excluded only when a range is set.</p><Tag type="gray">Unknown dates: {projection.points.filter((point) => !point.year).length}</Tag></AccordionItem>}
        {view === 'critical' && <AccordionItem title="Critical inquiry" open><p>This visualisation represents the currently embedded evidence surface. Flagged conditions describe system representation, not historical absence.</p><Tag type="warm-gray">Image-only: {scope.imageOnlyRecords ?? 0}</Tag><Tag type="warm-gray">No asset: {scope.noAssetRecords ?? 0}</Tag></AccordionItem>}
      </Accordion>
    </aside>
    <section className="visual-analytics-workbench__map-region">
      <div className="visual-analytics-workbench__map-header"><div><h1>{VIEWS.find(([key]) => key === view)?.[1]}</h1><p>UMAP proximity is exploratory. Visual patterns are candidates for source investigation, not evidence of historical connection.</p></div><Tag type="blue">Visible: {visiblePoints.length}</Tag></div>
      {loading ? <div className="visual-analytics-workbench__empty-map">Loading embedding surface...</div> : <EmbeddingCanvas points={visiblePoints} emptyMessage={projection.message} dimensions={activeDimensions} azimuth={azimuth} elevation={elevation} selectedIds={selectedIds} searchIds={searchIds} anchorId={anchorId} comparisonA={comparisonA} comparisonB={comparisonB} colorBy={filters.colorBy} labelBy={filters.labelBy} onSelect={selectPoint} onHover={setHovered} />}
      {hovered && <div className="visual-analytics-workbench__hover">{pointLabel(hovered)}{hovered.year ? ` (${hovered.year})` : ''}</div>}
    </section>
    <aside className="visual-analytics-workbench__inspector">
      <Button kind="ghost" size="sm" renderIcon={View} onClick={() => setPanels((current) => ({ ...current, inspector: false }))}>Collapse inspector</Button>
      {!inspectorPoint ? <Tile><h2>Inspector</h2><p>Select a point to inspect source metadata, provenance context, and distinct embedding and projected neighbours.</p></Tile> : <Tile>
        <h2>{selectedPoints.length > 1 ? `${selectedPoints.length} selected items` : pointLabel(inspectorPoint)}</h2>
        {selectedPoints.length === 1 && <><p className="visual-analytics-workbench__excerpt">{inspectorPoint.excerpt || 'No excerpt is available.'}</p><dl><dt>Year</dt><dd>{inspectorPoint.year || 'Unknown'}</dd><dt>Source type</dt><dd>{inspectorPoint.sourceType || 'Unknown'}</dd><dt>PID</dt><dd>{inspectorPoint.pid || 'Unavailable'}</dd><dt>Chunk</dt><dd>{inspectorPoint.chunkId || 'Document point'}</dd><dt>Themes</dt><dd>{inspectorPoint.themes?.join(', ') || 'Unlabelled'}</dd><dt>Projection</dt><dd>{projection.metadata.projectionId || 'Current UMAP surface'}</dd></dl></>}
        <div className="visual-analytics-workbench__actions"><Button size="sm" kind="ghost" onClick={() => handoff('/sources')}>Open source</Button><Button size="sm" kind="ghost" onClick={() => handoff('/source-interrogation')}>Ask about selected sources</Button><Button size="sm" kind="ghost" onClick={() => { setAnchorId(inspectorPoint.id); setView('neighbourhoods') }}>Semantic neighbourhood</Button><Button size="sm" kind="ghost" renderIcon={Add} onClick={() => setComparisonA((current) => [...new Set([...current, ...selectedIds])])}>Add to comparison A</Button><Button size="sm" kind="ghost" onClick={() => handoff('/cross-readings')}>Cross-read</Button><Button size="sm" kind="ghost" renderIcon={WarningAlt} onClick={() => handoff('/absences')}>Record scoped absence</Button></div>
        <h3>Embedding neighbours</h3><p>Nearest passages in the original embedding space.</p><div className="visual-analytics-workbench__neighbour-list">{embeddingNeighbours.length ? embeddingNeighbours.map((point) => <button type="button" key={point.id} onClick={() => selectPoint(point)}><span>{point.title}</span><small>rank {point.rank || '-'} | {point.similarity ?? point.distance ?? 'metric unavailable'}</small></button>) : <span>Choose “Explore neighbourhood” to retrieve backend embedding neighbours.</span>}</div>
        <h3>Projected neighbours</h3><p>Spatially close points in the UMAP projection only.</p><div className="visual-analytics-workbench__neighbour-list">{projectedNeighbours.map((point) => <button type="button" key={point.id} onClick={() => selectPoint(point)}><span>{pointLabel(point)}</span><small>projected distance {point.projectedDistance.toFixed(2)}</small></button>)}</div>
      </Tile>}
    </aside>
    <section className="visual-analytics-workbench__tray">
      {!panels.controls && <Button size="sm" kind="ghost" onClick={() => setPanels((current) => ({ ...current, controls: true }))}>Show controls</Button>}
      {!panels.inspector && <Button size="sm" kind="ghost" onClick={() => setPanels((current) => ({ ...current, inspector: true }))}>Show inspector</Button>}
      <div><strong>{view === 'comparative' ? 'Comparison' : view === 'neighbourhoods' ? 'Neighbourhood' : 'Selection'}:</strong> {selectedPoints.length ? selectedPoints.slice(0, 4).map(pointLabel).join(', ') : 'No points selected'}</div>
      <TextArea id="research-note" labelText="Research observation" hideLabel placeholder="Capture an observation from the current workspace..." value={note} onChange={(event) => setNote(event.target.value)} rows={2} />
      <Button size="sm" kind="tertiary" onClick={exportWorkspace}>Export observation</Button>
    </section>
  </main>
}

export default VisualAnalyticsWorkbench