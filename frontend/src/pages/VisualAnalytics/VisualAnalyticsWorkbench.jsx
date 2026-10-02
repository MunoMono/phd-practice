import { Accordion, AccordionItem, Button, InlineNotification, OverflowMenu, OverflowMenuItem, Search, Select, SelectItem, Slider, Tag, TextArea, TextInput, Tile } from '@carbon/react'
import { Add, ChevronLeft, ChevronRight, DataVis_4, Download, Pause, Play, Renew, Save, View, WarningAlt } from '@carbon/icons-react'
import * as d3 from 'd3'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createAtlasCoverageMissingness, createVisualAnnotation, createVisualCohort, createVisualCriticalProbe, createVisualInquiry, getAlignedUmapStaticComparison, getProjectionFidelity, getSemanticNeighbourhood, getUmapProjection, getVisualAnnotationRevisions, getVisualCriticalProbe, getVisualInquiry, getVisualTemporalPeriods, reviseVisualAnnotation, runCriticalProbe } from '../../api/viz'
import { downloadCsv, downloadFile } from '../../utils/workbenchExport'

const VIEWS = [
  ['atlas', 'Semantic atlas'],
  ['neighbourhoods', 'Semantic neighbourhoods'],
  ['comparative', 'Comparative views'],
  ['temporal', 'Temporal and documentary change'],
  ['critical', 'Critical inquiry'],
]

const VIEW_FRAMING = {
  atlas: 'Where is everything? Browse the corpus-level projection as an exploratory representation, not a neutral map of historical reality.',
  neighbourhoods: 'What is close to this archival trace? Select a focal passage, then retrieve its nearest neighbours in the original embedding space.',
  comparative: 'How do structures differ? Compare selected groups or use metadata overlays to test how archival categories distribute across the projection.',
  temporal: 'How does the documentary representation change? Filter known dates and inspect how concentrations move across the available corpus.',
  critical: 'What becomes visible through a stated critical lens? Start with a researcher-supplied concept and inspect the returned archival passages.',
}

const DEFAULT_FILTERS = { pointType: 'chunks', colorBy: 'view', labelBy: 'none', yearMin: '', yearMax: '', theme: '', sourceType: '' }
const WORKSPACE_STORAGE_KEY = 'ddr.visual-analytics.workspace'
const NEIGHBOURHOOD_K = { min: 5, max: 50, step: 5, default: 10 }
const COLOR_MODE_LABELS = { cluster: 'Cluster', year: 'Year', source_type: 'Source type', theme: 'Theme', representation: 'Representation state', missingness: 'Missingness state', archive_authority: 'Archive authority state', database_authority: 'Database authority linkage', annotation: 'Researcher annotation status', local_density: 'Projected local visual density', documentary_file_type: 'Documentary file type', documentary_extraction: 'Documentary extraction state', documentary_rights: 'Documentary rights/access state', documentary_metadata: 'Documentary metadata completeness', documentary_text_length: 'Document text-length band', documentary_chunk_count: 'Document chunk-count band' }
const CRITICAL_LENS_PRESETS = [
  { id: 'labour-attribution', label: 'Divisions of labour, authorship, and attribution', text: 'unacknowledged technical and administrative labour, authorship, and attribution' },
  { id: 'archival-obscurity', label: 'Archival silence and obscurity', text: 'archival silence, obscurity, and uneven documentary visibility' },
  { id: 'maintenance', label: 'Technical practice, maintenance, and infrastructure', text: 'technical maintenance, infrastructure, coordination, and support work' },
  { id: 'care-disability', label: 'Disability, care, and beneficiary relations', text: 'disability, care, beneficiary relations, and design practice' },
]

const readWorkspace = () => {
  try {
    const workspace = JSON.parse(sessionStorage.getItem(WORKSPACE_STORAGE_KEY) || '{}')
    return workspace.orbitVersion >= 4 ? workspace : { ...workspace, filters: { ...workspace.filters, colorBy: 'view' } }
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

const withProjectedLocalDensity = (points) => {
  if (points.length < 2) return points.map((point) => ({ ...point, projectedLocalDensity: 0 }))
  const xExtent = d3.extent(points, (point) => point.x)
  const yExtent = d3.extent(points, (point) => point.y)
  const coordinateDiagonal = Math.hypot(xExtent[1] - xExtent[0], yExtent[1] - yExtent[0]) || 1
  const neighbourCount = Math.min(12, points.length - 1)
  return points.map((point) => {
    const averageNeighbourDistance = points.filter((candidate) => candidate.id !== point.id).map((candidate) => Math.hypot(candidate.x - point.x, candidate.y - point.y)).sort((left, right) => left - right).slice(0, neighbourCount).reduce((sum, distance) => sum + distance, 0) / neighbourCount
    return { ...point, projectedLocalDensity: coordinateDiagonal / Math.max(averageNeighbourDistance, Number.EPSILON) }
  })
}

const documentaryTextLengthBand = (value) => !Number.isFinite(value) ? 'not_exposed' : value === 0 ? 'empty text' : value <= 5000 ? '1-5,000 characters' : value <= 25000 ? '5,001-25,000 characters' : '25,001+ characters'
const documentaryChunkCountBand = (value) => !Number.isFinite(value) ? 'not_exposed' : value === 0 ? 'no chunks recorded' : value <= 10 ? '1-10 chunks' : value <= 50 ? '11-50 chunks' : '51+ chunks'

const pointColour = (point, colorBy, colourScale, viewAccent) => {
  if (colorBy === 'view') return viewAccent
  if (colorBy === 'none') return '#8d8d8d'
  if (colorBy === 'year') return d3.interpolateYlGnBu(colourScale(point.year || 0))
  if (colorBy === 'local_density') return d3.interpolateYlGnBu(colourScale(point.projectedLocalDensity || 0))
  const value = colorBy === 'source_type' ? point.sourceType
    : colorBy === 'theme' ? point.themes?.[0]
      : colorBy === 'representation' ? point.evidenceSurface?.representationState
        : colorBy === 'missingness' ? point.missingness?.status
          : colorBy === 'archive_authority' ? point.archiveAuthorityContext?.availability
            : colorBy === 'database_authority' ? point.databaseAuthorityContext?.length ? 'Linked record' : 'No linked record exposed'
              : colorBy === 'annotation' ? point.annotationState?.status || point.annotations?.status
                  : colorBy === 'documentary_file_type' ? point.documentaryForm?.fileType
                    : colorBy === 'documentary_extraction' ? point.documentaryForm?.extractionState
                      : colorBy === 'documentary_rights' ? point.documentaryForm?.rightsAccessState
                        : colorBy === 'documentary_metadata' ? point.documentaryForm?.metadataCompleteness
                          : colorBy === 'documentary_text_length' ? documentaryTextLengthBand(point.documentaryForm?.documentTextLength)
                            : colorBy === 'documentary_chunk_count' ? documentaryChunkCountBand(point.documentaryForm?.documentChunkCount)
                : point.clusterLabel
  return colourScale(value || 'Unavailable')
}

const EmbeddingCanvas = ({ points, emptyMessage, dimensions, azimuth, elevation, autoRotate, selectedIds, searchIds, anchorId, comparisonA, comparisonB, colorBy, labelBy, onSelect, onHover, onCameraChange, onOrbitStart, onClearSelection }) => {
  const canvasRef = useRef(null)
  const transformRef = useRef(d3.zoomIdentity)
  const dragRef = useRef(null)
  const callbacksRef = useRef({})
  const [size, setSize] = useState({ width: 800, height: 620 })
  callbacksRef.current = { onSelect, onHover, onCameraChange, onOrbitStart, onClearSelection }

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
    let renderedAzimuth = azimuth
    const azimuthRadians = () => renderedAzimuth * Math.PI / 180
    const elevationRadians = elevation * Math.PI / 180
    const coordinateSpan = Math.max(
      d3.max(points, (point) => Math.max(Math.abs(point.x), Math.abs(point.y), Math.abs(point.z || 0))) || 1,
      1,
    )
    const projectPoints = () => points.map((point) => {
      if (dimensions !== '3d') return { ...point, renderX: point.x, renderY: point.y, depth: 0 }
      const rotatedX = point.x * Math.cos(azimuthRadians()) - point.z * Math.sin(azimuthRadians())
      const depth = point.x * Math.sin(azimuthRadians()) + point.z * Math.cos(azimuthRadians())
      const perspective = 1 + (depth / coordinateSpan) * 0.22
      return { ...point, renderX: rotatedX * perspective, renderY: (point.y * Math.cos(elevationRadians) - depth * Math.sin(elevationRadians)) * perspective, depth }
    })
    let renderedPoints = projectPoints()
    let xScale
    let yScale
    const values = colorBy === 'year' ? points.map((point) => point.year).filter(Number.isFinite) : colorBy === 'local_density' ? points.map((point) => point.projectedLocalDensity).filter(Number.isFinite) : [...new Set(points.map((point) => colorBy === 'source_type' ? point.sourceType : colorBy === 'theme' ? point.themes?.[0] : colorBy === 'representation' ? point.evidenceSurface?.representationState : colorBy === 'missingness' ? point.missingness?.status : colorBy === 'archive_authority' ? point.archiveAuthorityContext?.availability : colorBy === 'database_authority' ? point.databaseAuthorityContext?.length ? 'Linked record' : 'No linked record exposed' : colorBy === 'annotation' ? point.annotationState?.status || point.annotations?.status : point.clusterLabel))]
    const colourScale = colorBy === 'year' || colorBy === 'local_density'
      ? d3.scaleLinear().domain(d3.extent(values.length ? values : [0, 1])).range([0.15, 0.9])
      : d3.scaleOrdinal(d3.schemeTableau10).domain(values)

    const draw = () => {
      renderedPoints = projectPoints()
      const xSpan = Math.max(d3.max(renderedPoints, (point) => Math.abs(point.renderX)) || 0, 1) * 1.08
      const ySpan = Math.max(d3.max(renderedPoints, (point) => Math.abs(point.renderY)) || 0, 1) * 1.08
      xScale = d3.scaleLinear().domain([-xSpan, xSpan]).range([30, size.width - 30])
      yScale = d3.scaleLinear().domain([-ySpan, ySpan]).range([size.height - 30, 30])
      const transform = transformRef.current
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
      context.clearRect(0, 0, size.width, size.height)
      const styles = getComputedStyle(canvas)
      context.fillStyle = styles.getPropertyValue('--atlas-canvas-background').trim() || '#ffffff'
      context.fillRect(0, 0, size.width, size.height)
      if (dimensions === '3d') {
        const projectAxis = (x, y, z) => {
          const rotatedX = x * Math.cos(azimuthRadians()) - z * Math.sin(azimuthRadians())
          const depth = x * Math.sin(azimuthRadians()) + z * Math.cos(azimuthRadians())
          const perspective = 1 + (depth / coordinateSpan) * 0.22
          return [xScale(rotatedX * perspective), yScale((y * Math.cos(elevationRadians) - depth * Math.sin(elevationRadians)) * perspective)]
        }
        const origin = projectAxis(0, 0, 0)
        const axisLength = coordinateSpan * 0.72
        ;[[axisLength, 0, 0, '#da1e28', 'x'], [0, axisLength, 0, '#24a148', 'y'], [0, 0, axisLength, '#0f62fe', 'z']].forEach(([x, y, z, colour, label]) => {
          const endpoint = projectAxis(x, y, z)
          context.beginPath()
          context.moveTo(...origin)
          context.lineTo(...endpoint)
          context.lineWidth = 1.5
          context.strokeStyle = colour
          context.globalAlpha = 0.85
          context.stroke()
          context.globalAlpha = 1
          context.fillStyle = colour
          context.font = '12px IBM Plex Sans, sans-serif'
          context.fillText(label, endpoint[0] + 5, endpoint[1] - 5)
        })
      }
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
        const depthAlpha = dimensions === '3d' ? 0.48 + ((point.depth / coordinateSpan + 1) / 2) * 0.42 : 0.9
        const focused = selected || anchored || searched || inA || inB
        context.globalAlpha = selectedIds.length === 0 ? depthAlpha : focused ? depthAlpha : 0.22
        context.fillStyle = selectedIds.length > 0 && !focused ? styles.getPropertyValue('--atlas-muted-point').trim() || '#8d8d8d' : anchored ? '#ff832b' : inA && inB ? '#a56eff' : inA ? '#42be65' : inB ? '#78a9ff' : pointColour(point, colorBy, colourScale, styles.getPropertyValue('--atlas-view-accent').trim() || '#0f62fe')
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
    let animationFrame
    let lastFrame
    const animate = (time) => {
      if (autoRotate && dimensions === '3d') {
        if (lastFrame !== undefined) {
          renderedAzimuth = ((renderedAzimuth + (time - lastFrame) * 0.012 + 180) % 360) - 180
          draw()
        }
        lastFrame = time
      }
      animationFrame = window.requestAnimationFrame(animate)
    }
    animationFrame = window.requestAnimationFrame(animate)
    const zoom = d3.zoom().filter((event) => event.type === 'wheel').scaleExtent([0.75, 10]).on('zoom', (event) => { transformRef.current = event.transform; draw() })
    d3.select(canvas).call(zoom).on('dblclick.zoom', null)
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
    const onClick = (event) => {
      if (dragRef.current?.moved || canvas.dataset.dragged === 'true') {
        canvas.dataset.dragged = 'false'
        return
      }
      locate(event, callbacksRef.current.onSelect)
    }
    const onMove = (event) => locate(event, (point) => callbacksRef.current.onHover(point ? { point, x: event.clientX, y: event.clientY } : null))
    const onDoubleClick = (event) => {
      event.preventDefault()
      callbacksRef.current.onClearSelection()
    }
    const startOrbit = (event) => {
      if (dimensions !== '3d' || event.button !== 0) return
      callbacksRef.current.onOrbitStart()
      callbacksRef.current.onCameraChange(elevation, renderedAzimuth)
      dragRef.current = { x: event.clientX, y: event.clientY, azimuth: renderedAzimuth, elevation, moved: false }
    }
    const orbit = (event) => {
      const drag = dragRef.current
      if (!drag) return
      const deltaX = event.clientX - drag.x
      const deltaY = event.clientY - drag.y
      drag.moved ||= Math.abs(deltaX) + Math.abs(deltaY) > 3
      if (drag.moved) {
        event.preventDefault()
        callbacksRef.current.onCameraChange(Math.max(-80, Math.min(80, drag.elevation - deltaY * 0.45)), ((drag.azimuth + deltaX * 0.45 + 180) % 360) - 180)
      }
    }
    const endOrbit = () => {
      if (!dragRef.current) return
      canvas.dataset.dragged = String(dragRef.current.moved)
      dragRef.current = null
    }
    canvas.addEventListener('click', onClick)
    canvas.addEventListener('mousemove', onMove)
    canvas.addEventListener('mousedown', startOrbit, true)
    canvas.addEventListener('mousemove', orbit, true)
    canvas.addEventListener('mouseup', endOrbit, true)
    canvas.addEventListener('dblclick', onDoubleClick)
    return () => {
      canvas.removeEventListener('click', onClick)
      canvas.removeEventListener('mousemove', onMove)
      canvas.removeEventListener('mousedown', startOrbit, true)
      canvas.removeEventListener('mousemove', orbit, true)
      canvas.removeEventListener('mouseup', endOrbit, true)
      canvas.removeEventListener('dblclick', onDoubleClick)
      d3.select(canvas).on('.zoom', null)
      window.cancelAnimationFrame(animationFrame)
    }
  }, [points, size, dimensions, azimuth, elevation, autoRotate, selectedIds, searchIds, anchorId, comparisonA, comparisonB, colorBy, labelBy])

  if (!points.length) return <div className="visual-analytics-workbench__empty-map">{emptyMessage || 'No points match the current corpus scope.'}</div>
  return <canvas ref={canvasRef} className="visual-analytics-workbench__canvas" aria-label="Interactive UMAP embedding map" onDoubleClickCapture={(event) => { event.preventDefault(); onClearSelection() }} />
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
  const [savedInquiryId, setSavedInquiryId] = useState(() => savedWorkspace.inquiryId || null)
  const [search, setSearch] = useState(() => savedWorkspace.search || '')
  const [selectedIds, setSelectedIds] = useState(() => savedWorkspace.selectedIds || [])
  const [hovered, setHovered] = useState(null)
  const [anchorId, setAnchorId] = useState(() => savedWorkspace.anchorId || null)
  const [neighbourhoodK, setNeighbourhoodK] = useState(() => savedWorkspace.neighbourhoodK || NEIGHBOURHOOD_K.default)
  const [neighbourhoodKValue, setNeighbourhoodKValue] = useState(() => String(savedWorkspace.neighbourhoodK || NEIGHBOURHOOD_K.default))
  const [criticalResultCount, setCriticalResultCount] = useState(() => savedWorkspace.criticalResultCount || '25')
  const [embeddingNeighbours, setEmbeddingNeighbours] = useState([])
  const [neighbourhoodResult, setNeighbourhoodResult] = useState(null)
  const [criticalConcept, setCriticalConcept] = useState(() => savedWorkspace.criticalConcept || '')
  const [criticalPresetId, setCriticalPresetId] = useState(() => savedWorkspace.criticalPresetId || '')
  const [criticalResults, setCriticalResults] = useState([])
  const [criticalProbeLabel, setCriticalProbeLabel] = useState('')
  const [criticalProbePolarity, setCriticalProbePolarity] = useState('positive')
  const [savedCriticalProbeId, setSavedCriticalProbeId] = useState(null)
  const [comparisonCriticalProbeId, setComparisonCriticalProbeId] = useState('')
  const [criticalProbeComparison, setCriticalProbeComparison] = useState(null)
  const [comparisonA, setComparisonA] = useState(() => savedWorkspace.comparisonA || [])
  const [comparisonB, setComparisonB] = useState(() => savedWorkspace.comparisonB || [])
  const [comparisonCohortA, setComparisonCohortA] = useState(() => savedWorkspace.comparisonCohortA || null)
  const [comparisonCohortB, setComparisonCohortB] = useState(() => savedWorkspace.comparisonCohortB || null)
  const [comparisonCohortNameA, setComparisonCohortNameA] = useState(() => savedWorkspace.comparisonCohortA?.name || 'Cohort A')
  const [comparisonCohortNameB, setComparisonCohortNameB] = useState(() => savedWorkspace.comparisonCohortB?.name || 'Cohort B')
  const [cohortRuleSourceType, setCohortRuleSourceType] = useState('')
  const [cohortRuleTheme, setCohortRuleTheme] = useState('')
  const [cohortRuleYearFrom, setCohortRuleYearFrom] = useState('')
  const [cohortRuleYearTo, setCohortRuleYearTo] = useState('')
  const [cohortRuleOperator, setCohortRuleOperator] = useState('and')
  const [fidelityMode, setFidelityMode] = useState(() => savedWorkspace.fidelityMode || 'off')
  const [fidelityResult, setFidelityResult] = useState(null)
  const [temporalMode, setTemporalMode] = useState(() => savedWorkspace.temporalMode || 'fixed')
  const [temporalWindowA, setTemporalWindowA] = useState(() => savedWorkspace.temporalWindowA || { from: '', to: '' })
  const [temporalWindowB, setTemporalWindowB] = useState(() => savedWorkspace.temporalWindowB || { from: '', to: '' })
  const [temporalPeriods, setTemporalPeriods] = useState([])
  const [temporalPeriodA, setTemporalPeriodA] = useState('')
  const [temporalPeriodB, setTemporalPeriodB] = useState('')
  const [alignedRunId, setAlignedRunId] = useState(() => savedWorkspace.alignedRunId || '')
  const [alignedComparison, setAlignedComparison] = useState(null)
  const selectedTemporalPeriodA = temporalPeriods.find((period) => period.period_id === temporalPeriodA)
  const selectedTemporalPeriodB = temporalPeriods.find((period) => period.period_id === temporalPeriodB)
  const [annotationType, setAnnotationType] = useState('researcher_note')
  const [annotationValue, setAnnotationValue] = useState('')
  const [annotationStatus, setAnnotationStatus] = useState('draft')
  const [savedAnnotationId, setSavedAnnotationId] = useState(null)
  const [annotationRevisions, setAnnotationRevisions] = useState([])
  const [note, setNote] = useState(() => savedWorkspace.note || '')
  const [dimensions, setDimensions] = useState('3d')
  const [azimuth, setAzimuth] = useState(() => savedWorkspace.azimuth || 25)
  const [elevation, setElevation] = useState(() => savedWorkspace.elevation || 18)
  const [autoRotate, setAutoRotate] = useState(true)
  const [panels, setPanels] = useState({ controls: true, inspector: true })

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getUmapProjection({ point_type: filters.pointType, include_missingness: true, limit: 1000 })
      .then((payload) => { if (!cancelled) setProjection(payload) })
      .catch((requestError) => { if (!cancelled) setError(requestError.message || 'The embedding projection could not be loaded.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [filters.pointType])

  useEffect(() => {
    let cancelled = false
    getVisualTemporalPeriods().then((result) => { if (!cancelled) setTemporalPeriods(result.periods || []) }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const inquiryId = searchParams.get('inquiryId')
    if (!inquiryId || inquiryId === savedInquiryId) return undefined
    let cancelled = false
    getVisualInquiry(inquiryId).then((inquiry) => {
      if (cancelled) return
      const workspace = inquiry.workspace || {}
      setSavedInquiryId(inquiry.inquiry_id)
      setView(workspace.view || inquiry.view || 'atlas')
      setFilters((current) => ({ ...current, ...workspace.filters }))
      setSearch(workspace.search || '')
      setSelectedIds(workspace.selectedIds || [])
      setAnchorId(workspace.anchorId || null)
      setNeighbourhoodK(workspace.neighbourhoodK || NEIGHBOURHOOD_K.default)
      setNeighbourhoodKValue(String(workspace.neighbourhoodK || NEIGHBOURHOOD_K.default))
      setCriticalResultCount(workspace.criticalResultCount || '25')
      setCriticalConcept(workspace.criticalConcept || '')
      setCriticalPresetId(workspace.criticalPresetId || '')
      setComparisonA(workspace.comparisonA || [])
      setComparisonB(workspace.comparisonB || [])
      setComparisonCohortA(workspace.comparisonCohortA || null)
      setComparisonCohortB(workspace.comparisonCohortB || null)
      setFidelityMode(workspace.fidelityMode || 'off')
      setTemporalMode(workspace.temporalMode || 'fixed')
      setTemporalWindowA(workspace.temporalWindowA || { from: '', to: '' })
      setTemporalWindowB(workspace.temporalWindowB || { from: '', to: '' })
      setAlignedRunId(workspace.alignedRunId || '')
      setNote(workspace.note || '')
      setDimensions(workspace.dimensions || '3d')
      setAzimuth(workspace.azimuth || 25)
      setElevation(workspace.elevation || 18)
    }).catch((requestError) => { if (!cancelled) setError(requestError.message || 'The saved visual inquiry could not be loaded.') })
    return () => { cancelled = true }
  }, [savedInquiryId, searchParams])

  useEffect(() => {
    sessionStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify({ inquiryId: savedInquiryId, view, filters, search, selectedIds, anchorId, neighbourhoodK, criticalResultCount, criticalConcept, criticalPresetId, comparisonA, comparisonB, comparisonCohortA, comparisonCohortB, fidelityMode, temporalMode, temporalWindowA, temporalWindowB, alignedRunId, note, dimensions, azimuth, elevation, autoRotate, orbitVersion: 7 }))
  }, [savedInquiryId, view, filters, search, selectedIds, anchorId, neighbourhoodK, criticalResultCount, criticalConcept, criticalPresetId, comparisonA, comparisonB, comparisonCohortA, comparisonCohortB, fidelityMode, temporalMode, temporalWindowA, temporalWindowB, alignedRunId, note, dimensions, azimuth, elevation, autoRotate])

  const visiblePoints = useMemo(() => projection.points.filter((point) => (
    matchesSearch(point, search)
    && (!filters.yearMin || Number(point.year) >= Number(filters.yearMin))
    && (!filters.yearMax || Number(point.year) <= Number(filters.yearMax))
    && (!filters.theme || point.themes?.some((theme) => theme.toLowerCase().includes(filters.theme.toLowerCase())))
    && (!filters.sourceType || point.sourceType === filters.sourceType)
  )), [projection.points, filters, search])
  const criticalPoints = useMemo(() => criticalResults.map(normalizeNeighbour), [criticalResults])
  const mapPoints = useMemo(() => {
    if (view === 'neighbourhoods' && anchorId && embeddingNeighbours.length) {
      const anchor = projection.points.find((point) => point.id === anchorId)
      return [anchor, ...embeddingNeighbours].filter(Boolean)
    }
    return view === 'critical' && criticalPoints.length ? criticalPoints : visiblePoints
  }, [anchorId, criticalPoints, embeddingNeighbours, projection.points, view, visiblePoints])
  const displayPoints = useMemo(() => filters.colorBy === 'local_density' ? withProjectedLocalDensity(mapPoints) : mapPoints, [filters.colorBy, mapPoints])
  const pointById = useMemo(() => new Map(projection.points.map((point) => [point.id, point])), [projection.points])
  const selectedPoints = selectedIds.map((id) => pointById.get(id)).filter(Boolean)
  const inspectorPoint = selectedPoints[selectedPoints.length - 1] || null
  const searchIds = useMemo(() => search ? visiblePoints.map((point) => point.id) : [], [search, visiblePoints])
  const projectedNeighbours = useMemo(() => !inspectorPoint ? [] : projection.points.filter((point) => point.id !== inspectorPoint.id).map((point) => ({ ...point, projectedDistance: Math.hypot(point.x - inspectorPoint.x, point.y - inspectorPoint.y) })).sort((left, right) => left.projectedDistance - right.projectedDistance).slice(0, 8), [projection.points, inspectorPoint])
  const sourceTypes = useMemo(() => [...new Set(projection.points.map((point) => point.sourceType).filter(Boolean))].sort(), [projection.points])
  const colorLegendValues = useMemo(() => {
    if (!COLOR_MODE_LABELS[filters.colorBy]) return []
    if (filters.colorBy === 'local_density') return ['Lower local visual density', 'Higher local visual density']
    const documentaryField = { documentary_file_type: 'fileType', documentary_extraction: 'extractionState', documentary_rights: 'rightsAccessState', documentary_metadata: 'metadataCompleteness' }[filters.colorBy]
    if (documentaryField) return [...new Set(projection.points.map((point) => point.documentaryForm?.[documentaryField] || 'not_exposed'))].sort()
    if (filters.colorBy === 'documentary_text_length') return [...new Set(projection.points.map((point) => documentaryTextLengthBand(point.documentaryForm?.documentTextLength)))].sort()
    if (filters.colorBy === 'documentary_chunk_count') return [...new Set(projection.points.map((point) => documentaryChunkCountBand(point.documentaryForm?.documentChunkCount)))].sort()
    if (filters.colorBy === 'year') return projection.points.map((point) => point.year).filter(Boolean).sort((left, right) => left - right)
    return [...new Set(projection.points.map((point) => filters.colorBy === 'source_type' ? point.sourceType : filters.colorBy === 'theme' ? point.themes?.[0] : filters.colorBy === 'representation' ? point.evidenceSurface?.representationState : filters.colorBy === 'missingness' ? point.missingness?.status : filters.colorBy === 'archive_authority' ? point.archiveAuthorityContext?.availability : filters.colorBy === 'database_authority' ? point.databaseAuthorityContext?.length ? 'Linked record' : 'No linked record exposed' : filters.colorBy === 'annotation' ? point.annotationState?.status || point.annotations?.status : point.clusterLabel).filter(Boolean))].sort()
  }, [filters.colorBy, projection.points])
  const scope = projection.metadata.evidenceSurfaceScope || {}
  const atlasUnavailable = !loading && projection.points.length === 0 && scope.embeddedChunks === 0 && scope.activeFtsChunks > 0
  const activeCorpusSummary = `${(scope.activeFtsChunks || 0).toLocaleString()} FTS chunks | ${(scope.activeFtsDocuments || 0).toLocaleString()} documents`
  const evidenceSurfaceCounts = `Eligible: ${(scope.eligibleCount ?? 0).toLocaleString()} | Represented: ${(scope.representedCount ?? 0).toLocaleString()} | Rendered: ${(scope.renderedCount ?? projection.points.length).toLocaleString()} | Visible: ${visiblePoints.length.toLocaleString()}`
  const has3dProjection = projection.points.some((point) => Number.isFinite(point.z))
  const activeDimensions = dimensions === '3d' && !has3dProjection ? '2d' : dimensions
  const fidelityChunkIds = useMemo(() => [...new Set([...comparisonA, ...comparisonB])].map((id) => pointById.get(id)?.chunkId).filter(Boolean), [comparisonA, comparisonB, pointById])
  const comparisonSourceRows = useMemo(() => [...new Set([...comparisonA, ...comparisonB])].map((id) => {
    const point = pointById.get(id)
    return point ? { point, membership: comparisonA.includes(id) && comparisonB.includes(id) ? 'A/B overlap' : comparisonA.includes(id) ? 'A' : 'B' } : null
  }).filter(Boolean), [comparisonA, comparisonB, pointById])
  const temporalSummary = useMemo(() => ({
    represented: projection.points.length,
    visible: visiblePoints.length,
    undated: projection.points.filter((point) => !point.year).length,
    excluded: projection.points.length - visiblePoints.length,
  }), [projection.points, visiblePoints])
  const temporalWindowSummary = useMemo(() => {
    const summarize = (window) => {
      const from = Number(window.from) || -Infinity
      const to = Number(window.to) || Infinity
      const dated = projection.points.filter((point) => Number.isFinite(Number(point.year)))
      return { represented: projection.points.length, inWindow: dated.filter((point) => Number(point.year) >= from && Number(point.year) <= to).length, undated: projection.points.length - dated.length }
    }
    return { a: summarize(temporalWindowA), b: summarize(temporalWindowB) }
  }, [projection.points, temporalWindowA, temporalWindowB])

  useEffect(() => {
    setAutoRotate(activeDimensions === '3d')
  }, [view, activeDimensions])

  useEffect(() => {
    if (fidelityMode !== 'show') { setFidelityResult(null); return }
    if (!fidelityChunkIds.length) { setFidelityResult({ unavailable: 'Save one or more represented cohort points before requesting fidelity.' }); return }
    let cancelled = false
    getProjectionFidelity({ focal_chunk_ids: fidelityChunkIds, neighbourhood_size: 10 })
      .then((result) => { if (!cancelled) setFidelityResult(result) })
      .catch((requestError) => { if (!cancelled) setFidelityResult({ unavailable: requestError.message || 'Projection fidelity is unavailable.' }) })
    return () => { cancelled = true }
  }, [fidelityMode, fidelityChunkIds])

  const updateFilter = (field, value) => setFilters((current) => ({ ...current, [field]: value }))
  const selectPoint = (point, event) => {
    if (!point) { if (!(event?.shiftKey || event?.metaKey)) setSelectedIds([]); return }
    setPanels((current) => ({ ...current, inspector: true }))
    setSelectedIds((current) => event?.shiftKey || event?.metaKey ? (current.includes(point.id) ? current.filter((id) => id !== point.id) : [...current, point.id]) : [point.id])
  }
  const clearSelection = () => { setSelectedIds([]); setAnchorId(null); setHovered(null); setAutoRotate(false) }
  const loadNeighbours = async () => {
    const anchor = pointById.get(anchorId) || inspectorPoint
    if (!anchor?.chunkId) return
    setError('')
    try {
      const result = await getSemanticNeighbourhood({ focal_chunk_id: anchor.chunkId, size: neighbourhoodK })
      setEmbeddingNeighbours((result.neighbours || []).map(normalizeNeighbour))
      setNeighbourhoodResult(result)
      setAnchorId(anchor.id)
    } catch (requestError) { setError(requestError.message || 'Embedding neighbours could not be loaded.') }
  }
  const refocusNeighbour = async (point) => {
    if (!point?.chunkId) return
    setError('')
    setAnchorId(point.id)
    setSelectedIds([point.id])
    try {
      const result = await getSemanticNeighbourhood({ focal_chunk_id: point.chunkId, size: neighbourhoodK })
      setEmbeddingNeighbours((result.neighbours || []).map(normalizeNeighbour))
      setNeighbourhoodResult(result)
    } catch (requestError) { setError(requestError.message || 'The selected neighbour could not become the focal trace.') }
  }
  useEffect(() => {
    if (view === 'neighbourhoods' && anchorId && embeddingNeighbours.length) loadNeighbours()
  }, [neighbourhoodK])
  const runProbe = async () => {
    if (!criticalConcept.trim()) return
    setError('')
    try {
      const result = await runCriticalProbe({ concept: criticalConcept.trim(), size: Number(criticalResultCount) })
      setCriticalResults(result.passages || [])
      setSelectedIds([])
    } catch (requestError) { setError(requestError.message || 'Critical inquiry probe could not be completed.') }
  }
  const saveCriticalProbe = async () => {
    if (!criticalConcept.trim() || !criticalResults.length) return
    setError('')
    try {
      const probe = await createVisualCriticalProbe({ inquiry_id: savedInquiryId || null, label: criticalProbeLabel.trim() || criticalConcept.trim(), probe_text: criticalConcept.trim(), polarity: criticalProbePolarity, projection_id: projection.metadata.projectionId || null, embedding_set_id: projection.metadata.embeddingSetId || null, retrieval_method: 'original-space embedding retrieval', results: { passages: criticalResults } })
      setSavedCriticalProbeId(probe.probe_id)
    } catch (requestError) { setError(requestError.message || 'The critical probe record could not be saved.') }
  }
  const compareCriticalProbes = async () => {
    if (!savedCriticalProbeId || !comparisonCriticalProbeId.trim()) return
    setError('')
    try {
      const [currentProbe, comparisonProbe] = await Promise.all([
        getVisualCriticalProbe(savedCriticalProbeId),
        getVisualCriticalProbe(comparisonCriticalProbeId.trim()),
      ])
      const currentIds = new Set((currentProbe.results?.passages || []).map((passage) => passage.id || passage.chunk_id || passage.document_id).filter(Boolean))
      const comparisonIds = new Set((comparisonProbe.results?.passages || []).map((passage) => passage.id || passage.chunk_id || passage.document_id).filter(Boolean))
      const overlap = [...currentIds].filter((id) => comparisonIds.has(id))
      setCriticalProbeComparison({ comparisonProbe, currentCount: currentIds.size, comparisonCount: comparisonIds.size, overlapCount: overlap.length })
    } catch (requestError) { setError(requestError.message || 'The saved critical probes could not be compared.') }
  }
  const loadAlignedComparison = async () => {
    if (!alignedRunId.trim()) return
    setError('')
    try {
      setAlignedComparison(await getAlignedUmapStaticComparison(alignedRunId.trim()))
    } catch (requestError) {
      setAlignedComparison(null)
      setError(requestError.message || 'The aligned run is not available for static comparison.')
    }
  }
  const changeView = (nextView) => {
    setView(nextView)
    navigate(nextView === 'atlas' ? '/visual-analytics' : `/visual-analytics?view=${nextView}`)
  }
  const saveComparisonCohort = async (slot) => {
    const name = (slot === 'A' ? comparisonCohortNameA : comparisonCohortNameB).trim() || `Cohort ${slot}`
    const hasCohortRule = cohortRuleSourceType || cohortRuleTheme || cohortRuleYearFrom || cohortRuleYearTo
    const pointIds = (hasCohortRule
      ? projection.points.filter((point) => {
        const criteria = [
          cohortRuleSourceType && point.sourceType === cohortRuleSourceType,
          cohortRuleTheme && point.themes?.includes(cohortRuleTheme),
          (cohortRuleYearFrom || cohortRuleYearTo) && Number.isFinite(Number(point.year)) && (!cohortRuleYearFrom || Number(point.year) >= Number(cohortRuleYearFrom)) && (!cohortRuleYearTo || Number(point.year) <= Number(cohortRuleYearTo)),
        ].filter((criterion) => criterion !== '')
        return cohortRuleOperator === 'or' ? criteria.some(Boolean) : criteria.every(Boolean)
      }).map((point) => point.id)
      : [...selectedIds])
    try {
      const definition = hasCohortRule ? { source: 'researcher_rule', operator: cohortRuleOperator, source_type: cohortRuleSourceType || null, theme: cohortRuleTheme || null, year_from: cohortRuleYearFrom || null, year_to: cohortRuleYearTo || null } : { source: 'researcher_selection', operator: 'include', selected_point_ids: pointIds }
      const cohort = await createVisualCohort({ name, inquiry_id: savedInquiryId || null, point_ids: pointIds, definition, projection_id: projection.metadata.projectionId || null, embedding_set_id: projection.metadata.embeddingSetId || null })
      const localCohort = { id: cohort.cohort_id, name: cohort.name, pointIds: cohort.point_ids, source: 'researcher selection', createdAt: cohort.created_at, projectionId: cohort.projection_id, embeddingSetId: cohort.embedding_set_id, version: cohort.version }
      if (slot === 'A') { setComparisonA(pointIds); setComparisonCohortA(localCohort) } else { setComparisonB(pointIds); setComparisonCohortB(localCohort) }
    } catch (requestError) { setError(requestError.message || 'The comparison cohort could not be saved.') }
  }
  const resetWorkspace = () => { sessionStorage.removeItem(WORKSPACE_STORAGE_KEY); setFilters(DEFAULT_FILTERS); setSearch(''); setSelectedIds([]); setAnchorId(null); setEmbeddingNeighbours([]); setNeighbourhoodResult(null); setNeighbourhoodK(NEIGHBOURHOOD_K.default); setNeighbourhoodKValue(String(NEIGHBOURHOOD_K.default)); setCriticalResultCount('25'); setComparisonA([]); setComparisonB([]); setComparisonCohortA(null); setComparisonCohortB(null); setComparisonCohortNameA('Cohort A'); setComparisonCohortNameB('Cohort B'); setCohortRuleSourceType(''); setCohortRuleTheme(''); setCohortRuleYearFrom(''); setCohortRuleYearTo(''); setCohortRuleOperator('and'); setFidelityMode('off'); setFidelityResult(null); setTemporalMode('fixed'); setAlignedRunId(''); setAlignedComparison(null); setCriticalResults([]); setCriticalConcept(''); setCriticalPresetId(''); setSavedCriticalProbeId(null); setComparisonCriticalProbeId(''); setCriticalProbeComparison(null); setNote(''); setDimensions('3d'); setAzimuth(25); setElevation(18); setAutoRotate(true); changeView('atlas') }
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
    const state = { exportedAt: new Date().toISOString(), view, filters, search, selectedPoints, comparisonA, comparisonB, comparisonCohortA, comparisonCohortB, fidelityMode, fidelityResult, temporalMode, temporalSummary, anchorId, neighbourhoodK, criticalPresetId, criticalConcept, criticalResultCount, note, projection: projection.metadata }
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' }))
    link.download = 'visual-analytics-workspace.json'
    link.click()
    URL.revokeObjectURL(link.href)
  }
  const saveInquiry = async () => {
    const workspace = { view, filters, search, selectedIds, anchorId, neighbourhoodK, criticalResultCount, criticalConcept, criticalPresetId, comparisonA, comparisonB, comparisonCohortA, comparisonCohortB, fidelityMode, temporalMode, temporalWindowA, temporalWindowB, alignedRunId, note, dimensions, azimuth, elevation }
    setError('')
    try {
      const inquiry = await createVisualInquiry({ view, note, projection_id: projection.metadata.projectionId, embedding_set_id: projection.metadata.embeddingSetId, workspace })
      setSavedInquiryId(inquiry.inquiry_id)
    } catch (requestError) { setError(requestError.message || 'The visual inquiry could not be saved.') }
  }
  const saveAnnotation = async () => {
    if (!inspectorPoint || !annotationValue.trim()) return
    setError('')
    try {
      const payload = { inquiry_id: savedInquiryId || null, document_id: inspectorPoint.documentId || null, chunk_id: inspectorPoint.chunkId || null, annotation_type: annotationType, value: { note: annotationValue.trim() }, evidence_source: 'Visual Analytics researcher annotation', status: annotationStatus }
      const annotation = savedAnnotationId ? await reviseVisualAnnotation(savedAnnotationId, payload) : await createVisualAnnotation(payload)
      setSavedAnnotationId(annotation.annotation_id)
      const history = await getVisualAnnotationRevisions(annotation.annotation_id)
      setAnnotationRevisions(history.revisions || [])
    } catch (requestError) { setError(requestError.message || 'The source annotation could not be saved.') }
  }
  const loadAnnotationHistory = async () => {
    if (!savedAnnotationId) return
    try {
      const history = await getVisualAnnotationRevisions(savedAnnotationId)
      setAnnotationRevisions(history.revisions || [])
    } catch (requestError) { setError(requestError.message || 'The annotation history could not be loaded.') }
  }
  const exportImage = () => {
    const canvas = document.querySelector('.visual-analytics-workbench__canvas')
    if (!canvas) return
    const link = document.createElement('a')
    link.href = canvas.toDataURL('image/png')
    link.download = `semantic-${view}-view.png`
    link.click()
  }
  const exportSvg = () => {
    const canvas = document.querySelector('.visual-analytics-workbench__canvas')
    if (!canvas) return
    const image = canvas.toDataURL('image/png')
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}" viewBox="0 0 ${canvas.width} ${canvas.height}"><image href="${image}" width="${canvas.width}" height="${canvas.height}" /></svg>`
    downloadFile(`semantic-${view}-view.svg`, svg, 'image/svg+xml;charset=utf-8')
  }
  const exportText = () => downloadFile(`semantic-${view}-observation.txt`, `${VIEWS.find(([key]) => key === view)?.[1]}\n\n${note || 'No research observation recorded.'}\n\nSelection: ${selectedPoints.map(pointLabel).join(', ') || 'No points selected'}\nVisible points: ${visiblePoints.length}\nProjection: ${projection.metadata.projectionId || 'Current UMAP surface'}\nExported: ${new Date().toISOString()}\n`)
  const exportComparisonCohorts = () => {
    const membershipIds = [...new Set([...comparisonA, ...comparisonB])]
    downloadCsv('visual-analytics-cohort-comparison.csv', membershipIds.map((id) => {
      const point = pointById.get(id) || {}
      const inA = comparisonA.includes(id)
      const inB = comparisonB.includes(id)
      return {
        point_id: id,
        document_id: point.documentId || '',
        chunk_id: point.chunkId || '',
        pid: point.pid || '',
        title: point.title || '',
        year: point.year || '',
        source_type: point.sourceType || '',
        themes: (point.themes || []).join('; '),
        membership: inA && inB ? 'A/B overlap' : inA ? 'A' : 'B',
        cohort_a_id: comparisonCohortA?.id || '',
        cohort_b_id: comparisonCohortB?.id || '',
        projection_id: projection.metadata.projectionId || '',
        embedding_set_id: projection.metadata.embeddingSetId || '',
      }
    }))
  }
  const exportNeighbourhoodPacket = (format) => {
    if (!neighbourhoodResult?.focal_chunk_id) return
    const packet = { exportedAt: new Date().toISOString(), workflow: 'semantic_neighbourhood', focal: neighbourhoodResult.focal || pointById.get(anchorId) || null, neighbours: embeddingNeighbours, requestedK: neighbourhoodResult.metadata?.requested_k || neighbourhoodK, returnedK: neighbourhoodResult.metadata?.returned_k || embeddingNeighbours.length, metric: neighbourhoodResult.metadata?.metric || 'cosine similarity', method: neighbourhoodResult.metadata?.method, interpretationLimit: neighbourhoodResult.metadata?.interpretation_limit, projection: { projectionId: neighbourhoodResult.metadata?.projection_id || projection.metadata.projectionId, embeddingSetId: neighbourhoodResult.metadata?.embedding_set_id || projection.metadata.embeddingSetId }, researcherNote: note }
    if (format === 'json') { downloadFile('semantic-neighbourhood-evidence-packet.json', `${JSON.stringify(packet, null, 2)}\n`, 'application/json;charset=utf-8'); return }
    const rows = embeddingNeighbours.map((point) => `- ${point.rank || '-'} | ${point.title || 'Untitled trace'} | PID: ${point.pid || 'Unavailable'} | chunk: ${point.chunkId || point.id} | score: ${point.similarity ?? 'Unavailable'}\n  ${point.excerpt || 'No bounded excerpt available.'}`).join('\n')
    downloadFile('semantic-neighbourhood-evidence-packet.md', `# Semantic Neighbourhood Evidence Packet\n\n## Focal Trace\n${packet.focal?.title || packet.focal?.chunk_id || packet.focal?.id || packet.focal?.chunkId || 'Unavailable'}\n\n## Method\n- Projection: ${packet.projection.projectionId || 'Unavailable'}\n- Embedding set: ${packet.projection.embeddingSetId || 'Unavailable'}\n- Metric: ${packet.metric}\n- Requested / returned k: ${packet.requestedK} / ${packet.returnedK}\n\n## Ranked Neighbours\n${rows || 'No neighbours returned.'}\n\n## Researcher Note\n${note || 'None recorded.'}\n\n## Interpretation Limit\n${packet.interpretationLimit || 'Computational proximity identifies candidates for archival investigation; it does not establish a historical relationship.'}\n`, 'text/markdown;charset=utf-8')
  }

  return <main className={`visual-analytics-workbench visual-analytics-workbench--view-${view} ${!panels.controls ? 'visual-analytics-workbench--controls-collapsed' : ''} ${!panels.inspector ? 'visual-analytics-workbench--inspector-collapsed' : ''}`}>
    <header className="visual-analytics-workbench__toolbar">
      <div className="visual-analytics-workbench__title"><DataVis_4 size={24} /><span>Visual Analytics</span></div>
      <Select id="analytics-view" labelText="View" hideLabel value={view} onChange={(event) => changeView(event.target.value)}>{VIEWS.map(([value, label]) => <SelectItem key={value} value={value} text={label} />)}</Select>
      <Search id="atlas-search" labelText="Search corpus" placeholder="Search corpus..." value={search} onChange={(event) => setSearch(event.target.value)} />
      <span className="visual-analytics-workbench__scope">{atlasUnavailable ? `Semantic atlas unavailable | FTS retrieval: ${activeCorpusSummary}` : `${scope.embeddedChunks || projection.points.length} embedded chunks | ${scope.documentsWithEmbeddings || 0} documents`}</span>
      {!atlasUnavailable && <Tag type="gray">{projection.metadata.projectionId || 'Projection pending'} | {projection.metadata.embeddingSetId || 'Embedding set pending'}</Tag>}
      {!atlasUnavailable && <div className="visual-analytics-workbench__method-strip" aria-label="Projection method and provenance"><span>{projection.metadata.projectionMethod || 'UMAP'}</span><span>metric: {projection.metadata.metric || 'Unavailable'}</span><span>n_neighbors: {projection.metadata.nNeighbors ?? 'Unavailable'}</span><span>min_dist: {projection.metadata.minDist ?? 'Unavailable'}</span><span>{activeDimensions.toUpperCase()}</span></div>}
      <div className="visual-analytics-workbench__panel-actions">
        {!panels.controls && <Button kind="ghost" size="sm" renderIcon={ChevronRight} onClick={() => setPanels((current) => ({ ...current, controls: true }))}>View controls</Button>}
        {!panels.inspector && <Button kind="ghost" size="sm" renderIcon={ChevronLeft} onClick={() => setPanels((current) => ({ ...current, inspector: true }))}>View inspector</Button>}
      </div>
      <Button kind="ghost" size="sm" renderIcon={Renew} onClick={resetWorkspace}>Reset</Button>
      <OverflowMenu aria-label="Save view" iconDescription="Save view" renderIcon={Download} size="sm" flipped>
        <OverflowMenuItem itemText={savedInquiryId ? `Saved inquiry: ${savedInquiryId}` : 'Save durable inquiry'} onClick={saveInquiry} />
        <OverflowMenuItem itemText="Save workspace data" onClick={exportWorkspace} />
        <OverflowMenuItem itemText="Save view as PNG" onClick={exportImage} />
        <OverflowMenuItem itemText="Save view as SVG" onClick={exportSvg} />
        <OverflowMenuItem itemText="Save observation as text" onClick={exportText} />
        {view === 'comparative' && <OverflowMenuItem itemText="Export cohort comparison (CSV)" disabled={!comparisonA.length && !comparisonB.length} onClick={exportComparisonCohorts} />}
        {view === 'neighbourhoods' && <><OverflowMenuItem itemText="Export neighbourhood evidence packet (JSON)" disabled={!neighbourhoodResult} onClick={() => exportNeighbourhoodPacket('json')} /><OverflowMenuItem itemText="Export neighbourhood evidence packet (Markdown)" disabled={!neighbourhoodResult} onClick={() => exportNeighbourhoodPacket('markdown')} /></>}
      </OverflowMenu>
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
          <Select id="colour-by" labelText="Colour by" value={filters.colorBy} onChange={(event) => updateFilter('colorBy', event.target.value)}><SelectItem value="view" text="View accent" /><SelectItem value="none" text="None" /><SelectItem value="cluster" text="Cluster" /><SelectItem value="year" text="Year" /><SelectItem value="source_type" text="Source type" /><SelectItem value="theme" text="Theme" /><SelectItem value="representation" text="Representation state" /><SelectItem value="missingness" text="Missingness state" /><SelectItem value="archive_authority" text="Archive authority state" /><SelectItem value="database_authority" text="Database authority linkage" /><SelectItem value="annotation" text="Researcher annotation status" /><SelectItem value="local_density" text="Projected local visual density" /><SelectItem value="documentary_file_type" text="Documentary file type" /><SelectItem value="documentary_extraction" text="Documentary extraction state" /><SelectItem value="documentary_rights" text="Documentary rights/access state" /><SelectItem value="documentary_metadata" text="Documentary metadata completeness" /><SelectItem value="documentary_text_length" text="Document text-length band" /><SelectItem value="documentary_chunk_count" text="Document chunk-count band" /></Select>
          <Select id="label-by" labelText="Label selected points by" value={filters.labelBy} onChange={(event) => updateFilter('labelBy', event.target.value)}><SelectItem value="none" text="None" /><SelectItem value="source" text="Source" /><SelectItem value="theme" text="Theme" /><SelectItem value="year" text="Year" /><SelectItem value="cluster" text="Cluster" /></Select>
        </AccordionItem>
        <AccordionItem title="Projection">
          <p>UMAP coordinates are stored, versioned projections. Parameters cannot be changed here without recomputation.</p>
          <Tag type="gray">{projection.metadata.projectionMethod || 'UMAP'}</Tag>
          <Select id="projection-dimensions" labelText="Display dimensions" value={activeDimensions} onChange={(event) => setDimensions(event.target.value)}>
            <SelectItem value="2d" text="2D" />
            <SelectItem value="3d" text={has3dProjection ? '3D' : '3D (no stored coordinate)'} disabled={!has3dProjection} />
          </Select>
          {activeDimensions === '3d' && <><Slider id="projection-azimuth" labelText="Horizontal orbit" min={-180} max={180} value={azimuth} onChange={({ value }) => { setAutoRotate(false); setAzimuth(value) }} /><Slider id="projection-elevation" labelText="Vertical orbit" min={-80} max={80} value={elevation} onChange={({ value }) => { setAutoRotate(false); setElevation(value) }} /><Button kind="ghost" size="sm" renderIcon={autoRotate ? Pause : Play} onClick={() => setAutoRotate((current) => !current)}>{autoRotate ? 'Pause orbit' : 'Resume orbit'}</Button><p>The Atlas opens in a slow orbit. Mouse down stops it; drag to inspect the stored 3D projection.</p></>}
        </AccordionItem>
        {view === 'neighbourhoods' && <AccordionItem title="Semantic neighbourhood" open>
          <Slider id="neighbourhood-size" labelText="Neighbourhood size (k)" min={NEIGHBOURHOOD_K.min} max={NEIGHBOURHOOD_K.max} step={NEIGHBOURHOOD_K.step} value={neighbourhoodK} onChange={({ value }) => { setNeighbourhoodK(value); setNeighbourhoodKValue(String(value)) }} />
          <TextInput id="neighbourhood-size-value" labelText="Neighbourhood size value" type="number" min={NEIGHBOURHOOD_K.min} max={NEIGHBOURHOOD_K.max} step={NEIGHBOURHOOD_K.step} value={neighbourhoodKValue} onChange={(event) => { const value = event.target.value; setNeighbourhoodKValue(value); const parsed = Number(value); if (parsed >= NEIGHBOURHOOD_K.min && parsed <= NEIGHBOURHOOD_K.max && parsed % NEIGHBOURHOOD_K.step === 0) setNeighbourhoodK(parsed) }} />
          <p>k controls how many original-space nearest neighbours are shown. It does not change the stored UMAP projection or its n_neighbors parameter.</p>
          <Button size="sm" onClick={loadNeighbours} disabled={!inspectorPoint?.chunkId}>Explore neighbourhood</Button>
        </AccordionItem>}
        {view === 'comparative' && <AccordionItem title="Comparison groups" open>
          <Select id="cohort-rule-operator" labelText="Cohort rule operator" value={cohortRuleOperator} onChange={(event) => setCohortRuleOperator(event.target.value)}><SelectItem value="and" text="Match all stated criteria" /><SelectItem value="or" text="Match any stated criterion" /></Select>
          <Select id="cohort-rule-source-type" labelText="Cohort rule: source type" value={cohortRuleSourceType} onChange={(event) => setCohortRuleSourceType(event.target.value)}><SelectItem value="" text="Use current selection" />{sourceTypes.map((type) => <SelectItem key={type} value={type} text={type} />)}</Select>
          <Select id="cohort-rule-theme" labelText="Cohort rule: theme" value={cohortRuleTheme} onChange={(event) => setCohortRuleTheme(event.target.value)}><SelectItem value="" text="Any theme" />{[...new Set(projection.points.flatMap((point) => point.themes || []))].sort().map((theme) => <SelectItem key={theme} value={theme} text={theme} />)}</Select>
          <TextInput id="cohort-rule-year-from" labelText="Cohort rule: from year" value={cohortRuleYearFrom} onChange={(event) => setCohortRuleYearFrom(event.target.value.replace(/[^0-9]/g, ''))} />
          <TextInput id="cohort-rule-year-to" labelText="Cohort rule: to year" value={cohortRuleYearTo} onChange={(event) => setCohortRuleYearTo(event.target.value.replace(/[^0-9]/g, ''))} />
          <p>Defined criteria use the selected AND/OR semantics. Records without a date do not match a date-bound criterion.</p>
          <TextInput id="comparison-cohort-a-name" labelText="Cohort A name" value={comparisonCohortNameA} onChange={(event) => setComparisonCohortNameA(event.target.value)} />
          <Button size="sm" kind="secondary" onClick={() => saveComparisonCohort('A')} disabled={!selectedIds.length && !cohortRuleSourceType && !cohortRuleTheme && !cohortRuleYearFrom && !cohortRuleYearTo}>Save cohort A from selection</Button>
          <TextInput id="comparison-cohort-b-name" labelText="Cohort B name" value={comparisonCohortNameB} onChange={(event) => setComparisonCohortNameB(event.target.value)} />
          <Button size="sm" kind="secondary" onClick={() => saveComparisonCohort('B')} disabled={!selectedIds.length && !cohortRuleSourceType && !cohortRuleTheme && !cohortRuleYearFrom && !cohortRuleYearTo}>Save cohort B from selection</Button>
          <p>A: {comparisonCohortA ? `${comparisonCohortA.name} (${comparisonA.length})` : 'not saved'} | B: {comparisonCohortB ? `${comparisonCohortB.name} (${comparisonB.length})` : 'not saved'} | Overlap: {comparisonA.filter((id) => comparisonB.includes(id)).length}</p>
          <Tag type="green">A membership</Tag><Tag type="blue">B membership</Tag><Tag type="purple">A/B overlap</Tag>
          <Select id="projection-fidelity" labelText="Projection fidelity" value={fidelityMode} onChange={(event) => setFidelityMode(event.target.value)} disabled={!comparisonA.length && !comparisonB.length}><SelectItem value="off" text="Off" /><SelectItem value="show" text="Show neighbourhood preservation" /></Select>
          {fidelityResult?.unavailable && <Tag type="warm-gray">{fidelityResult.unavailable}</Tag>}
          {fidelityResult?.metadata && <p>Neighbourhood preservation: {fidelityResult.results?.length ? (fidelityResult.results.reduce((sum, result) => sum + (result.jaccard_overlap || 0), 0) / fidelityResult.results.length).toFixed(2) : 'Unavailable'} | {fidelityResult.metadata.method}. This is not historical confidence.</p>}
        </AccordionItem>}
        {view === 'temporal' && <AccordionItem title="Temporal scope" open><Select id="temporal-mode" labelText="Temporal mode" value={temporalMode} onChange={(event) => setTemporalMode(event.target.value)}><SelectItem value="fixed" text="Fixed projection" /><SelectItem value="aligned" text="Aligned change (unavailable)" disabled /></Select><Select id="temporal-period-a" labelText="Authority period A" value={temporalPeriodA} onChange={(event) => { const period = temporalPeriods.find((item) => item.period_id === event.target.value); setTemporalPeriodA(event.target.value); if (period) setTemporalWindowA({ from: String(period.start_year || ''), to: String(period.end_year || '') }) }}><SelectItem value="" text="Custom window" />{temporalPeriods.map((period) => <SelectItem key={period.period_id} value={period.period_id} text={period.label} />)}</Select>{selectedTemporalPeriodA && <p>Window A authority: {selectedTemporalPeriodA.authority_source} ({selectedTemporalPeriodA.certainty}){selectedTemporalPeriodA.notes ? ` - ${selectedTemporalPeriodA.notes}` : ''}</p>}<Select id="temporal-period-b" labelText="Authority period B" value={temporalPeriodB} onChange={(event) => { const period = temporalPeriods.find((item) => item.period_id === event.target.value); setTemporalPeriodB(event.target.value); if (period) setTemporalWindowB({ from: String(period.start_year || ''), to: String(period.end_year || '') }) }}><SelectItem value="" text="Custom window" />{temporalPeriods.map((period) => <SelectItem key={period.period_id} value={period.period_id} text={period.label} />)}</Select>{selectedTemporalPeriodB && <p>Window B authority: {selectedTemporalPeriodB.authority_source} ({selectedTemporalPeriodB.certainty}){selectedTemporalPeriodB.notes ? ` - ${selectedTemporalPeriodB.notes}` : ''}</p>}<div className="visual-analytics-workbench__temporal-windows"><TextInput id="temporal-a-from" labelText="Window A from" value={temporalWindowA.from} onChange={(event) => setTemporalWindowA((current) => ({ ...current, from: event.target.value.replace(/[^0-9]/g, '') }))} /><TextInput id="temporal-a-to" labelText="Window A to" value={temporalWindowA.to} onChange={(event) => setTemporalWindowA((current) => ({ ...current, to: event.target.value.replace(/[^0-9]/g, '') }))} /><TextInput id="temporal-b-from" labelText="Window B from" value={temporalWindowB.from} onChange={(event) => setTemporalWindowB((current) => ({ ...current, from: event.target.value.replace(/[^0-9]/g, '') }))} /><TextInput id="temporal-b-to" labelText="Window B to" value={temporalWindowB.to} onChange={(event) => setTemporalWindowB((current) => ({ ...current, to: event.target.value.replace(/[^0-9]/g, '') }))} /></div><p>Fixed projection filters change visibility and encoding only. They do not recompute or move stored UMAP coordinates.</p><p>The saved windows support documentary comparison within that fixed projection.</p><Tag type="gray">Represented: {temporalSummary.represented} | Visible: {temporalSummary.visible} | Excluded: {temporalSummary.excluded} | Undated: {temporalSummary.undated}</Tag><Tag type="blue">Window A: {temporalWindowSummary.a.inWindow} dated in scope | {temporalWindowSummary.a.undated} undated</Tag><Tag type="purple">Window B: {temporalWindowSummary.b.inWindow} dated in scope | {temporalWindowSummary.b.undated} undated</Tag><Tag type="warm-gray">Aligned change requires explicit consecutive relation mappings and a separately versioned aligned run.</Tag></AccordionItem>}
        {view === 'critical' && <AccordionItem title="Critical inquiry" open><p>Critical lens supplied by researcher. Computational proximity indicates material for investigation, not confirmation of the proposition.</p><Select id="critical-lens-preset" labelText="Researcher lens preset" value={criticalPresetId} onChange={(event) => { const preset = CRITICAL_LENS_PRESETS.find((item) => item.id === event.target.value); setCriticalPresetId(event.target.value); if (preset) setCriticalConcept(preset.text) }}><SelectItem value="" text="No preset" />{CRITICAL_LENS_PRESETS.map((preset) => <SelectItem key={preset.id} value={preset.id} text={preset.label} />)}</Select><TextInput id="critical-concept" labelText="Concept or proposition" placeholder="e.g. unacknowledged technical labour" value={criticalConcept} onChange={(event) => setCriticalConcept(event.target.value)} /><Select id="critical-result-count" labelText="Passages to inspect" value={criticalResultCount} onChange={(event) => setCriticalResultCount(event.target.value)}>{['10', '25', '50'].map((value) => <SelectItem key={value} value={value} text={value} />)}</Select><Button size="sm" onClick={runProbe} disabled={!criticalConcept.trim()}>Investigate concept</Button><TextInput id="critical-probe-label" labelText="Probe record label" value={criticalProbeLabel} onChange={(event) => setCriticalProbeLabel(event.target.value)} /><Select id="critical-probe-polarity" labelText="Researcher probe polarity" value={criticalProbePolarity} onChange={(event) => setCriticalProbePolarity(event.target.value)}><SelectItem value="positive" text="Positive probe" /><SelectItem value="negative" text="Negative probe" /></Select><Button size="sm" kind="secondary" onClick={saveCriticalProbe} disabled={!criticalResults.length}>Save probe record</Button>{savedCriticalProbeId && <><Tag type="green">Saved probe: {savedCriticalProbeId}</Tag><TextInput id="critical-comparison-probe-id" labelText="Saved probe ID to compare" value={comparisonCriticalProbeId} onChange={(event) => setComparisonCriticalProbeId(event.target.value)} /><Button size="sm" kind="tertiary" onClick={compareCriticalProbes} disabled={!comparisonCriticalProbeId.trim()}>Compare saved probes</Button></>}{criticalProbeComparison && <p>Saved-probe comparison: current {criticalProbeComparison.currentCount} results | comparison {criticalProbeComparison.comparisonCount} results | overlap {criticalProbeComparison.overlapCount}. Result overlap identifies shared retrieval candidates, not evidential confirmation.</p>}<Tag type="warm-gray">Original-space retrieval only. A transformed researcher-probe marker is unavailable until a compatible retained reducer is verified.</Tag><Tag type="warm-gray">Image-only: {scope.imageOnlyRecords ?? 0}</Tag></AccordionItem>}
        {view === 'temporal' && <AccordionItem title="Validated aligned-run provenance"><TextInput id="aligned-run-id" labelText="Validated aligned run ID" value={alignedRunId} onChange={(event) => setAlignedRunId(event.target.value)} /><Button size="sm" kind="secondary" onClick={loadAlignedComparison} disabled={!alignedRunId.trim()}>Load static comparison</Button>{alignedComparison && <><Tag type="green">Validated run: {alignedComparison.aligned_run?.aligned_run_id}</Tag><p>{alignedComparison.slices?.length || 0} reviewed slices | {alignedComparison.relations?.length || 0} explicit consecutive relations</p><ol>{(alignedComparison.slices || []).map((slice) => <li key={slice.slice_id}>{slice.slice_order}: {slice.period_provenance?.label || slice.slice_id} ({slice.point_count} declared points)</li>)}</ol><p>{alignedComparison.interpretation_limit}</p></>}<p>Static comparison exposes only validated relation provenance. It does not generate coordinates, trails, animation, or historical continuity.</p></AccordionItem>}
      </Accordion>
    </aside>
    <section className="visual-analytics-workbench__map-region">
      {loading ? <div className="visual-analytics-workbench__empty-map">Loading embedding surface...</div> : <EmbeddingCanvas points={displayPoints} emptyMessage={atlasUnavailable ? `Semantic atlas unavailable: this corpus has no embedding vectors. Full-text retrieval remains active across ${activeCorpusSummary}.` : view === 'neighbourhoods' ? 'Select a focal archival passage, then choose Explore neighbourhood.' : view === 'critical' ? 'Enter a researcher-supplied critical concept to inspect nearby archival passages.' : projection.message} dimensions={activeDimensions} azimuth={azimuth} elevation={elevation} autoRotate={autoRotate} selectedIds={selectedIds} searchIds={searchIds} anchorId={anchorId} comparisonA={comparisonA} comparisonB={comparisonB} colorBy={filters.colorBy} labelBy={filters.labelBy} onSelect={selectPoint} onHover={setHovered} onCameraChange={(nextElevation, nextAzimuth) => { setAutoRotate(false); setElevation(nextElevation); setAzimuth(nextAzimuth) }} onOrbitStart={() => setAutoRotate(false)} onClearSelection={clearSelection} />}
      {hovered && <div className="visual-analytics-workbench__hover" style={{ left: hovered.x + 14, top: hovered.y + 14 }}><strong>{pointLabel(hovered.point)}</strong><span>{hovered.point.year || 'Undated'}</span></div>}
    </section>
    <aside className="visual-analytics-workbench__inspector">
      <Button kind="ghost" size="sm" renderIcon={View} onClick={() => setPanels((current) => ({ ...current, inspector: false }))}>Collapse inspector</Button>
      <Tile className="visual-analytics-workbench__view-context">
        <h2>{atlasUnavailable ? 'Semantic atlas unavailable' : VIEWS.find(([key]) => key === view)?.[1]}</h2>
        <p>{atlasUnavailable ? `The active corpus is available for full-text retrieval, but no embedding vectors are present for a spatial projection. This is a computational capability state, not archival absence.` : VIEW_FRAMING[view]}</p>
        <Tag type="blue">{atlasUnavailable ? `FTS retrieval: ${activeCorpusSummary}` : evidenceSurfaceCounts}</Tag>
      </Tile>
      {COLOR_MODE_LABELS[filters.colorBy] && <Tile><h2>Display legend</h2><p>Colour encodes {COLOR_MODE_LABELS[filters.colorBy]}. {filters.colorBy === 'local_density' ? 'It is derived from distances between displayed stored coordinates; it does not indicate historical concentration, significance, or archive completeness.' : ['documentary_text_length', 'documentary_chunk_count'].includes(filters.colorBy) ? 'These are returned measures for the represented database document, not an archive-wide total or a measure of historical significance.' : filters.colorBy.startsWith('documentary_') ? 'These are returned documentary representation fields. Not exposed or not evaluated states are not evidence of access, rights, completeness, or archival absence.' : 'This is a display field, not a historical conclusion.'}</p><div className="visual-analytics-workbench__legend-values">{colorLegendValues.length ? colorLegendValues.slice(0, 12).map((value) => <Tag key={String(value)} type="gray">{value}</Tag>) : <Tag type="warm-gray">Unavailable</Tag>}</div></Tile>}
      <Tile>
        <h2>Method and provenance</h2>
        <dl><dt>Projection</dt><dd>{projection.metadata.projectionId || 'Unavailable'}</dd><dt>Embedding set</dt><dd>{projection.metadata.embeddingSetId || 'Unavailable'}</dd><dt>Metric</dt><dd>{projection.metadata.metric || 'Unavailable'}</dd><dt>UMAP n_neighbors</dt><dd>{projection.metadata.nNeighbors ?? 'Unavailable'}</dd><dt>UMAP min_dist</dt><dd>{projection.metadata.minDist ?? 'Unavailable'}</dd><dt>Dimensions</dt><dd>{activeDimensions.toUpperCase()}</dd></dl>
      </Tile>
      {view === 'comparative' && <Tile><h2>Compare sources</h2>{comparisonSourceRows.length ? <table><thead><tr><th>Source</th><th>Membership</th><th>PID</th></tr></thead><tbody>{comparisonSourceRows.map(({ point, membership }) => <tr key={point.id}><td>{pointLabel(point)}</td><td>{membership}</td><td>{point.pid || 'Unavailable'}</td></tr>)}</tbody></table> : <p>Save cohort A or B from a selection to inspect source membership here.</p>}<p>Membership is a researcher-defined comparison condition, not a historical conclusion.</p></Tile>}
      {!inspectorPoint ? <Tile><h2>Inspector</h2><p>Select a point to inspect source metadata, provenance context, and distinct embedding and projected neighbours.</p></Tile> : <Tile>
        <h2>{selectedPoints.length > 1 ? `${selectedPoints.length} selected items` : pointLabel(inspectorPoint)}</h2>
        {selectedPoints.length === 1 && <><p className="visual-analytics-workbench__excerpt">{inspectorPoint.excerpt || 'No excerpt is available.'}</p><dl><dt>Year</dt><dd>{inspectorPoint.year || 'Unknown'}</dd><dt>Source type</dt><dd>{inspectorPoint.sourceType || 'Unknown'}</dd><dt>PID</dt><dd>{inspectorPoint.pid || 'Unavailable'}</dd><dt>Chunk</dt><dd>{inspectorPoint.chunkId || 'Document point'}</dd><dt>Themes</dt><dd>{inspectorPoint.themes?.join(', ') || 'Unlabelled'}</dd><dt>Representation</dt><dd>{inspectorPoint.evidenceSurface?.representationState || 'Unknown'}</dd><dt>Missingness</dt><dd>{inspectorPoint.missingness?.status || 'Not recorded'}</dd><dt>Archive authority</dt><dd>{inspectorPoint.archiveAuthorityContext?.availability || 'Not exposed'}</dd><dt>Database authority</dt><dd>{inspectorPoint.databaseAuthorityContext?.length ? `${inspectorPoint.databaseAuthorityContext.length} linked record(s)` : 'Not exposed'}</dd><dt>Projection</dt><dd>{projection.metadata.projectionId || 'Current UMAP surface'}</dd></dl></>}
        <div className="visual-analytics-workbench__actions"><Button size="sm" kind="ghost" onClick={() => handoff('/sources')}>Open source</Button><Button size="sm" kind="ghost" onClick={() => handoff('/source-interrogation')}>Ask about selected sources</Button><Button size="sm" kind="ghost" onClick={() => { setAnchorId(inspectorPoint.id); setView('neighbourhoods') }}>Semantic neighbourhood</Button><Button size="sm" kind="ghost" renderIcon={Add} onClick={() => setComparisonA((current) => [...new Set([...current, ...selectedIds])])}>Add to comparison A</Button><Button size="sm" kind="ghost" onClick={() => handoff('/cross-readings')}>Cross-read</Button><Button size="sm" kind="ghost" renderIcon={WarningAlt} onClick={() => handoff('/absences')}>Record scoped absence</Button></div>
        {selectedPoints.length === 1 && <div className="visual-analytics-workbench__annotation"><h3>Researcher annotation</h3><Select id="annotation-type" labelText="Annotation type" value={annotationType} onChange={(event) => setAnnotationType(event.target.value)}><SelectItem value="researcher_note" text="Researcher note" /><SelectItem value="interpretive_question" text="Interpretive question" /><SelectItem value="contested_reading" text="Contested reading" /></Select><Select id="annotation-status" labelText="Review status" value={annotationStatus} onChange={(event) => setAnnotationStatus(event.target.value)}><SelectItem value="draft" text="Draft" /><SelectItem value="reviewed" text="Reviewed" /><SelectItem value="contested" text="Contested" /></Select><TextArea id="annotation-value" labelText="Source-linked note" value={annotationValue} onChange={(event) => setAnnotationValue(event.target.value)} rows={3} /><Button size="sm" onClick={saveAnnotation} disabled={!annotationValue.trim()}>{savedAnnotationId ? 'Save revision' : 'Save annotation'}</Button>{savedAnnotationId && <><Tag type="green">Saved annotation: {savedAnnotationId}</Tag><Button size="sm" kind="ghost" onClick={loadAnnotationHistory}>View revision history</Button>{annotationRevisions.length > 0 && <ol className="visual-analytics-workbench__revision-list">{annotationRevisions.map((revision) => <li key={revision.revision}>Revision {revision.revision}: {revision.snapshot?.value?.note || 'No note recorded'}</li>)}</ol>}</>}</div>}
        <h3>Embedding neighbours</h3><p>Nearest passages in the original embedding space.</p>{neighbourhoodResult?.metadata && <div><h4>Why this neighbour?</h4><p>Rank and score use {neighbourhoodResult.metadata.metric || 'the recorded original-space metric'} in embedding set {neighbourhoodResult.metadata.embedding_set_id || 'Unavailable'}; projection {neighbourhoodResult.metadata.projection_id || 'Unavailable'} remains fixed. This is a retrieval diagnostic, not a historical relationship.</p></div>}<div className="visual-analytics-workbench__neighbour-list">{embeddingNeighbours.length ? embeddingNeighbours.map((point) => <div key={point.id}><button type="button" onClick={() => selectPoint(point)}><span>{point.title}</span><small>rank {point.rank || '-'} | {point.similarity ?? point.distance ?? 'metric unavailable'}</small></button><Button size="sm" kind="ghost" onClick={() => refocusNeighbour(point)} disabled={!point.chunkId}>Use as focal trace</Button></div>) : <span>Choose “Explore neighbourhood” to retrieve backend embedding neighbours.</span>}</div>
        <h3>Projected neighbours</h3><p>Spatially close points in the UMAP projection only.</p><div className="visual-analytics-workbench__neighbour-list">{projectedNeighbours.map((point) => <button type="button" key={point.id} onClick={() => selectPoint(point)}><span>{pointLabel(point)}</span><small>projected distance {point.projectedDistance.toFixed(2)}</small></button>)}</div>
      </Tile>}
    </aside>
    <section className="visual-analytics-workbench__tray">
      <div><strong>{view === 'comparative' ? 'Comparison' : view === 'neighbourhoods' ? 'Neighbourhood' : 'Selection'}:</strong> {selectedPoints.length ? selectedPoints.slice(0, 4).map(pointLabel).join(', ') : 'No points selected'}</div>
      <TextArea id="research-note" labelText="Research observation" hideLabel placeholder="Capture an observation from the current workspace..." value={note} onChange={(event) => setNote(event.target.value)} rows={2} />
      <Button size="sm" kind="tertiary" onClick={exportWorkspace}>Export observation</Button>
    </section>
  </main>
}

export default VisualAnalyticsWorkbench