import { Accordion, AccordionItem, Button, InlineLoading, InlineNotification, OverflowMenu, OverflowMenuItem, ProgressBar, Search, Select, SelectItem, Slider, Tab, TabList, Tabs, Tag, TextArea, TextInput, Tile, Toggle } from '@carbon/react'
import { Add, ChevronLeft, ChevronRight, DataVis_4, Download, Launch, Pause, Play, Renew, Save, TextFont, View, WarningAlt } from '@carbon/icons-react'
import * as d3 from 'd3'
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createAtlasCoverageMissingness, createVisualAnnotation, createVisualCohort, createVisualCriticalProbe, createVisualInquiry, getAlignedUmapCoordinates, getAlignedUmapRuns, getAlignedUmapStaticComparison, getCohortNeighbourhood, getOriginalSpaceDensity, getProjectionFidelity, getQueryNeighbourhood, getSemanticNeighbourhood, getUmapProjection, getVisualAnnotationRevisions, getVisualCriticalProbe, getVisualInquiry, getVisualTemporalPeriods, reviseVisualAnnotation, runCriticalProbe } from '../../api/viz'
import { downloadCsv, downloadFile } from '../../utils/workbenchExport'
import { getMissingnessSummary } from '../../api/missingness'

const VIEWS = [
  ['atlas', 'Semantic atlas'],
  ['neighbourhoods', 'Semantic neighbourhoods'],
  ['comparative', 'Comparative views'],
  ['temporal', 'Temporal and documentary change'],
  ['critical', 'Critical inquiry'],
]
const VIEW_PRESENTATION = {
  atlas: { number: '01', label: 'Semantic Atlas', colorBy: 'cluster' },
  neighbourhoods: { number: '02', label: 'Semantic Neighbourhoods', colorBy: 'cluster' },
  comparative: { number: '03', label: 'Comparative Views', colorBy: 'source_type' },
  temporal: { number: '04', label: 'Temporal and Documentary Change', colorBy: 'year' },
  critical: { number: '05', label: 'Critical Inquiry', colorBy: 'view' },
}

const VIEW_FRAMING = {
  atlas: 'Where is everything? Browse the corpus-level projection as an exploratory representation, not a neutral map of historical reality.',
  neighbourhoods: 'What is close to this archival trace? Select a focal passage, then retrieve its nearest neighbours in the original embedding space.',
  comparative: 'How do structures differ? Compare selected groups or use metadata overlays to test how archival categories distribute across the projection.',
  temporal: 'How does the documentary representation change? Filter known dates and inspect how concentrations move across the available corpus.',
  critical: 'What becomes visible through a stated critical lens? Start with a researcher-supplied concept and inspect the returned archival passages.',
}

const DEFAULT_FILTERS = { pointType: 'documents', colorBy: 'view', labelBy: 'none', yearMin: '', yearMax: '', sourceType: '' }
const WORKSPACE_STORAGE_KEY = 'ddr.visual-analytics.workspace'
const NEIGHBOURHOOD_K = { min: 1, max: 100, step: 1, default: 10 }
const PROJECTION_RENDER_LIMIT = 1000
const PROJECTION_PAGE_SIZE = 250
const COLOR_MODE_LABELS = { cluster: 'Cluster', year: 'Year', source_type: 'Source type', representation: 'Representation state', missingness: 'Missingness state', archive_authority: 'Archive authority state', database_authority: 'Database authority linkage', annotation: 'Researcher annotation status', local_density: 'Projected local visual density', original_space_density: 'Original embedding-space density cue', documentary_file_type: 'Documentary file type', documentary_extraction: 'Documentary extraction state', documentary_rights: 'Documentary rights/access state', documentary_metadata: 'Documentary metadata completeness', documentary_text_length: 'Document text-length band', documentary_chunk_count: 'Document chunk-count band' }
const CRITICAL_LENS_PRESETS = [
  { id: 'labour-attribution', label: 'Divisions of labour, authorship, and attribution', text: 'unacknowledged technical and administrative labour, authorship, and attribution' },
  { id: 'archival-obscurity', label: 'Archival silence and obscurity', text: 'archival silence, obscurity, and uneven documentary visibility' },
  { id: 'maintenance', label: 'Technical practice, maintenance, and infrastructure', text: 'technical maintenance, infrastructure, coordination, and support work' },
  { id: 'care-disability', label: 'Disability, care, and beneficiary relations', text: 'disability, care, beneficiary relations, and design practice' },
]
const ANNOTATION_TYPES = [
  ['researcher_note', 'Researcher note'], ['interpretive_question', 'Interpretive question'], ['contested_reading', 'Contested reading'],
  ['role_action', 'Role or action'], ['attribution', 'Attribution'], ['anonymity', 'Anonymity'], ['identity_alias', 'Identity or role alias'], ['contested_label', 'Contested label'], ['representation_condition', 'Representation condition'], ['interpretive_note', 'Interpretive note'],
]
const ANNOTATION_CONTROLLED_VALUES = {
  role_action: [['administrative', 'Administrative'], ['technical', 'Technical'], ['care', 'Care'], ['teaching', 'Teaching'], ['workshop', 'Workshop'], ['coordination', 'Coordination'], ['maintenance', 'Maintenance'], ['research', 'Research'], ['authorship', 'Authorship'], ['collaboration', 'Collaboration'], ['supervision', 'Supervision'], ['management', 'Management'], ['other_uncertain', 'Other or uncertain']],
  attribution: [['named_individual', 'Named individual'], ['collective_attribution', 'Collective attribution'], ['unnamed_actor', 'Unnamed actor'], ['inferred_uncertain', 'Inferred or uncertain'], ['absent_not_described', 'Absent or not described']],
  anonymity: [['identified', 'Identified'], ['anonymous', 'Anonymous'], ['not_exposed', 'Not exposed']],
  representation_condition: [['documentary_trace', 'Documentary trace'], ['descriptive_trace', 'Descriptive trace'], ['oral_history_trace', 'Oral-history trace'], ['authority_context', 'Authority context'], ['computational_cue', 'Computational cue'], ['missingness_condition', 'Missingness condition']],
}
const ANNOTATION_RESEARCHER_VALUE_LABELS = { identity_alias: 'Identity or role alias', contested_label: 'Contested label', interpretive_note: 'Interpretive coding value' }

const readWorkspace = () => {
  try {
    const workspace = JSON.parse(sessionStorage.getItem(WORKSPACE_STORAGE_KEY) || '{}')
    return workspace.orbitVersion >= 9 ? workspace : { ...workspace, filters: { ...workspace.filters, colorBy: 'view', pointType: 'documents' } }
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
  evidenceClass: point.evidenceClass || point.evidence_class || { kind: 'documentary_record', label: 'Archival document' },
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

const pointColour = (point, colorBy, colourScale, viewAccent, mutedPoint, categoricalColours, sequentialColours) => {
  if (colorBy === 'view') return viewAccent
  if (colorBy === 'none') return mutedPoint
  if (colorBy === 'year' || colorBy === 'local_density' || colorBy === 'original_space_density') {
    const value = colorBy === 'year' ? point.year : colorBy === 'local_density' ? point.projectedLocalDensity : point.originalSpaceDensity
    return sequentialColours[Math.round(Math.max(0, Math.min(1, colourScale(value || 0))) * (sequentialColours.length - 1))]
  }
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

const legendValue = (point, colorBy) => {
  if (colorBy === 'source_type') return point.sourceType || 'Unavailable'
  if (colorBy === 'theme') return point.themes?.[0] || 'Unlabelled'
  if (colorBy === 'representation') return point.evidenceSurface?.representationState || 'Unavailable'
  if (colorBy === 'missingness') return point.missingness?.status || 'Unavailable'
  if (colorBy === 'archive_authority') return point.archiveAuthorityContext?.availability || 'Unavailable'
  if (colorBy === 'database_authority') return point.databaseAuthorityContext?.length ? 'Linked record' : 'No linked record exposed'
  if (colorBy === 'annotation') return point.annotationState?.status || point.annotations?.status || 'Unavailable'
  if (colorBy === 'documentary_file_type') return point.documentaryForm?.fileType || 'Unavailable'
  if (colorBy === 'documentary_extraction') return point.documentaryForm?.extractionState || 'Unavailable'
  if (colorBy === 'documentary_rights') return point.documentaryForm?.rightsAccessState || 'Unavailable'
  if (colorBy === 'documentary_metadata') return point.documentaryForm?.metadataCompleteness || 'Unavailable'
  if (colorBy === 'documentary_text_length') return documentaryTextLengthBand(point.documentaryForm?.documentTextLength)
  if (colorBy === 'documentary_chunk_count') return documentaryChunkCountBand(point.documentaryForm?.documentChunkCount)
  return point.clusterLabel || 'Unclustered'
}

const MapVisualLegend = ({ view, colorBy, points, anchorId, comparisonA, comparisonB }) => {
  const numericEncoding = ['year', 'local_density', 'original_space_density'].includes(colorBy)
  const categories = [...new Set(points.map((point) => legendValue(point, colorBy)))].slice(0, 8)
  const hasComparisonCohort = comparisonA.length > 0 || comparisonB.length > 0
  const entries = view === 'comparative' && hasComparisonCohort
    ? [['cohort-a', 'Cohort A'], ['cohort-overlap', 'Shared membership'], ['cohort-b', 'Cohort B']]
    : view === 'neighbourhoods' && anchorId
      ? [['focal', 'Focal trace'], ['neighbour', 'Original-space neighbour'], ['muted', 'Other represented record']]
      : view === 'critical'
        ? [['critical', 'Critical-query result'], ...categories.map((value, index) => [`category-${index + 1}`, value])]
        : numericEncoding
          ? [['sequential', `${COLOR_MODE_LABELS[colorBy]}: lower to higher`]]
          : categories.map((value, index) => [`category-${index + 1}`, value])

  if (!entries.length) return null
  return <div className="visual-analytics-workbench__map-legend" aria-label={`${COLOR_MODE_LABELS[colorBy] || 'Projection'} visual key`}>
    <span className="visual-analytics-workbench__map-legend-title">{view === 'comparative' && hasComparisonCohort ? 'Cohort comparison' : view === 'neighbourhoods' && anchorId ? 'Original-space retrieval' : COLOR_MODE_LABELS[colorBy] || 'Projection encoding'}</span>
    <div>{entries.map(([tone, label]) => <span key={label} className="visual-analytics-workbench__map-legend-item"><i className={`visual-analytics-workbench__map-swatch visual-analytics-workbench__map-swatch--${tone}`} />{label}</span>)}</div>
  </div>
}

const EmbeddingCanvas = ({ points, emptyMessage, view, dimensions, sphereView, azimuth, elevation, autoRotate, boxSelectionEnabled, selectedIds, searchIds, anchorId, comparisonA, comparisonB, focusSelection, colorBy, labelBy, showTitleLabels = labelBy === 'source', relationLinks = [], zAxisLabel = 'z', ariaLabel = 'Interactive UMAP embedding map', onSelect, onSelectMany, onHover, onCameraChange, onOrbitStart, onClearSelection }) => {
  const canvasRef = useRef(null)
  const transformRef = useRef(d3.zoomIdentity)
  const dragRef = useRef(null)
  const callbacksRef = useRef({})
  const [size, setSize] = useState({ width: 800, height: 620 })
  callbacksRef.current = { onSelect, onSelectMany, onHover, onCameraChange, onOrbitStart, onClearSelection }

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setSize({ width: entry.contentRect.width, height: Math.max(460, entry.contentRect.height) }))
    if (canvasRef.current?.parentElement) observer.observe(canvasRef.current.parentElement)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !points.length) return undefined
    const styles = getComputedStyle(canvas)
    const colour = (name) => styles.getPropertyValue(name).trim()
    const categoricalColours = Array.from({ length: 14 }, (_, index) => colour(`--atlas-categorical-${index + 1}`))
    const sequentialColours = Array.from({ length: 9 }, (_, index) => colour(`--atlas-sequential-${index + 1}`))
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
    const temporalYears = points.map((point) => Number(point.year)).filter(Number.isFinite)
    const temporalYearExtent = d3.extent(temporalYears.length ? temporalYears : [0, 1])
    const projectPoints = () => points.map((point) => {
      if (view === 'temporal') {
        const year = Number(point.year)
        const timePosition = Number.isFinite(year) ? d3.scaleLinear().domain(temporalYearExtent).range([-coordinateSpan, coordinateSpan])(year) : coordinateSpan * 1.18
        return { ...point, renderX: timePosition, renderY: point.y * 0.32, depth: 0, temporalUndated: !Number.isFinite(year) }
      }
      if (dimensions !== '3d') return { ...point, renderX: point.x, renderY: point.y, depth: 0 }
      const pointRadius = Math.hypot(point.x, point.y, point.z || 0) || 1
      const displayScale = sphereView ? coordinateSpan / pointRadius : 1
      const displayX = point.x * displayScale
      const displayY = point.y * displayScale
      const displayZ = (point.z || 0) * displayScale
      const rotatedX = displayX * Math.cos(azimuthRadians()) - displayZ * Math.sin(azimuthRadians())
      const depth = displayX * Math.sin(azimuthRadians()) + displayZ * Math.cos(azimuthRadians())
      const perspective = 1 + (depth / coordinateSpan) * 0.22
      return { ...point, renderX: rotatedX * perspective, renderY: (displayY * Math.cos(elevationRadians) - depth * Math.sin(elevationRadians)) * perspective, depth }
    })
    let renderedPoints = projectPoints()
    let xScale
    let yScale
    const values = colorBy === 'year' ? points.map((point) => point.year).filter(Number.isFinite) : colorBy === 'local_density' ? points.map((point) => point.projectedLocalDensity).filter(Number.isFinite) : colorBy === 'original_space_density' ? points.map((point) => point.originalSpaceDensity).filter(Number.isFinite) : [...new Set(points.map((point) => colorBy === 'source_type' ? point.sourceType : colorBy === 'theme' ? point.themes?.[0] : colorBy === 'representation' ? point.evidenceSurface?.representationState : colorBy === 'missingness' ? point.missingness?.status : colorBy === 'archive_authority' ? point.archiveAuthorityContext?.availability : colorBy === 'database_authority' ? point.databaseAuthorityContext?.length ? 'Linked record' : 'No linked record exposed' : colorBy === 'annotation' ? point.annotationState?.status || point.annotations?.status : point.clusterLabel))]
    const colourScale = colorBy === 'year' || colorBy === 'local_density' || colorBy === 'original_space_density'
      ? d3.scaleLinear().domain(d3.extent(values.length ? values : [0, 1])).range([0, 1])
      : d3.scaleOrdinal(categoricalColours).domain(values)

    let selectionRect = null
    const draw = () => {
      renderedPoints = projectPoints()
      const xSpan = Math.max(d3.max(renderedPoints, (point) => Math.abs(point.renderX)) || 0, 1) * 1.08
      const ySpan = Math.max(d3.max(renderedPoints, (point) => Math.abs(point.renderY)) || 0, 1) * 1.08
      const paddedExtent = (accessor) => {
        const [minimum, maximum] = d3.extent(renderedPoints, accessor)
        const span = Math.max((maximum || 0) - (minimum || 0), 1)
        return [(minimum || 0) - span * 0.08, (maximum || 0) + span * 0.08]
      }
      xScale = d3.scaleLinear().domain(dimensions === '2d' ? paddedExtent((point) => point.renderX) : [-xSpan, xSpan]).range([30, size.width - 30])
      yScale = d3.scaleLinear().domain(dimensions === '2d' ? paddedExtent((point) => point.renderY) : [-ySpan, ySpan]).range([size.height - 30, 30])
      const transform = transformRef.current
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
      context.clearRect(0, 0, size.width, size.height)
      context.fillStyle = colour('--atlas-canvas-background')
      context.fillRect(0, 0, size.width, size.height)
      if (dimensions === '2d') {
        context.save()
        context.strokeStyle = colour('--atlas-grid')
        context.lineWidth = 1
        context.globalAlpha = 0.45
        const gridStep = Math.max(72, Math.round(Math.min(size.width, size.height) / 8))
        for (let x = gridStep; x < size.width; x += gridStep) {
          context.beginPath()
          context.moveTo(x, 0)
          context.lineTo(x, size.height)
          context.stroke()
        }
        for (let y = gridStep; y < size.height; y += gridStep) {
          context.beginPath()
          context.moveTo(0, y)
          context.lineTo(size.width, y)
          context.stroke()
        }
        context.restore()
      }
      if (view === 'temporal' && temporalYears.length) {
        const firstYear = Math.floor(temporalYearExtent[0] / 5) * 5
        const lastYear = Math.ceil(temporalYearExtent[1] / 5) * 5
        context.save()
        context.strokeStyle = colour('--atlas-guide')
        context.fillStyle = colour('--atlas-guide-label')
        context.globalAlpha = 0.55
        context.font = '11px IBM Plex Sans, sans-serif'
        for (let year = firstYear; year <= lastYear; year += 5) {
          const x = xScale(d3.scaleLinear().domain(temporalYearExtent).range([-coordinateSpan, coordinateSpan])(year))
          context.beginPath()
          context.moveTo(x, 0)
          context.lineTo(x, size.height)
          context.stroke()
          context.fillText(String(year), x + 4, size.height - 10)
        }
        const undatedX = xScale(coordinateSpan * 1.18)
        context.setLineDash([4, 3])
        context.beginPath()
        context.moveTo(undatedX, 0)
        context.lineTo(undatedX, size.height)
        context.stroke()
        context.setLineDash([])
        context.fillText('Undated', undatedX + 4, size.height - 10)
        context.restore()
      }
      if (dimensions === '3d') {
        const projectAxis = (x, y, z) => {
          const rotatedX = x * Math.cos(azimuthRadians()) - z * Math.sin(azimuthRadians())
          const depth = x * Math.sin(azimuthRadians()) + z * Math.cos(azimuthRadians())
          const perspective = 1 + (depth / coordinateSpan) * 0.22
          return [xScale(rotatedX * perspective), yScale((y * Math.cos(elevationRadians) - depth * Math.sin(elevationRadians)) * perspective)]
        }
        const origin = projectAxis(0, 0, 0)
        const axisLength = coordinateSpan * 0.72
        ;[[axisLength, 0, 0, colour('--atlas-axis-x'), 'x'], [0, axisLength, 0, colour('--atlas-axis-y'), 'y'], [0, 0, axisLength, colour('--atlas-axis-z'), zAxisLabel]].forEach(([x, y, z, axisColour, label]) => {
          const endpoint = projectAxis(x, y, z)
          context.beginPath()
          context.moveTo(...origin)
          context.lineTo(...endpoint)
          context.lineWidth = 1.5
          context.strokeStyle = axisColour
          context.globalAlpha = 0.85
          context.stroke()
          context.globalAlpha = 1
          context.fillStyle = axisColour
          context.font = '12px IBM Plex Sans, sans-serif'
          context.fillText(label, endpoint[0] + 5, endpoint[1] - 5)
        })
      }
      context.save()
      context.translate(transform.x, transform.y)
      context.scale(transform.k, transform.k)
      const renderedPointById = new Map(renderedPoints.map((point) => [point.id, point]))
      const neighbourIds = new Set(view === 'neighbourhoods' ? relationLinks.map((link) => link.targetId) : [])
      if (view === 'comparative') {
        [[comparisonA, colour('--atlas-cohort-a')], [comparisonB, colour('--atlas-cohort-b')]].forEach(([ids, cohortColour]) => {
          const hull = d3.polygonHull(ids.map((id) => renderedPointById.get(id)).filter(Boolean).map((point) => [xScale(point.renderX), yScale(point.renderY)]))
          if (!hull) return
          context.beginPath()
          hull.forEach(([x, y], index) => index ? context.lineTo(x, y) : context.moveTo(x, y))
          context.closePath()
          context.fillStyle = cohortColour
          context.globalAlpha = 0.12
          context.fill()
          context.lineWidth = 1 / transform.k
          context.globalAlpha = 0.46
          context.strokeStyle = cohortColour
          context.stroke()
        })
      }
      if (view === 'neighbourhoods' && anchorId && renderedPointById.has(anchorId)) {
        const anchor = renderedPointById.get(anchorId)
        context.strokeStyle = colour('--atlas-view-accent')
        context.lineWidth = 1 / transform.k
        context.globalAlpha = 0.28
        ;[28, 56, 84].forEach((radius) => {
          context.beginPath()
          context.arc(xScale(anchor.renderX), yScale(anchor.renderY), radius / transform.k, 0, Math.PI * 2)
          context.stroke()
        })
      }
      relationLinks.forEach(({ sourceId, targetId }) => {
        const source = renderedPointById.get(sourceId)
        const target = renderedPointById.get(targetId)
        if (!source || !target) return
        context.beginPath()
        context.moveTo(xScale(source.renderX), yScale(source.renderY))
        context.lineTo(xScale(target.renderX), yScale(target.renderY))
        context.lineWidth = 1.5 / transform.k
        context.strokeStyle = colour('--atlas-focal')
        context.globalAlpha = 0.8
        context.stroke()
      })
      context.globalAlpha = 1
      renderedPoints.forEach((point) => {
        const selected = selectedIds.includes(point.id)
        const inA = comparisonA.includes(point.id)
        const inB = comparisonB.includes(point.id)
        const searched = searchIds.includes(point.id)
        const anchored = point.id === anchorId
        const originalSpaceNeighbour = neighbourIds.has(point.id)
        const criticalResult = view === 'critical' && searched
        context.beginPath()
        context.arc(xScale(point.renderX), yScale(point.renderY), (selected || anchored ? 5.5 : 2.15) + (dimensions === '3d' ? Math.max(-1, Math.min(1, point.depth)) : 0), 0, Math.PI * 2)
        const depthAlpha = dimensions === '3d' ? 0.48 + ((point.depth / coordinateSpan + 1) / 2) * 0.42 : 0.72
        const focused = selected || anchored || searched || inA || inB
        context.globalAlpha = selectedIds.length > 0 ? focused ? depthAlpha : 0.22 : depthAlpha
        context.fillStyle = selectedIds.length > 0 && !focused ? colour('--atlas-muted-point') : anchored ? colour('--atlas-focal') : originalSpaceNeighbour ? colour('--atlas-neighbour') : criticalResult ? colour('--atlas-critical') : inA && inB ? colour('--atlas-cohort-overlap') : inA ? colour('--atlas-cohort-a') : inB ? colour('--atlas-cohort-b') : pointColour(point, colorBy, colourScale, colour('--atlas-view-accent'), colour('--atlas-muted-point'), categoricalColours, sequentialColours)
        context.fill()
        if (selected || searched || anchored) {
          context.lineWidth = 2 / transform.k
          context.strokeStyle = colour('--atlas-label')
          context.stroke()
        }
      })
      if (labelBy !== 'none' || showTitleLabels) {
        renderedPoints.filter((point) => showTitleLabels || selectedIds.includes(point.id) || point.id === anchorId).forEach((point) => {
          const label = showTitleLabels ? point.title : labelBy === 'year' ? String(point.year || 'Unknown') : labelBy === 'theme' ? point.themes?.[0] : labelBy === 'source' ? point.title : point.clusterLabel
          context.globalAlpha = 1
          context.fillStyle = colour('--atlas-label')
          const titleScale = dimensions === '3d' ? 0.72 + ((point.depth / coordinateSpan + 1) / 2) * 0.76 : 1
          context.font = `${showTitleLabels ? 10 * titleScale : 11 / transform.k}px IBM Plex Sans, sans-serif`
          context.fillText(label || 'Unlabelled', xScale(point.renderX) + 7 / transform.k, yScale(point.renderY) - 7 / transform.k)
        })
      }
      context.restore()
      if (selectionRect) {
        const left = Math.min(selectionRect.startX, selectionRect.endX)
        const top = Math.min(selectionRect.startY, selectionRect.endY)
        context.save()
        context.fillStyle = colour('--atlas-selection')
        context.globalAlpha = 0.12
        context.strokeStyle = colour('--atlas-selection')
        context.lineWidth = 1
        context.setLineDash([4, 3])
        context.fillRect(left, top, Math.abs(selectionRect.endX - selectionRect.startX), Math.abs(selectionRect.endY - selectionRect.startY))
        context.strokeRect(left + 0.5, top + 0.5, Math.abs(selectionRect.endX - selectionRect.startX), Math.abs(selectionRect.endY - selectionRect.startY))
        context.restore()
      }
    }
    draw()
    const themeRoot = canvas.closest('.ddr-theme')
    const themeObserver = themeRoot ? new MutationObserver(draw) : null
    themeObserver?.observe(themeRoot, { attributes: true, attributeFilter: ['class'] })
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
    const suppressContextMenu = (event) => event.preventDefault()
    const startOrbit = (event) => {
      if (![0, 2].includes(event.button)) return
      if (boxSelectionEnabled) {
        if (event.button !== 0) return
        const [x, y] = d3.pointer(event, canvas)
        dragRef.current = { type: 'selection', startX: x, startY: y, endX: x, endY: y, moved: false, event }
        selectionRect = dragRef.current
        return
      }
      if (dimensions === '2d' || event.shiftKey || event.button === 2) {
        dragRef.current = { type: 'pan', x: event.clientX, y: event.clientY, transform: transformRef.current, moved: false }
        return
      }
      callbacksRef.current.onOrbitStart()
      callbacksRef.current.onCameraChange(elevation, renderedAzimuth)
      dragRef.current = { type: 'orbit', x: event.clientX, y: event.clientY, azimuth: renderedAzimuth, elevation, moved: false }
    }
    const orbit = (event) => {
      const drag = dragRef.current
      if (!drag) return
      if (drag.type === 'selection') {
        const [x, y] = d3.pointer(event, canvas)
        drag.endX = x
        drag.endY = y
        drag.moved ||= Math.abs(x - drag.startX) + Math.abs(y - drag.startY) > 3
        if (drag.moved) draw()
        return
      }
      if (drag.type === 'pan') {
        const deltaX = event.clientX - drag.x
        const deltaY = event.clientY - drag.y
        drag.moved ||= Math.abs(deltaX) + Math.abs(deltaY) > 3
        if (drag.moved) {
          event.preventDefault()
          transformRef.current = d3.zoomIdentity.translate(drag.transform.x + deltaX, drag.transform.y + deltaY).scale(drag.transform.k)
          draw()
        }
        return
      }
      const deltaX = event.clientX - drag.x
      const deltaY = event.clientY - drag.y
      drag.moved ||= Math.abs(deltaX) + Math.abs(deltaY) > 3
      if (drag.moved) {
        event.preventDefault()
        callbacksRef.current.onCameraChange(Math.max(-80, Math.min(80, drag.elevation - deltaY * 0.45)), ((drag.azimuth + deltaX * 0.45 + 180) % 360) - 180)
      }
    }
    const endOrbit = () => {
      const drag = dragRef.current
      if (!drag) return
      if (drag.type === 'selection' && drag.moved) {
        const left = Math.min(drag.startX, drag.endX)
        const right = Math.max(drag.startX, drag.endX)
        const top = Math.min(drag.startY, drag.endY)
        const bottom = Math.max(drag.startY, drag.endY)
        const transform = transformRef.current
        const enclosed = renderedPoints.filter((point) => {
          const x = xScale(point.renderX) * transform.k + transform.x
          const y = yScale(point.renderY) * transform.k + transform.y
          return x >= left && x <= right && y >= top && y <= bottom
        })
        callbacksRef.current.onSelectMany(enclosed, drag.event)
        selectionRect = null
        draw()
      }
      canvas.dataset.dragged = String(drag.moved)
      dragRef.current = null
    }
    canvas.addEventListener('click', onClick)
    canvas.addEventListener('mousemove', onMove)
    canvas.addEventListener('mousedown', startOrbit, true)
    canvas.addEventListener('mousemove', orbit, true)
    canvas.addEventListener('mouseup', endOrbit, true)
    canvas.addEventListener('contextmenu', suppressContextMenu)
    canvas.addEventListener('dblclick', onDoubleClick)
    return () => {
      canvas.removeEventListener('click', onClick)
      canvas.removeEventListener('mousemove', onMove)
      canvas.removeEventListener('mousedown', startOrbit, true)
      canvas.removeEventListener('mousemove', orbit, true)
      canvas.removeEventListener('mouseup', endOrbit, true)
      canvas.removeEventListener('contextmenu', suppressContextMenu)
      canvas.removeEventListener('dblclick', onDoubleClick)
      d3.select(canvas).on('.zoom', null)
      themeObserver?.disconnect()
      window.cancelAnimationFrame(animationFrame)
    }
  }, [points, size, view, dimensions, azimuth, elevation, autoRotate, boxSelectionEnabled, selectedIds, searchIds, anchorId, comparisonA, comparisonB, focusSelection, colorBy, labelBy, relationLinks, zAxisLabel])

  if (!points.length) return <div className="visual-analytics-workbench__empty-map">{emptyMessage || 'No points match the current corpus scope.'}</div>
  return <canvas ref={canvasRef} className={`visual-analytics-workbench__canvas ${boxSelectionEnabled ? 'visual-analytics-workbench__canvas--box-select' : ''}`} aria-label={ariaLabel} onDoubleClickCapture={(event) => { event.preventDefault(); onClearSelection() }} />
}

const VisualAnalyticsWorkbench = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const projectorOnly = searchParams.get('projector') === 'detached'
  const savedWorkspace = useMemo(readWorkspace, [])
  const [view, setView] = useState(() => searchParams.get('view') || savedWorkspace.view || 'atlas')
  const [controlTab, setControlTab] = useState(() => ['neighbourhoods', 'comparative', 'temporal', 'critical'].includes(searchParams.get('view') || savedWorkspace.view) ? 3 : 0)
  const [filters, setFilters] = useState(() => ({ ...DEFAULT_FILTERS, ...savedWorkspace.filters }))
  const [projection, setProjection] = useState({ points: [], metadata: {} })
  const [loading, setLoading] = useState(true)
  const [loadProgress, setLoadProgress] = useState({ loaded: 0, target: PROJECTION_RENDER_LIMIT, represented: null })
  const [error, setError] = useState('')
  const [savedInquiryId, setSavedInquiryId] = useState(() => savedWorkspace.inquiryId || null)
  const [search, setSearch] = useState(() => savedWorkspace.search || '')
  const [selectedIds, setSelectedIds] = useState(() => savedWorkspace.selectedIds || [])
  const [focusSelection, setFocusSelection] = useState(() => savedWorkspace.focusSelection ?? false)
  const [hovered, setHovered] = useState(null)
  const [anchorId, setAnchorId] = useState(() => savedWorkspace.anchorId || null)
  const [neighbourhoodK, setNeighbourhoodK] = useState(() => savedWorkspace.neighbourhoodK || NEIGHBOURHOOD_K.default)
  const [criticalResultCount, setCriticalResultCount] = useState(() => savedWorkspace.criticalResultCount || '25')
  const [embeddingNeighbours, setEmbeddingNeighbours] = useState([])
  const [neighbourhoodResult, setNeighbourhoodResult] = useState(null)
  const [queryFocal, setQueryFocal] = useState('')
  const [queryNeighbourhoodResult, setQueryNeighbourhoodResult] = useState(null)
  const [loadingQueryNeighbours, setLoadingQueryNeighbours] = useState(false)
  const [criticalConcept, setCriticalConcept] = useState(() => savedWorkspace.criticalConcept || '')
  const [criticalPresetId, setCriticalPresetId] = useState(() => savedWorkspace.criticalPresetId || '')
  const [criticalResults, setCriticalResults] = useState([])
  const [criticalProbeLabel, setCriticalProbeLabel] = useState('')
  const [criticalProbePolarity, setCriticalProbePolarity] = useState('positive')
  const [savedCriticalProbeId, setSavedCriticalProbeId] = useState(null)
  const [comparisonCriticalProbeId, setComparisonCriticalProbeId] = useState('')
  const [criticalProbeComparison, setCriticalProbeComparison] = useState(null)
  const [criticalCoverage, setCriticalCoverage] = useState(null)
  const [comparisonA, setComparisonA] = useState(() => savedWorkspace.comparisonA || [])
  const [comparisonB, setComparisonB] = useState(() => savedWorkspace.comparisonB || [])
  const [comparisonCohortA, setComparisonCohortA] = useState(() => savedWorkspace.comparisonCohortA || null)
  const [comparisonCohortB, setComparisonCohortB] = useState(() => savedWorkspace.comparisonCohortB || null)
  const [comparisonCohortNameA, setComparisonCohortNameA] = useState(() => savedWorkspace.comparisonCohortA?.name || 'Cohort A')
  const [comparisonCohortNameB, setComparisonCohortNameB] = useState(() => savedWorkspace.comparisonCohortB?.name || 'Cohort B')
  const [cohortNeighbourhoods, setCohortNeighbourhoods] = useState({})
  const [loadingCohortNeighbourhood, setLoadingCohortNeighbourhood] = useState('')
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
  const [alignedRuns, setAlignedRuns] = useState([])
  const [alignedRunsLimit, setAlignedRunsLimit] = useState('')
  const [alignedComparison, setAlignedComparison] = useState(null)
  const [alignedCoordinates, setAlignedCoordinates] = useState(null)
  const [alignedDisplayMode, setAlignedDisplayMode] = useState('surface')
  const [originalSpaceDensity, setOriginalSpaceDensity] = useState({ values: {}, limit: '' })
  const selectedTemporalPeriodA = temporalPeriods.find((period) => period.period_id === temporalPeriodA)
  const selectedTemporalPeriodB = temporalPeriods.find((period) => period.period_id === temporalPeriodB)
  const [annotationType, setAnnotationType] = useState('researcher_note')
  const [annotationControlledValue, setAnnotationControlledValue] = useState('')
  const [annotationResearcherValue, setAnnotationResearcherValue] = useState('')
  const [annotationValue, setAnnotationValue] = useState('')
  const [annotationStatus, setAnnotationStatus] = useState('draft')
  const [savedAnnotationId, setSavedAnnotationId] = useState(null)
  const [annotationRevisions, setAnnotationRevisions] = useState([])
  const [note, setNote] = useState(() => savedWorkspace.note || '')
  const [dimensions, setDimensions] = useState('3d')
  const [azimuth, setAzimuth] = useState(() => savedWorkspace.azimuth || 25)
  const [elevation, setElevation] = useState(() => savedWorkspace.elevation || 18)
  const [sphereView, setSphereView] = useState(false)
  const [boxSelectionEnabled, setBoxSelectionEnabled] = useState(false)
  const [hasBoxSelection, setHasBoxSelection] = useState(false)
  const [showEmbeddingNeighbours, setShowEmbeddingNeighbours] = useState(false)
  const [loadingNeighbours, setLoadingNeighbours] = useState(false)
  const [projectorDetached, setProjectorDetached] = useState(false)
  const [autoRotate, setAutoRotate] = useState(true)
  const [panels, setPanels] = useState({ controls: true, inspector: true })

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    setLoadProgress({ loaded: 0, target: PROJECTION_RENDER_LIMIT, represented: null })
    const loadProjection = async () => {
      let offset = 0
      let firstPayload = null
      let points = []
      while (offset < PROJECTION_RENDER_LIMIT) {
        const payload = await getUmapProjection({ point_type: filters.pointType, include_missingness: true, limit: PROJECTION_PAGE_SIZE, offset })
        if (cancelled) return
        firstPayload ||= payload
        const knownIds = new Set(points.map((point) => point.id))
        const nextPoints = (payload.points || []).filter((point) => !knownIds.has(point.id))
        points = [...points, ...nextPoints]
        const represented = payload.metadata?.evidenceSurfaceScope?.representedCount || payload.metadata?.evidenceSurfaceScope?.totalCandidates || null
        const target = Math.min(PROJECTION_RENDER_LIMIT, represented || PROJECTION_RENDER_LIMIT)
        setLoadProgress({ loaded: points.length, target, represented })
        if ((payload.points || []).length < PROJECTION_PAGE_SIZE || !nextPoints.length || points.length >= target) break
        offset += (payload.points || []).length
      }
      if (!cancelled && firstPayload) {
        setProjection({ ...firstPayload, points, metadata: { ...firstPayload.metadata, evidenceSurfaceScope: { ...firstPayload.metadata.evidenceSurfaceScope, renderedCount: points.length } } })
      }
    }
    loadProjection()
      .catch((requestError) => { if (!cancelled) setError(requestError.message || 'The embedding projection could not be loaded.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [filters.pointType])

  useEffect(() => {
    if (projectorOnly) return undefined
    const handleProjectorReattach = (event) => {
      if (event.origin !== window.location.origin || event.data?.type !== 'ddr-projector-reattach') return
      setProjectorDetached(false)
    }
    window.addEventListener('message', handleProjectorReattach)
    return () => window.removeEventListener('message', handleProjectorReattach)
  }, [projectorOnly])

  useEffect(() => {
    let cancelled = false
    getVisualTemporalPeriods().then((result) => { if (!cancelled) setTemporalPeriods(result.periods || []) }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    getAlignedUmapRuns().then((result) => {
      if (cancelled) return
      setAlignedRuns(result.runs || [])
      setAlignedRunsLimit(result.interpretation_limit || '')
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (view !== 'critical') return undefined
    let cancelled = false
    getMissingnessSummary().then((summary) => { if (!cancelled) setCriticalCoverage(summary) }).catch(() => { if (!cancelled) setCriticalCoverage(null) })
    return () => { cancelled = true }
  }, [view])

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
      setFocusSelection(workspace.focusSelection ?? false)
      setAnchorId(workspace.anchorId || null)
      setNeighbourhoodK(workspace.neighbourhoodK || NEIGHBOURHOOD_K.default)
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
    sessionStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify({ inquiryId: savedInquiryId, view, filters, search, selectedIds, focusSelection, anchorId, neighbourhoodK, criticalResultCount, criticalConcept, criticalPresetId, comparisonA, comparisonB, comparisonCohortA, comparisonCohortB, fidelityMode, temporalMode, temporalWindowA, temporalWindowB, alignedRunId, note, dimensions, azimuth, elevation, autoRotate, orbitVersion: 8 }))
  }, [savedInquiryId, view, filters, search, selectedIds, focusSelection, anchorId, neighbourhoodK, criticalResultCount, criticalConcept, criticalPresetId, comparisonA, comparisonB, comparisonCohortA, comparisonCohortB, fidelityMode, temporalMode, temporalWindowA, temporalWindowB, alignedRunId, note, dimensions, azimuth, elevation, autoRotate])

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
      const returnedNeighboursById = new Map(embeddingNeighbours.map((point) => [point.id, point]))
      const contextualPoints = visiblePoints.map((point) => returnedNeighboursById.get(point.id) || point)
      const contextualIds = new Set(contextualPoints.map((point) => point.id))
      return [...contextualPoints, ...embeddingNeighbours.filter((point) => !contextualIds.has(point.id))]
    }
    if (view === 'critical' && criticalPoints.length) {
      const returnedResultsById = new Map(criticalPoints.map((point) => [point.id, point]))
      const contextualPoints = visiblePoints.map((point) => returnedResultsById.get(point.id) || point)
      const contextualIds = new Set(contextualPoints.map((point) => point.id))
      return [...contextualPoints, ...criticalPoints.filter((point) => !contextualIds.has(point.id))]
    }
    return visiblePoints
  }, [anchorId, criticalPoints, embeddingNeighbours, projection.points, view, visiblePoints])
  const showingAlignedStaticSurface = view === 'temporal' && temporalMode === 'aligned' && Boolean(alignedCoordinates?.coordinates?.length)
  const showingAlignedTimeStack = showingAlignedStaticSurface && alignedDisplayMode === 'stack' && Boolean(alignedComparison?.relations?.length)
  const alignedStaticPoints = useMemo(() => {
    if (!showingAlignedStaticSurface) return []
    const sourceByChunkId = new Map(projection.points.map((point) => [point.chunkId || point.id, point]))
    return alignedCoordinates.coordinates.map((coordinate) => ({ ...sourceByChunkId.get(coordinate.chunk_id), id: `aligned:${coordinate.slice_id}:${coordinate.chunk_id}`, sourcePointId: coordinate.chunk_id, chunkId: coordinate.chunk_id, title: sourceByChunkId.get(coordinate.chunk_id)?.title || coordinate.chunk_id, x: coordinate.x, y: coordinate.y, z: coordinate.z, alignedSliceId: coordinate.slice_id }))
  }, [alignedCoordinates, projection.points, showingAlignedStaticSurface])
  const alignedTimeStackPoints = useMemo(() => {
    if (!showingAlignedTimeStack) return []
    const sliceOrders = new Map((alignedComparison.slices || []).map((slice) => [slice.slice_id, slice.slice_order]))
    const coordinateSpan = Math.max(...alignedStaticPoints.map((point) => Math.max(Math.abs(point.x), Math.abs(point.y))), 1)
    const midpoint = (sliceOrders.size - 1) / 2
    return alignedStaticPoints.map((point) => ({ ...point, z: ((sliceOrders.get(point.alignedSliceId) || 0) - midpoint) * coordinateSpan * 1.25 }))
  }, [alignedComparison, alignedStaticPoints, showingAlignedTimeStack])
  const alignedRelationLinks = useMemo(() => [
    ...(showingAlignedTimeStack ? (alignedComparison.relations || []).map((relation) => ({ sourceId: `aligned:${relation.from_slice_id}:${relation.source_point_id}`, targetId: `aligned:${relation.to_slice_id}:${relation.target_point_id}` })) : []),
    ...(view === 'neighbourhoods' && anchorId ? embeddingNeighbours.map((point) => ({ sourceId: anchorId, targetId: point.id })).filter((link) => link.sourceId !== link.targetId) : []),
  ], [alignedComparison, anchorId, embeddingNeighbours, showingAlignedTimeStack, view])
  const activeMapPoints = showingAlignedTimeStack ? alignedTimeStackPoints : showingAlignedStaticSurface ? alignedStaticPoints : mapPoints
  const displayPoints = useMemo(() => filters.colorBy === 'local_density' ? withProjectedLocalDensity(activeMapPoints) : filters.colorBy === 'original_space_density' ? activeMapPoints.map((point) => ({ ...point, originalSpaceDensity: originalSpaceDensity.values[point.chunkId] })) : activeMapPoints, [activeMapPoints, filters.colorBy, originalSpaceDensity.values])
  const pointById = useMemo(() => new Map(projection.points.map((point) => [point.id, point])), [projection.points])
  const displayPointById = useMemo(() => new Map([...projection.points, ...criticalPoints, ...embeddingNeighbours, ...alignedStaticPoints, ...alignedTimeStackPoints].map((point) => [point.id, point])), [alignedStaticPoints, alignedTimeStackPoints, criticalPoints, embeddingNeighbours, projection.points])
  const selectedPoints = selectedIds.map((id) => displayPointById.get(id)).filter(Boolean)
  const inspectorPoint = selectedPoints[selectedPoints.length - 1] || null
  const searchIds = useMemo(() => view === 'critical' ? criticalPoints.map((point) => point.id) : search ? visiblePoints.map((point) => point.id) : [], [criticalPoints, search, view, visiblePoints])
  const projectedNeighbours = useMemo(() => !inspectorPoint ? [] : projection.points.filter((point) => point.id !== inspectorPoint.id).map((point) => ({ ...point, projectedDistance: Math.hypot(point.x - inspectorPoint.x, point.y - inspectorPoint.y) })).sort((left, right) => left.projectedDistance - right.projectedDistance).slice(0, 8), [projection.points, inspectorPoint])
  const sourceTypes = useMemo(() => [...new Set(projection.points.map((point) => point.sourceType).filter(Boolean))].sort(), [projection.points])
  const requestedDocumentId = searchParams.get('documentId')
  const requestedDocumentIsUnrepresented = Boolean(
    requestedDocumentId && !projection.points.some((point) => point.documentId === requestedDocumentId)
  )
  const visibleCoverage = useMemo(() => {
    const documents = new Set(visiblePoints.map((point) => point.documentId).filter(Boolean))
    const chunks = visiblePoints.filter((point) => point.chunkId).length
    const pids = new Set(visiblePoints.map((point) => point.pid).filter(Boolean))
    const types = [...new Set(visiblePoints.map((point) => point.sourceType).filter(Boolean))].sort()
    const years = visiblePoints.map((point) => Number(point.year)).filter(Number.isFinite)
    const states = [...new Set(visiblePoints.map((point) => point.evidenceSurface?.representationState || 'not_exposed'))].sort()
    return { documents: documents.size, chunks, pids: pids.size, types, years, undated: visiblePoints.length - years.length, states }
  }, [visiblePoints])
  const colorLegendValues = useMemo(() => {
    if (!COLOR_MODE_LABELS[filters.colorBy]) return []
    if (filters.colorBy === 'local_density') return ['Lower local visual density', 'Higher local visual density']
    if (filters.colorBy === 'original_space_density') return ['Lower original-space density', 'Higher original-space density']
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
  const comparisonSummary = useMemo(() => {
    const cohortA = new Set(comparisonA)
    const cohortB = new Set(comparisonB)
    const overlap = [...cohortA].filter((id) => cohortB.has(id)).length
    return { aOnly: cohortA.size - overlap, overlap, bOnly: cohortB.size - overlap, total: new Set([...cohortA, ...cohortB]).size }
  }, [comparisonA, comparisonB])
  const neighbourhoodRankMaximum = useMemo(
    () => Math.max(1, ...embeddingNeighbours.map((point, index) => Number(point.rank) || index + 1)),
    [embeddingNeighbours]
  )
  const temporalSummary = useMemo(() => ({
    represented: projection.points.length,
    visible: visiblePoints.length,
    undated: projection.points.filter((point) => !point.year).length,
    excluded: projection.points.length - visiblePoints.length,
  }), [projection.points, visiblePoints])
  const temporalDocumentaryDistribution = useMemo(() => {
    const bins = new Map()
    visiblePoints.forEach((point) => {
      const year = Number(point.year)
      if (!Number.isFinite(year)) return
      const start = Math.floor(year / 5) * 5
      const current = bins.get(start) || { start, end: start + 4, count: 0, sourceTypes: new Set() }
      current.count += 1
      current.sourceTypes.add(point.sourceType || 'not_exposed')
      bins.set(start, current)
    })
    return [...bins.values()].sort((left, right) => left.start - right.start).map((bin) => ({ ...bin, sourceTypes: [...bin.sourceTypes].sort() }))
  }, [visiblePoints])
  const temporalDistributionMaximum = useMemo(
    () => Math.max(1, ...temporalDocumentaryDistribution.map((bin) => bin.count)),
    [temporalDocumentaryDistribution]
  )
  const temporalWindowSummary = useMemo(() => {
    const summarize = (window) => {
      const from = Number(window.from) || -Infinity
      const to = Number(window.to) || Infinity
      const dated = projection.points.filter((point) => Number.isFinite(Number(point.year)))
      return { represented: projection.points.length, inWindow: dated.filter((point) => Number(point.year) >= from && Number(point.year) <= to).length, undated: projection.points.length - dated.length }
    }
    return { a: summarize(temporalWindowA), b: summarize(temporalWindowB) }
  }, [projection.points, temporalWindowA, temporalWindowB])
  const temporalWindowComparison = useMemo(() => {
    const bounds = (window) => ({ from: Number(window.from), to: Number(window.to) })
    const a = bounds(temporalWindowA)
    const b = bounds(temporalWindowB)
    if (!Number.isFinite(a.from) || !Number.isFinite(a.to) || !Number.isFinite(b.from) || !Number.isFinite(b.to)) return null
    const labelsFor = (window) => new Map(projection.points.filter((point) => Number.isFinite(Number(point.year)) && Number(point.year) >= window.from && Number(point.year) <= window.to).reduce((groups, point) => {
      const label = point.clusterLabel || 'Unlabelled'
      groups.set(label, (groups.get(label) || 0) + 1)
      return groups
    }, new Map()))
    const labelsA = labelsFor(a)
    const labelsB = labelsFor(b)
    const labels = [...new Set([...labelsA.keys(), ...labelsB.keys()])].sort()
    return labels.map((label) => ({ label, a: labelsA.get(label) || 0, b: labelsB.get(label) || 0, membership: labelsA.has(label) && labelsB.has(label) ? 'Both windows' : labelsA.has(label) ? 'Window A only' : 'Window B only' }))
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

  useEffect(() => {
    if (filters.colorBy !== 'original_space_density') return undefined
    const chunkIds = [...new Set(mapPoints.map((point) => point.chunkId).filter(Boolean))]
    const embeddingSetId = projection.metadata.embeddingSetId
    if (!embeddingSetId || chunkIds.length < 3 || chunkIds.length > 200) {
      setOriginalSpaceDensity({ values: {}, limit: 'Original-space density is available only for 3-200 represented chunks with a declared embedding set.' })
      return undefined
    }
    let cancelled = false
    setOriginalSpaceDensity({ values: {}, limit: 'Calculating original-space density cue...' })
    getOriginalSpaceDensity({ chunk_ids: chunkIds, embedding_set_id: embeddingSetId }).then((result) => {
      if (cancelled) return
      setOriginalSpaceDensity({ values: Object.fromEntries((result.densities || []).map((density) => [density.chunk_id, density.density])), limit: result.metadata?.interpretation_limit || '' })
    }).catch((requestError) => {
      if (!cancelled) setOriginalSpaceDensity({ values: {}, limit: requestError.message || 'Original-space density is unavailable.' })
    })
    return () => { cancelled = true }
  }, [filters.colorBy, mapPoints, projection.metadata.embeddingSetId])

  const updateFilter = (field, value) => setFilters((current) => ({ ...current, [field]: value }))
  const selectPoint = (point, event) => {
    setAutoRotate(false)
    setHasBoxSelection(false)
    if (!point) { if (!(event?.shiftKey || event?.metaKey)) setSelectedIds([]); return }
    setPanels((current) => ({ ...current, inspector: true }))
    setSelectedIds((current) => event?.shiftKey || event?.metaKey ? (current.includes(point.id) ? current.filter((id) => id !== point.id) : [...current, point.id]) : [point.id])
  }
  const selectPoints = (points, event) => {
    setAutoRotate(false)
    setHasBoxSelection(true)
    const ids = points.map((point) => point.id)
    if (!ids.length && !(event?.shiftKey || event?.metaKey)) { setSelectedIds([]); return }
    setPanels((current) => ({ ...current, inspector: true }))
    setSelectedIds((current) => event?.shiftKey || event?.metaKey ? [...new Set([...current, ...ids])] : ids)
  }
  const clearSelection = () => { setSelectedIds([]); setAnchorId(null); setHovered(null); setHasBoxSelection(false); setShowEmbeddingNeighbours(false); setAutoRotate(false) }
  const loadNeighbours = async () => {
    const anchor = pointById.get(anchorId) || inspectorPoint
    if (!anchor?.chunkId) return
    setError('')
    setLoadingNeighbours(true)
    try {
      const result = await getSemanticNeighbourhood({ focal_chunk_id: anchor.chunkId, size: neighbourhoodK })
      setEmbeddingNeighbours((result.neighbours || []).map(normalizeNeighbour))
      setNeighbourhoodResult(result)
      setAnchorId(anchor.id)
    } catch (requestError) { setError(requestError.message || 'Embedding neighbours could not be loaded.') } finally { setLoadingNeighbours(false) }
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
  const loadQueryNeighbours = async () => {
    if (!queryFocal.trim()) return
    setLoadingQueryNeighbours(true)
    setError('')
    try {
      setQueryNeighbourhoodResult(await getQueryNeighbourhood({ query: queryFocal.trim(), size: neighbourhoodK }))
    } catch (requestError) { setError(requestError.message || 'The query neighbourhood could not be retrieved.') } finally { setLoadingQueryNeighbours(false) }
  }
  const loadCohortNeighbourhood = async (slot) => {
    const pointIds = slot === 'A' ? comparisonA : comparisonB
    const cohortName = slot === 'A' ? (comparisonCohortA?.name || comparisonCohortNameA) : (comparisonCohortB?.name || comparisonCohortNameB)
    const chunkIds = [...new Set(pointIds.map((id) => pointById.get(id)?.chunkId).filter(Boolean))]
    if (!chunkIds.length) {
      setError(`${cohortName} has no represented chunk points for original-space retrieval.`)
      return
    }
    setError('')
    setLoadingCohortNeighbourhood(slot)
    try {
      const result = await getCohortNeighbourhood({ cohort_name: cohortName, chunk_ids: chunkIds, size: neighbourhoodK })
      setCohortNeighbourhoods((current) => ({ ...current, [slot]: result }))
    } catch (requestError) { setError(requestError.message || `The ${cohortName} neighbourhood could not be retrieved.`) } finally { setLoadingCohortNeighbourhood('') }
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
  const loadAlignedCoordinates = async () => {
    if (!alignedRunId.trim()) return
    setError('')
    try {
      setAlignedCoordinates(await getAlignedUmapCoordinates(alignedRunId.trim()))
    } catch (requestError) {
      setAlignedCoordinates(null)
      setError(requestError.message || 'Aligned coordinates are unavailable.')
    }
  }
  const changeView = (nextView) => {
    setView(nextView)
    setFilters((current) => ({ ...current, colorBy: VIEW_PRESENTATION[nextView].colorBy }))
    if (nextView === 'temporal') setDimensions('2d')
    setControlTab(nextView === 'atlas' ? 0 : 3)
    navigate(nextView === 'atlas' ? '/visual-analytics' : `/visual-analytics?view=${nextView}`)
  }
  const recordAtlasCoverageCondition = async () => {
    if (!requestedDocumentIsUnrepresented) return
    try {
      const result = await createAtlasCoverageMissingness({
        document_id: requestedDocumentId,
        projection_id: projection.metadata.projectionId || projection.metadata.projection_id || null,
      })
      navigate(`/absences?eventId=${encodeURIComponent(result.event_id)}`)
    } catch (requestError) {
      setError(requestError.message || 'The computational coverage condition could not be recorded.')
    }
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
  const resetWorkspace = () => { sessionStorage.removeItem(WORKSPACE_STORAGE_KEY); setFilters(DEFAULT_FILTERS); setSearch(''); setSelectedIds([]); setAnchorId(null); setEmbeddingNeighbours([]); setNeighbourhoodResult(null); setNeighbourhoodK(NEIGHBOURHOOD_K.default); setNeighbourhoodKValue(String(NEIGHBOURHOOD_K.default)); setCriticalResultCount('25'); setComparisonA([]); setComparisonB([]); setComparisonCohortA(null); setComparisonCohortB(null); setComparisonCohortNameA('Cohort A'); setComparisonCohortNameB('Cohort B'); setCohortRuleSourceType(''); setCohortRuleTheme(''); setCohortRuleYearFrom(''); setCohortRuleYearTo(''); setCohortRuleOperator('and'); setFidelityMode('off'); setFidelityResult(null); setTemporalMode('fixed'); setAlignedRunId(''); setAlignedComparison(null); setAlignedCoordinates(null); setCriticalResults([]); setCriticalConcept(''); setCriticalPresetId(''); setSavedCriticalProbeId(null); setComparisonCriticalProbeId(''); setCriticalProbeComparison(null); setNote(''); setDimensions('3d'); setAzimuth(25); setElevation(18); setAutoRotate(true); changeView('atlas') }
  const showAllData = () => { setFilters((current) => ({ ...DEFAULT_FILTERS, pointType: current.pointType })); setSearch(''); clearSelection() }
  const handoff = (path) => {
    const params = new URLSearchParams()
    params.set('returnTo', 'visual-analytics')
    if (selectedPoints[0]?.documentId) params.set(path === '/absences' || path === '/cross-readings' ? 'sourceDocumentId' : 'documentId', selectedPoints[0].documentId)
    if (selectedPoints[0]?.chunkId) params.set('chunkId', selectedPoints[0].chunkId)
    if (selectedPoints[0]?.chunkId && (path === '/absences' || path === '/cross-readings')) params.set('sourceChunkId', selectedPoints[0].chunkId)
    if (selectedPoints[0]?.pid) params.set('pid', selectedPoints[0].pid)
    if (selectedPoints.length > 1) params.set('sourceDocumentIds', selectedPoints.map((point) => point.documentId).filter(Boolean).join(','))
    navigate(`${path}?${params.toString()}`)
  }
  const exportWorkspace = () => {
    const state = { exportedAt: new Date().toISOString(), view, filters, search, selectedPoints, focusSelection, comparisonA, comparisonB, comparisonCohortA, comparisonCohortB, fidelityMode, fidelityResult, temporalMode, temporalSummary, anchorId, neighbourhoodK, criticalPresetId, criticalConcept, criticalResultCount, note, projection: projection.metadata }
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' }))
    link.download = 'visual-analytics-workspace.json'
    link.click()
    URL.revokeObjectURL(link.href)
  }
  const saveInquiry = async () => {
    const workspace = { view, filters, search, selectedIds, focusSelection, anchorId, neighbourhoodK, criticalResultCount, criticalConcept, criticalPresetId, comparisonA, comparisonB, comparisonCohortA, comparisonCohortB, fidelityMode, temporalMode, temporalWindowA, temporalWindowB, alignedRunId, note, dimensions, azimuth, elevation }
    setError('')
    try {
      const inquiry = await createVisualInquiry({ view, note, projection_id: projection.metadata.projectionId, embedding_set_id: projection.metadata.embeddingSetId, workspace })
      setSavedInquiryId(inquiry.inquiry_id)
    } catch (requestError) { setError(requestError.message || 'The visual inquiry could not be saved.') }
  }
  const saveAnnotation = async () => {
    if (!inspectorPoint || !annotationValue.trim() || (ANNOTATION_RESEARCHER_VALUE_LABELS[annotationType] && !annotationResearcherValue.trim())) return
    setError('')
    try {
      const payload = { inquiry_id: savedInquiryId || null, document_id: inspectorPoint.documentId || null, chunk_id: inspectorPoint.chunkId || null, annotation_type: annotationType, value: { note: annotationValue.trim(), ...(ANNOTATION_CONTROLLED_VALUES[annotationType] ? { controlled_value: annotationControlledValue, vocabulary_version: 'visual-annotation-v1' } : {}), ...(ANNOTATION_RESEARCHER_VALUE_LABELS[annotationType] ? { researcher_value: annotationResearcherValue.trim() } : {}) }, evidence_source: 'Visual Analytics researcher annotation', status: annotationStatus }
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
  const exportCriticalPacket = (format) => {
    if (!criticalResults.length) return
    const packet = { exportedAt: new Date().toISOString(), workflow: 'critical_inquiry', proposition: criticalConcept.trim(), polarity: criticalProbePolarity, passages: criticalResults, projection: { projectionId: projection.metadata.projectionId, embeddingSetId: projection.metadata.embeddingSetId }, researcherNote: note, interpretationLimit: 'These are retrieval candidates for source review under a researcher-supplied proposition. They are not a classification, evidential confirmation, or statement about archival absence.' }
    if (format === 'json') { downloadFile('critical-inquiry-evidence-packet.json', `${JSON.stringify(packet, null, 2)}\n`, 'application/json;charset=utf-8'); return }
    const rows = criticalPoints.map((point) => `- ${point.title || 'Untitled trace'} | PID: ${point.pid || 'Unavailable'} | document: ${point.documentId || 'Unavailable'} | chunk: ${point.chunkId || point.id}\n  ${point.excerpt || 'No bounded excerpt available.'}`).join('\n')
    downloadFile('critical-inquiry-evidence-packet.md', `# Critical Inquiry Evidence Packet\n\n## Researcher Proposition\n${packet.proposition || 'Unavailable'}\n\n## Method\n- Retrieval: original-space embedding retrieval\n- Polarity: ${packet.polarity}\n- Projection: ${packet.projection.projectionId || 'Unavailable'}\n- Embedding set: ${packet.projection.embeddingSetId || 'Unavailable'}\n- Returned passages: ${packet.passages.length}\n\n## Retrieval Candidates\n${rows}\n\n## Researcher Note\n${note || 'None recorded.'}\n\n## Interpretation Limit\n${packet.interpretationLimit}\n`, 'text/markdown;charset=utf-8')
  }

  const openProjectorWindow = () => {
    window.open(`${window.location.pathname}?view=${encodeURIComponent(view)}&projector=detached`, 'ddr-projector', 'popup=yes,width=1280,height=900,resizable=yes,scrollbars=no')
    setProjectorDetached(true)
  }
  const reattachProjector = () => {
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage({ type: 'ddr-projector-reattach' }, window.location.origin)
      window.close()
      return
    }
    navigate(view === 'atlas' ? '/visual-analytics' : `/visual-analytics?view=${view}`)
  }

  return <main className={`visual-analytics-workbench visual-analytics-workbench--view-${view} ${projectorOnly ? 'visual-analytics-workbench--projector-only' : ''} ${projectorDetached ? 'visual-analytics-workbench--projector-detached' : ''} ${!panels.controls ? 'visual-analytics-workbench--controls-collapsed' : ''} ${!panels.inspector ? 'visual-analytics-workbench--inspector-collapsed' : ''}`}>
    {!panels.controls && <Button className="visual-analytics-workbench__restore-panel visual-analytics-workbench__restore-panel--controls" kind="ghost" size="sm" renderIcon={ChevronRight} onClick={() => setPanels((current) => ({ ...current, controls: true }))}>Show tools</Button>}
    {!panels.inspector && <Button className="visual-analytics-workbench__restore-panel visual-analytics-workbench__restore-panel--inspector" kind="ghost" size="sm" renderIcon={ChevronLeft} onClick={() => setPanels((current) => ({ ...current, inspector: true }))}>Show inspector</Button>}
    <aside className="visual-analytics-workbench__controls">
      <div className="visual-analytics-workbench__control-header"><Select id="analytics-view" labelText="Analysis view" value={view} onChange={(event) => changeView(event.target.value)}>{VIEWS.map(([value, label]) => <SelectItem key={value} value={value} text={label} />)}</Select><div className="visual-analytics-workbench__control-actions"><Button kind="ghost" size="sm" renderIcon={Renew} onClick={resetWorkspace}>Reset</Button><Button className="visual-analytics-workbench__control-collapse" kind="ghost" size="sm" renderIcon={View} onClick={() => setPanels((current) => ({ ...current, controls: false }))}>Collapse</Button></div></div>
      <Tabs selectedIndex={controlTab} onChange={({ selectedIndex }) => setControlTab(selectedIndex)} className="visual-analytics-workbench__control-tabs">
        <TabList aria-label="Visual Analytics controls"><Tab>Data</Tab><Tab>Display</Tab><Tab>UMAP</Tab>{view !== 'atlas' && <Tab>{view === 'neighbourhoods' ? 'Neighbours' : view === 'comparative' ? 'Compare' : view === 'temporal' ? 'Time' : 'Inquiry'}</Tab>}</TabList>
      </Tabs>
      <Accordion align="start" className="visual-analytics-workbench__control-panels">
        {controlTab === 0 && <AccordionItem title="Data" open>
          <Select id="point-type" labelText="Point type" value={filters.pointType} onChange={(event) => updateFilter('pointType', event.target.value)}><SelectItem value="chunks" text="Chunks" /><SelectItem value="documents" text="Documents" /></Select>
          <div className="visual-analytics-workbench__year-range"><div className="visual-analytics-workbench__year-range-header"><span>Date range</span><strong>{filters.yearMin || 1965}-{filters.yearMax || 1985}</strong></div><Slider id="year-range" labelText="" ariaLabelInput="Date range" min={1965} max={1985} step={1} value={Number(filters.yearMin || 1965)} unstable_valueUpper={Number(filters.yearMax || 1985)} onChange={({ value, valueUpper }) => { updateFilter('yearMin', String(value)); updateFilter('yearMax', String(valueUpper)) }} /><div className="visual-analytics-workbench__year-range-limits"><span>1965</span><span>1985</span></div></div>
          <Select id="source-type" labelText="Source type" value={filters.sourceType} onChange={(event) => updateFilter('sourceType', event.target.value)}><SelectItem value="" text="All source types" />{sourceTypes.map((type) => <SelectItem key={type} value={type} text={type} />)}</Select>
        </AccordionItem>}
        {controlTab === 1 && <AccordionItem title="Display" open>
          <Select id="colour-by" labelText="Colour by" value={filters.colorBy} onChange={(event) => updateFilter('colorBy', event.target.value)}><SelectItem value="view" text="View accent" /><SelectItem value="none" text="None" /><SelectItem value="cluster" text="Cluster" /><SelectItem value="year" text="Year" /><SelectItem value="source_type" text="Source type" /><SelectItem value="representation" text="Representation state" /><SelectItem value="missingness" text="Missingness state" /><SelectItem value="archive_authority" text="Archive authority state" /><SelectItem value="database_authority" text="Database authority linkage" /><SelectItem value="annotation" text="Researcher annotation status" /><SelectItem value="local_density" text="Projected local visual density" /><SelectItem value="original_space_density" text="Original embedding-space density cue" /><SelectItem value="documentary_file_type" text="Documentary file type" /><SelectItem value="documentary_extraction" text="Documentary extraction state" /><SelectItem value="documentary_rights" text="Documentary rights/access state" /><SelectItem value="documentary_metadata" text="Documentary metadata completeness" /><SelectItem value="documentary_text_length" text="Document text-length band" /><SelectItem value="documentary_chunk_count" text="Document chunk-count band" /></Select>
          <Select id="label-by" labelText="Label selected points by" value={filters.labelBy} onChange={(event) => updateFilter('labelBy', event.target.value)}><SelectItem value="none" text="None" /><SelectItem value="source" text="Source" /><SelectItem value="year" text="Year" /><SelectItem value="cluster" text="Cluster" /></Select>
        </AccordionItem>}
        {controlTab === 2 && <AccordionItem title="UMAP" open>
          <p>UMAP coordinates are stored, versioned projections. Parameters cannot be changed here without recomputation.</p>
          <Tag type="gray">{projection.metadata.projectionMethod || 'UMAP'}</Tag>
          <Toggle id="projection-dimensions" labelText="Dimension" labelA="2D" labelB="3D" toggled={activeDimensions === '3d'} onToggle={(toggled) => setDimensions(toggled ? '3d' : '2d')} disabled={!has3dProjection} />
          <div className="visual-analytics-workbench__neighbourhood-slider"><Slider id="neighbourhood-size" labelText="Neighbours" min={NEIGHBOURHOOD_K.min} max={NEIGHBOURHOOD_K.max} step={NEIGHBOURHOOD_K.step} value={neighbourhoodK} onChange={({ value }) => setNeighbourhoodK(value)} /></div>
          <p>Neighbours controls the size of an explicit original-space neighbourhood request. It does not alter the stored UMAP projection or its parameters.</p>
          {activeDimensions === '3d' && <Toggle id="sphere-view" labelText="Sphere view" labelA="Flat" labelB="Sphere" toggled={sphereView} onToggle={setSphereView} />}
          {activeDimensions === '3d' && <><Slider id="projection-azimuth" labelText="Horizontal orbit" min={-180} max={180} value={azimuth} onChange={({ value }) => { setAutoRotate(false); setAzimuth(value) }} /><Slider id="projection-elevation" labelText="Vertical orbit" min={-80} max={80} value={elevation} onChange={({ value }) => { setAutoRotate(false); setElevation(value) }} /><Button kind="ghost" size="sm" renderIcon={autoRotate ? Pause : Play} onClick={() => setAutoRotate((current) => !current)}>{autoRotate ? 'Pause orbit' : 'Resume orbit'}</Button><p>The Atlas opens in a slow orbit. Mouse down stops it; drag to inspect the stored 3D projection.</p></>}
        </AccordionItem>}
        {controlTab === 3 && <>
        {view === 'neighbourhoods' && <AccordionItem title="Semantic neighbourhood" open>
          <Button size="sm" onClick={loadNeighbours} disabled={!inspectorPoint?.chunkId || loadingNeighbours}>{loadingNeighbours ? 'Fetching nearest neighbours' : 'Explore neighbourhood'}</Button>
          {loadingNeighbours && <InlineLoading description={`Fetching nearest neighbours: 0 / ${neighbourhoodK} returned`} />}
          {!loadingNeighbours && neighbourhoodResult && <p>Nearest neighbours returned: {neighbourhoodResult.metadata?.returned_k || embeddingNeighbours.length} / {neighbourhoodResult.metadata?.requested_k || neighbourhoodK}</p>}
          <TextInput id="query-focal" labelText="Researcher query focal" placeholder="e.g. technical maintenance" value={queryFocal} onChange={(event) => setQueryFocal(event.target.value)} />
          <Button size="sm" kind="secondary" onClick={loadQueryNeighbours} disabled={!queryFocal.trim() || loadingQueryNeighbours}>{loadingQueryNeighbours ? 'Retrieving query neighbours' : 'Explore query neighbourhood'}</Button>
          {loadingQueryNeighbours && <InlineLoading description={`Retrieving query neighbours: 0 / ${neighbourhoodK} returned`} />}
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
          <Button size="sm" kind="secondary" onClick={() => loadCohortNeighbourhood('A')} disabled={!comparisonA.some((id) => pointById.get(id)?.chunkId) || Boolean(loadingCohortNeighbourhood)}>{loadingCohortNeighbourhood === 'A' ? 'Retrieving cohort A neighbours' : 'Explore cohort A neighbourhood'}</Button>
          <Button size="sm" kind="secondary" onClick={() => loadCohortNeighbourhood('B')} disabled={!comparisonB.some((id) => pointById.get(id)?.chunkId) || Boolean(loadingCohortNeighbourhood)}>{loadingCohortNeighbourhood === 'B' ? 'Retrieving cohort B neighbours' : 'Explore cohort B neighbourhood'}</Button>
          {loadingCohortNeighbourhood && <InlineLoading description={`Retrieving cohort ${loadingCohortNeighbourhood} neighbours: 0 / ${neighbourhoodK} returned`} />}
          <Select id="projection-fidelity" labelText="Projection fidelity" value={fidelityMode} onChange={(event) => setFidelityMode(event.target.value)} disabled={!comparisonA.length && !comparisonB.length}><SelectItem value="off" text="Off" /><SelectItem value="show" text="Show neighbourhood preservation" /></Select>
          {fidelityResult?.unavailable && <Tag type="warm-gray">{fidelityResult.unavailable}</Tag>}
          {fidelityResult?.metadata && <p>Neighbourhood preservation: {fidelityResult.results?.length ? (fidelityResult.results.reduce((sum, result) => sum + (result.jaccard_overlap || 0), 0) / fidelityResult.results.length).toFixed(2) : 'Unavailable'} | {fidelityResult.metadata.method}. This is not historical confidence.</p>}
        </AccordionItem>}
        {view === 'temporal' && <AccordionItem title="Temporal scope" open><Select id="temporal-mode" labelText="Temporal mode" value={temporalMode} onChange={(event) => setTemporalMode(event.target.value)}><SelectItem value="fixed" text="Fixed projection" /><SelectItem value="aligned" text="Aligned change (unavailable)" disabled /></Select><Select id="temporal-period-a" labelText="Authority period A" value={temporalPeriodA} onChange={(event) => { const period = temporalPeriods.find((item) => item.period_id === event.target.value); setTemporalPeriodA(event.target.value); if (period) setTemporalWindowA({ from: String(period.start_year || ''), to: String(period.end_year || '') }) }}><SelectItem value="" text="Custom window" />{temporalPeriods.map((period) => <SelectItem key={period.period_id} value={period.period_id} text={period.label} />)}</Select>{selectedTemporalPeriodA && <p>Window A authority: {selectedTemporalPeriodA.authority_source} ({selectedTemporalPeriodA.certainty}){selectedTemporalPeriodA.notes ? ` - ${selectedTemporalPeriodA.notes}` : ''}</p>}<Select id="temporal-period-b" labelText="Authority period B" value={temporalPeriodB} onChange={(event) => { const period = temporalPeriods.find((item) => item.period_id === event.target.value); setTemporalPeriodB(event.target.value); if (period) setTemporalWindowB({ from: String(period.start_year || ''), to: String(period.end_year || '') }) }}><SelectItem value="" text="Custom window" />{temporalPeriods.map((period) => <SelectItem key={period.period_id} value={period.period_id} text={period.label} />)}</Select>{selectedTemporalPeriodB && <p>Window B authority: {selectedTemporalPeriodB.authority_source} ({selectedTemporalPeriodB.certainty}){selectedTemporalPeriodB.notes ? ` - ${selectedTemporalPeriodB.notes}` : ''}</p>}<div className="visual-analytics-workbench__temporal-windows"><TextInput id="temporal-a-from" labelText="Window A from" value={temporalWindowA.from} onChange={(event) => setTemporalWindowA((current) => ({ ...current, from: event.target.value.replace(/[^0-9]/g, '') }))} /><TextInput id="temporal-a-to" labelText="Window A to" value={temporalWindowA.to} onChange={(event) => setTemporalWindowA((current) => ({ ...current, to: event.target.value.replace(/[^0-9]/g, '') }))} /><TextInput id="temporal-b-from" labelText="Window B from" value={temporalWindowB.from} onChange={(event) => setTemporalWindowB((current) => ({ ...current, from: event.target.value.replace(/[^0-9]/g, '') }))} /><TextInput id="temporal-b-to" labelText="Window B to" value={temporalWindowB.to} onChange={(event) => setTemporalWindowB((current) => ({ ...current, to: event.target.value.replace(/[^0-9]/g, '') }))} /></div><p>Fixed projection filters change visibility and encoding only. They do not recompute or move stored UMAP coordinates.</p><p>The saved windows support documentary comparison within that fixed projection.</p><Tag type="gray">Represented: {temporalSummary.represented} | Visible: {temporalSummary.visible} | Excluded: {temporalSummary.excluded} | Undated: {temporalSummary.undated}</Tag><Tag type="blue">Window A: {temporalWindowSummary.a.inWindow} dated in scope | {temporalWindowSummary.a.undated} undated</Tag><Tag type="purple">Window B: {temporalWindowSummary.b.inWindow} dated in scope | {temporalWindowSummary.b.undated} undated</Tag><Tag type="warm-gray">Aligned change requires explicit consecutive relation mappings and a separately versioned aligned run.</Tag></AccordionItem>}
        {view === 'critical' && <AccordionItem title="Critical inquiry" open><p>Critical lens supplied by researcher. Computational proximity indicates material for investigation, not confirmation of the proposition.</p><Select id="critical-lens-preset" labelText="Researcher lens preset" value={criticalPresetId} onChange={(event) => { const preset = CRITICAL_LENS_PRESETS.find((item) => item.id === event.target.value); setCriticalPresetId(event.target.value); if (preset) setCriticalConcept(preset.text) }}><SelectItem value="" text="No preset" />{CRITICAL_LENS_PRESETS.map((preset) => <SelectItem key={preset.id} value={preset.id} text={preset.label} />)}</Select><TextInput id="critical-concept" labelText="Concept or proposition" placeholder="e.g. unacknowledged technical labour" value={criticalConcept} onChange={(event) => setCriticalConcept(event.target.value)} /><Select id="critical-result-count" labelText="Passages to inspect" value={criticalResultCount} onChange={(event) => setCriticalResultCount(event.target.value)}>{['10', '25', '50'].map((value) => <SelectItem key={value} value={value} text={value} />)}</Select><Button size="sm" onClick={runProbe} disabled={!criticalConcept.trim()}>Investigate concept</Button><TextInput id="critical-probe-label" labelText="Probe record label" value={criticalProbeLabel} onChange={(event) => setCriticalProbeLabel(event.target.value)} /><Select id="critical-probe-polarity" labelText="Researcher probe polarity" value={criticalProbePolarity} onChange={(event) => setCriticalProbePolarity(event.target.value)}><SelectItem value="positive" text="Positive probe" /><SelectItem value="negative" text="Negative probe" /></Select><Button size="sm" kind="secondary" onClick={saveCriticalProbe} disabled={!criticalResults.length}>Save probe record</Button>{savedCriticalProbeId && <><Tag type="green">Saved probe: {savedCriticalProbeId}</Tag><TextInput id="critical-comparison-probe-id" labelText="Saved probe ID to compare" value={comparisonCriticalProbeId} onChange={(event) => setComparisonCriticalProbeId(event.target.value)} /><Button size="sm" kind="tertiary" onClick={compareCriticalProbes} disabled={!comparisonCriticalProbeId.trim()}>Compare saved probes</Button></>}{criticalProbeComparison && <p>Saved-probe comparison: current {criticalProbeComparison.currentCount} results | comparison {criticalProbeComparison.comparisonCount} results | overlap {criticalProbeComparison.overlapCount}. Result overlap identifies shared retrieval candidates, not evidential confirmation.</p>}<Tag type="warm-gray">Original-space retrieval only. A transformed researcher-probe marker is unavailable until a compatible retained reducer is verified.</Tag><Tag type="warm-gray">Image-only: {scope.imageOnlyRecords ?? 0}</Tag></AccordionItem>}
        {view === 'temporal' && <AccordionItem title="Validated aligned-run provenance"><Select id="aligned-run-picker" labelText="Recorded aligned run" value={alignedRunId} onChange={(event) => { setAlignedRunId(event.target.value); setAlignedCoordinates(null) }}><SelectItem value="" text="Select a recorded run" />{alignedRuns.map((run) => <SelectItem key={run.aligned_run_id} value={run.aligned_run_id} text={`${run.aligned_run_id} | ${run.status} | ${run.slice_count} slices | ${run.relation_count} relations`} />)}</Select>{alignedRuns.length > 0 && <div className="visual-analytics-workbench__aligned-run-statuses">{alignedRuns.map((run) => <Tag key={run.aligned_run_id} type={run.status === 'validated' ? 'green' : run.status === 'invalid' ? 'red' : 'warm-gray'}>{run.aligned_run_id}: {run.status}</Tag>)}</div>}<TextInput id="aligned-run-id" labelText="Validated aligned run ID" value={alignedRunId} onChange={(event) => { setAlignedRunId(event.target.value); setAlignedCoordinates(null) }} /><Button size="sm" kind="secondary" onClick={loadAlignedComparison} disabled={!alignedRunId.trim()}>Load static comparison</Button><Button size="sm" kind="ghost" onClick={loadAlignedCoordinates} disabled={!alignedRunId.trim()}>Check persisted coordinates</Button>{alignedComparison && <><Tag type="green">Validated run: {alignedComparison.aligned_run?.aligned_run_id}</Tag><p>{alignedComparison.slices?.length || 0} reviewed slices | {alignedComparison.relations?.length || 0} explicit consecutive relations</p><ol>{(alignedComparison.slices || []).map((slice) => <li key={slice.slice_id}>{slice.slice_order}: {slice.period_provenance?.label || slice.slice_id} ({slice.point_count} declared points)</li>)}</ol><p>{alignedComparison.interpretation_limit}</p></>}{alignedCoordinates && <><Tag type="green">Persisted coordinates: {alignedCoordinates.coordinates?.length || 0}</Tag><p>{alignedCoordinates.interpretation_limit}</p></>}<p>{alignedRunsLimit || 'Readiness status records relation validation only. It does not indicate that aligned coordinates, trails, or historical continuity are available.'}</p><p>Static comparison exposes only validated relation provenance. It does not generate coordinates, trails, animation, or historical continuity.</p></AccordionItem>}
        </>}
      </Accordion>
    </aside>
    <section className="visual-analytics-workbench__map-region">
      <div className="visual-analytics-workbench__map-status" aria-label="Projection status"><div className="visual-analytics-workbench__map-tools">{projectorOnly ? <Button kind="ghost" size="sm" renderIcon={ChevronLeft} onClick={reattachProjector}>Reattach</Button> : <Button kind="ghost" size="sm" hasIconOnly renderIcon={Launch} iconDescription="Open detached projector" tooltipPosition="bottom" onClick={openProjectorWindow} />}<Button kind={boxSelectionEnabled ? 'primary' : 'ghost'} size="sm" hasIconOnly renderIcon={DataVis_4} iconDescription="Bounding box selection" tooltipPosition="bottom" onClick={() => setBoxSelectionEnabled((current) => !current)} /><Button className="visual-analytics-workbench__labels-toggle" kind={filters.labelBy === 'source' ? 'primary' : 'ghost'} size="sm" hasIconOnly renderIcon={TextFont} iconDescription="Enable or disable title labels" tooltipPosition="bottom" onClick={() => updateFilter('labelBy', filters.labelBy === 'source' ? 'none' : 'source')} /></div><span className="visual-analytics-workbench__mode-marker">{VIEW_PRESENTATION[view].number} {VIEW_PRESENTATION[view].label}</span><span>Displayed: {displayPoints.length.toLocaleString()}</span><span>Dimension: {projection.metadata.embeddingDimension || projection.metadata.embedding_dimension || `${showingAlignedTimeStack ? '3D time/slice' : showingAlignedStaticSurface ? '2D aligned' : activeDimensions.toUpperCase()}`}</span>{hovered && <span>{pointLabel(hovered.point)} | {hovered.point.year || 'Undated'}</span>}{hasBoxSelection && selectedIds.length > 0 && <span>Selected: {selectedIds.length.toLocaleString()}</span>}</div>
      {!loading && <MapVisualLegend view={view} colorBy={filters.colorBy} points={displayPoints} anchorId={anchorId} comparisonA={comparisonA} comparisonB={comparisonB} />}
      {error && <InlineNotification className="visual-analytics-workbench__notification" lowContrast kind="error" title="Visual analytics unavailable" subtitle={error} />}
      {loading && <div className="visual-analytics-workbench__loading-count" role="status">Loading projection records: {loadProgress.loaded.toLocaleString()} / {loadProgress.target.toLocaleString()}{loadProgress.represented ? ` requested (${loadProgress.represented.toLocaleString()} represented)` : ' requested'}</div>}
      {view === 'temporal' && alignedCoordinates?.coordinates?.length > 0 && <div className="visual-analytics-workbench__aligned-surface-control"><Button size="sm" kind="secondary" onClick={() => { setTemporalMode(showingAlignedStaticSurface ? 'fixed' : 'aligned'); setAlignedDisplayMode('surface'); setAutoRotate(false); clearSelection() }}>{showingAlignedStaticSurface ? 'Return to fixed baseline' : 'Show aligned static surface'}</Button>{showingAlignedStaticSurface && alignedComparison?.relations?.length > 0 && <Button size="sm" kind="ghost" onClick={() => { setAlignedDisplayMode(showingAlignedTimeStack ? 'surface' : 'stack'); setAutoRotate(false); clearSelection() }}>{showingAlignedTimeStack ? 'Show aligned static surface' : 'Show Time stack'}</Button>}<p>Separately persisted aligned coordinate surface, not the baseline Atlas. It does not establish historical trajectories, continuity, or causation.</p>{showingAlignedTimeStack && <p>Time stack: z is documentary time/slice. Orange segments are only reviewed explicit relation mappings; no animation or inferred trajectory is shown.</p>}</div>}
      {loading ? <div className="visual-analytics-workbench__loading-surface" aria-live="polite"><ProgressBar label="Fetching stored projection" helperText="Waiting for the projection service to return represented records" status="active" /></div> : <>{showingAlignedStaticSurface && <InlineNotification lowContrast kind="info" title={showingAlignedTimeStack ? 'Aligned Time stack' : 'Aligned static surface'} subtitle={showingAlignedTimeStack ? 'z is documentary time/slice. Segments represent reviewed explicit mappings only; they do not establish continuity or causation.' : 'Separately generated coordinates for the selected validated run. This view does not create trails, continuity, causation, or a baseline replacement.'} />}<EmbeddingCanvas points={displayPoints} view={view} sphereView={sphereView && !showingAlignedTimeStack} emptyMessage={atlasUnavailable ? `Semantic atlas unavailable: this corpus has no embedding vectors. Full-text retrieval remains active across ${activeCorpusSummary}.` : view === 'neighbourhoods' ? 'Select a focal archival passage, then choose Explore neighbourhood.' : view === 'critical' ? 'Enter a researcher-supplied critical concept to inspect nearby archival passages.' : projection.message} dimensions={showingAlignedTimeStack ? '3d' : showingAlignedStaticSurface ? '2d' : activeDimensions} azimuth={azimuth} elevation={elevation} autoRotate={showingAlignedStaticSurface ? false : autoRotate} boxSelectionEnabled={boxSelectionEnabled} selectedIds={selectedIds} searchIds={searchIds} anchorId={anchorId} comparisonA={comparisonA} comparisonB={comparisonB} focusSelection={focusSelection} colorBy={filters.colorBy} labelBy={filters.labelBy} relationLinks={alignedRelationLinks} zAxisLabel={showingAlignedTimeStack ? 'time/slice' : 'z'} ariaLabel={showingAlignedTimeStack ? 'Aligned UMAP Time stack with documentary time slice axis' : view === 'temporal' ? 'Interactive temporal UMAP layout with separate undated lane' : 'Interactive UMAP embedding map'} onSelect={selectPoint} onSelectMany={selectPoints} onHover={setHovered} onCameraChange={(nextElevation, nextAzimuth) => { setAutoRotate(false); setElevation(nextElevation); setAzimuth(nextAzimuth) }} onOrbitStart={() => setAutoRotate(false)} onClearSelection={clearSelection} /></>}
      {hovered && <div className="visual-analytics-workbench__hover" style={{ left: hovered.x + 14, top: hovered.y + 14 }}><strong>{pointLabel(hovered.point)}</strong><span>{hovered.point.year || 'Undated'}</span></div>}
    </section>
    <aside className="visual-analytics-workbench__inspector">
      <div className="visual-analytics-workbench__inspector-header"><Search id="atlas-search" labelText="Search corpus" placeholder="Search corpus..." value={search} onChange={(event) => setSearch(event.target.value)} /></div>
      <div className="visual-analytics-workbench__inspector-tools"><Button kind="ghost" size="sm" renderIcon={Download} onClick={exportWorkspace}>Download</Button><div className="visual-analytics-workbench__download"><OverflowMenu aria-label="More download options" iconDescription="More download options" size="sm" flipped>
          <OverflowMenuItem itemText={savedInquiryId ? `Saved inquiry: ${savedInquiryId}` : 'Save durable inquiry'} onClick={saveInquiry} />
          <OverflowMenuItem itemText="Save workspace data" onClick={exportWorkspace} />
          <OverflowMenuItem itemText="Save view as PNG" onClick={exportImage} />
          <OverflowMenuItem itemText="Save view as SVG" onClick={exportSvg} />
          <OverflowMenuItem itemText="Save observation as text" onClick={exportText} />
          {view === 'comparative' && <OverflowMenuItem itemText="Export cohort comparison (CSV)" disabled={!comparisonA.length && !comparisonB.length} onClick={exportComparisonCohorts} />}
          {view === 'neighbourhoods' && <><OverflowMenuItem itemText="Export neighbourhood evidence packet (JSON)" disabled={!neighbourhoodResult} onClick={() => exportNeighbourhoodPacket('json')} /><OverflowMenuItem itemText="Export neighbourhood evidence packet (Markdown)" disabled={!neighbourhoodResult} onClick={() => exportNeighbourhoodPacket('markdown')} /></>}
          {view === 'critical' && <><OverflowMenuItem itemText="Export critical inquiry evidence packet (JSON)" disabled={!criticalResults.length} onClick={() => exportCriticalPacket('json')} /><OverflowMenuItem itemText="Export critical inquiry evidence packet (Markdown)" disabled={!criticalResults.length} onClick={() => exportCriticalPacket('markdown')} /></>}
        </OverflowMenu></div><Button kind="ghost" size="sm" renderIcon={View} onClick={() => setPanels((current) => ({ ...current, inspector: false }))}>Collapse</Button></div>
      <div className="visual-analytics-workbench__selection-actions"><Button size="sm" kind="secondary" onClick={showAllData}>Show all data</Button><Button size="sm" kind="secondary" onClick={clearSelection} disabled={!selectedIds.length}>Clear selection</Button></div>
      {!inspectorPoint && <Tile className="visual-analytics-workbench__view-context">
        <h2>{atlasUnavailable ? 'Semantic atlas unavailable' : VIEWS.find(([key]) => key === view)?.[1]}</h2>
        <p>{atlasUnavailable ? `The active corpus is available for full-text retrieval, but no embedding vectors are present for a spatial projection. This is a computational capability state, not archival absence.` : VIEW_FRAMING[view]}</p>
        <Tag type="blue">{atlasUnavailable ? `FTS retrieval: ${activeCorpusSummary}` : evidenceSurfaceCounts}</Tag>
      </Tile>}
      {!inspectorPoint && COLOR_MODE_LABELS[filters.colorBy] && <Tile><h2>Display legend</h2><p>Colour encodes {COLOR_MODE_LABELS[filters.colorBy]}. {filters.colorBy === 'local_density' ? 'It is derived from distances between displayed stored coordinates; it does not indicate historical concentration, significance, or archive completeness.' : filters.colorBy === 'original_space_density' ? originalSpaceDensity.limit || 'Original embedding-space density is being calculated.' : ['documentary_text_length', 'documentary_chunk_count'].includes(filters.colorBy) ? 'These are returned measures for the represented database document, not an archive-wide total or a measure of historical significance.' : filters.colorBy.startsWith('documentary_') ? 'These are returned documentary representation fields. Not exposed or not evaluated states are not evidence of access, rights, completeness, or archival absence.' : 'This is a display field, not a historical conclusion.'}</p><div className="visual-analytics-workbench__legend-values">{colorLegendValues.length ? colorLegendValues.slice(0, 12).map((value) => <Tag key={String(value)} type="gray">{value}</Tag>) : <Tag type="warm-gray">Unavailable</Tag>}</div></Tile>}
      {!inspectorPoint && <Tile aria-label="Visible-set coverage"><h2>Visible-set coverage</h2><dl><dt>Documents</dt><dd>{visibleCoverage.documents}</dd><dt>Chunks</dt><dd>{visibleCoverage.chunks}</dd><dt>PIDs</dt><dd>{visibleCoverage.pids}</dd><dt>Source types</dt><dd>{visibleCoverage.types.join(', ') || 'not_exposed'}</dd><dt>Years</dt><dd>{visibleCoverage.years.length ? `${Math.min(...visibleCoverage.years)}-${Math.max(...visibleCoverage.years)}` : 'not_exposed'} | Undated: {visibleCoverage.undated}</dd><dt>Representation states</dt><dd>{visibleCoverage.states.join(', ')}</dd></dl><p>These counts describe the current returned and visible set only. They do not measure archive-wide representation, completeness, or historical absence.</p></Tile>}
      {view === 'comparative' && <Tile><h2>Compare sources</h2>{comparisonSourceRows.length ? <><div className="visual-analytics-workbench__comparison-overlap" aria-label="Cohort overlap summary"><div className="visual-analytics-workbench__comparison-overlap-segment visual-analytics-workbench__comparison-overlap-segment--a"><span>{comparisonCohortA?.name || 'Cohort A'} only</span><strong>{comparisonSummary.aOnly}</strong></div><div className="visual-analytics-workbench__comparison-overlap-segment visual-analytics-workbench__comparison-overlap-segment--shared"><span>Shared membership</span><strong>{comparisonSummary.overlap}</strong></div><div className="visual-analytics-workbench__comparison-overlap-segment visual-analytics-workbench__comparison-overlap-segment--b"><span>{comparisonCohortB?.name || 'Cohort B'} only</span><strong>{comparisonSummary.bOnly}</strong></div></div><p>{comparisonSummary.total} represented record{comparisonSummary.total === 1 ? '' : 's'} across the two researcher-defined cohorts.</p><table aria-label="Comparison sources"><thead><tr><th>Source</th><th>Membership</th><th>PID</th><th>Document</th><th>Chunk</th><th>Source type</th></tr></thead><tbody>{comparisonSourceRows.map(({ point, membership }) => <tr key={point.id}><td>{pointLabel(point)}</td><td>{membership}</td><td>{point.pid || 'Unavailable'}</td><td>{point.documentId || 'Unavailable'}</td><td>{point.chunkId || 'Document point'}</td><td>{point.sourceType || 'Unavailable'}</td></tr>)}</tbody></table><p>Projection scope: {projection.metadata.projectionId || 'Unavailable'} | Embedding scope: {projection.metadata.embeddingSetId || 'Unavailable'}</p></> : <p>Save cohort A or B from a selection to inspect source membership here.</p>}<p>Membership is a researcher-defined comparison condition, not a historical conclusion.</p></Tile>}
      {view === 'comparative' && Object.entries(cohortNeighbourhoods).map(([slot, result]) => <Tile key={slot} className="visual-analytics-workbench__neighbourhood-evidence"><h2>{result.cohort_name} neighbourhood</h2><Tag type="green">Returned: {result.metadata?.returned_k || result.neighbours?.length || 0}</Tag><table aria-label={`Cohort ${slot} neighbourhood results`}><thead><tr><th>Rank</th><th>Trace</th><th>Score</th></tr></thead><tbody>{(result.neighbours || []).map((point) => <tr key={point.id}><td>{point.rank}</td><td><button type="button" onClick={() => selectPoint(normalizeNeighbour(point))}>{pointLabel(point)}</button></td><td>{point.similarity ?? 'Unavailable'}</td></tr>)}</tbody></table><p>{result.metadata?.method} {result.metadata?.interpretation_limit}</p></Tile>)}
      {view === 'neighbourhoods' && neighbourhoodResult && <Tile className="visual-analytics-workbench__neighbourhood-evidence"><h2>Original-space neighbourhood</h2><p>Focal trace: {pointLabel(neighbourhoodResult.focal || pointById.get(anchorId) || {})}</p><div className="visual-analytics-workbench__legend-values"><Tag type="blue">Requested $k$: {neighbourhoodResult.metadata?.requested_k || neighbourhoodK}</Tag><Tag type="green">Returned: {neighbourhoodResult.metadata?.returned_k || embeddingNeighbours.length}</Tag></div><p>Rank and score use {neighbourhoodResult.metadata?.metric || 'the recorded original-space metric'} in embedding set {neighbourhoodResult.metadata?.embedding_set_id || projection.metadata.embeddingSetId || 'Unavailable'}. The displayed links are retrieval results, not historical relationships.</p>{embeddingNeighbours.length ? <><div className="visual-analytics-workbench__neighbourhood-rank-plot" aria-label="Original-space neighbour rank plot">{embeddingNeighbours.map((point, index) => { const rank = Number(point.rank) || index + 1; return <button type="button" key={point.id} onClick={() => selectPoint(point)} style={{ '--neighbourhood-rank-width': `${Math.max(16, ((neighbourhoodRankMaximum - rank + 1) / neighbourhoodRankMaximum) * 100)}%` }}><span>#{rank}</span><strong>{pointLabel(point)}</strong><small>{point.similarity ?? point.distance ?? 'metric unavailable'}</small></button> })}</div><p className="visual-analytics-workbench__neighbourhood-rank-note">Bar length encodes returned rank only. It does not show visual distance, historical closeness, or evidential strength.</p><table aria-label="Original-space neighbourhood results"><thead><tr><th>Rank</th><th>Trace</th><th>Score</th></tr></thead><tbody>{embeddingNeighbours.map((point) => <tr key={point.id}><td>{point.rank || 'Unavailable'}</td><td><button type="button" onClick={() => selectPoint(point)}>{pointLabel(point)}</button></td><td>{point.similarity ?? point.distance ?? 'Unavailable'}</td></tr>)}</tbody></table></> : <p>No original-space neighbours were returned.</p>}<Button size="sm" kind="ghost" onClick={() => exportNeighbourhoodPacket('markdown')}>Export evidence packet</Button></Tile>}
      {view === 'neighbourhoods' && queryNeighbourhoodResult && <Tile className="visual-analytics-workbench__neighbourhood-evidence"><h2>Query-focal neighbourhood</h2><p>Researcher query: {queryNeighbourhoodResult.query}</p><Tag type="green">Returned: {queryNeighbourhoodResult.metadata?.returned_k || queryNeighbourhoodResult.neighbours?.length || 0}</Tag><table aria-label="Query-focal neighbourhood results"><thead><tr><th>Rank</th><th>Trace</th><th>Score</th></tr></thead><tbody>{(queryNeighbourhoodResult.neighbours || []).map((point) => <tr key={point.id}><td>{point.rank}</td><td><button type="button" onClick={() => selectPoint(normalizeNeighbour(point))}>{pointLabel(point)}</button></td><td>{point.similarity ?? 'Unavailable'}</td></tr>)}</tbody></table><p>{queryNeighbourhoodResult.metadata?.interpretation_limit}</p></Tile>}
      {view === 'temporal' && temporalWindowComparison && <Tile><h2>Returned label comparison</h2><table aria-label="Returned label comparison across temporal windows"><thead><tr><th>Returned label</th><th>Window A</th><th>Window B</th><th>Representation</th></tr></thead><tbody>{temporalWindowComparison.map((item) => <tr key={item.label}><td>{item.label}</td><td>{item.a}</td><td>{item.b}</td><td>{item.membership}</td></tr>)}</tbody></table><p>These counts compare labels represented in the two selected returned-date windows. “Window A/B only” describes this bounded result set; it does not establish emergence, disappearance, continuity, or historical change.</p></Tile>}
      {view === 'temporal' && <Tile><h2>Documentary distribution</h2>{temporalDocumentaryDistribution.length ? <><div className="visual-analytics-workbench__temporal-distribution-strip" aria-label="Returned documentary records by five-year date bin">{temporalDocumentaryDistribution.map((bin) => <button type="button" key={bin.start} onClick={() => setFilters((current) => ({ ...current, yearMin: String(bin.start), yearMax: String(bin.end) }))} style={{ '--temporal-distribution-width': `${Math.max(16, (bin.count / temporalDistributionMaximum) * 100)}%` }}><span>{bin.start}-{bin.end}</span><strong>{bin.count}</strong><small>{bin.sourceTypes.join(', ')}</small></button>)}</div><p className="visual-analytics-workbench__temporal-distribution-note">Bar length encodes the count of currently returned, dated records in each five-year bin. It does not show a historical trend, continuity, or archival completeness.</p><table aria-label="Documentary distribution by returned date"><thead><tr><th>Returned date</th><th>Records</th><th>Documentary forms</th><th>Filter</th></tr></thead><tbody>{temporalDocumentaryDistribution.map((bin) => <tr key={bin.start}><td>{bin.start}-{bin.end}</td><td>{bin.count}</td><td>{bin.sourceTypes.join(', ')}</td><td><Button size="sm" kind="ghost" onClick={() => setFilters((current) => ({ ...current, yearMin: String(bin.start), yearMax: String(bin.end) }))}>Show {bin.start}-{bin.end}</Button></td></tr>)}</tbody></table><p>Each row counts currently returned, dated records by documented year and returned source type. Selecting a row changes fixed-projection visibility only; it does not recompute coordinates or establish historical change.</p></> : <p>No dated records are available in the current returned set. Undated records are not placed into a documentary time bin.</p>}</Tile>}
      {view === 'critical' && criticalPoints.length > 0 && <Tile className="visual-analytics-workbench__critical-evidence"><h2>Critical inquiry results</h2><p>Researcher proposition: {criticalConcept || 'not_exposed'}</p><Tag type="purple">Returned passages: {criticalPoints.length}</Tag><table aria-label="Critical inquiry result records"><thead><tr><th>Trace</th><th>Excerpt</th></tr></thead><tbody>{criticalPoints.map((point) => <tr key={point.id}><td><button type="button" onClick={() => selectPoint(point)}>{pointLabel(point)}</button></td><td>{point.excerpt || 'No bounded excerpt available.'}</td></tr>)}</tbody></table><p>These are retrieval candidates for source review under a researcher-supplied proposition. They are not a classification, evidential confirmation, or statement about archival absence.</p></Tile>}
      {view === 'critical' && criticalCoverage && <Tile className="visual-analytics-workbench__critical-coverage"><h2>Recorded coverage conditions</h2><dl>{(criticalCoverage.completeness_cards || []).map((card) => <Fragment key={card.label}><dt>{card.label}</dt><dd>{card.value}<small>{card.note}</small></dd></Fragment>)}</dl><p>These are returned global system diagnostics and persisted missingness-event counts. They do not locate a sparse region, prove historical absence, or confirm the proposition.</p><Button size="sm" kind="ghost" onClick={() => handoff('/absences')}>Inspect coverage conditions</Button></Tile>}
      {inspectorPoint && <Tile className="visual-analytics-workbench__selection-inspector">
        <h2>{selectedPoints.length > 1 ? `${selectedPoints.length} selected items` : pointLabel(inspectorPoint)}</h2>
        {selectedPoints.length > 1 && <div className="visual-analytics-workbench__selected-list">{selectedPoints.map((point) => <button type="button" key={point.id} onClick={() => { setSelectedIds([point.id]); setAnchorId(point.id); setShowEmbeddingNeighbours(false) }}><span>{pointLabel(point)}</span><small>{point.year || 'Undated'}</small></button>)}</div>}
        {selectedPoints.length === 1 && <><p className="visual-analytics-workbench__excerpt">{inspectorPoint.excerpt || 'No excerpt is available.'}</p><Tag type={inspectorPoint.evidenceClass?.kind === 'oral_history_testimony' ? 'purple' : 'gray'}>{inspectorPoint.evidenceClass?.label || 'Archival document'}</Tag>{inspectorPoint.evidenceClass?.kind === 'oral_history_testimony' && <p>{inspectorPoint.evidenceClass.temporalClass || 'Later testimony'}. {inspectorPoint.evidenceClass.basis || 'Classification basis unavailable.'} It is situated retrospective evidence, not contemporaneous proof.</p>}<dl><dt>Year</dt><dd>{inspectorPoint.year || 'Unknown'}</dd><dt>Source type</dt><dd>{inspectorPoint.sourceType || 'Unknown'}</dd><dt>PID</dt><dd>{inspectorPoint.pid || 'Unavailable'}</dd><dt>Chunk</dt><dd>{inspectorPoint.chunkId || 'Document point'}</dd><dt>Themes</dt><dd>{inspectorPoint.themes?.join(', ') || 'Unlabelled'}</dd><dt>Representation</dt><dd>{inspectorPoint.evidenceSurface?.representationState || 'Unknown'}</dd><dt>Missingness</dt><dd>{inspectorPoint.missingness?.status || 'Not recorded'}</dd><dt>Archive authority</dt><dd>{inspectorPoint.archiveAuthorityContext?.availability || 'Not exposed'}</dd><dt>Database authority</dt><dd>{inspectorPoint.databaseAuthorityContext?.length ? `${inspectorPoint.databaseAuthorityContext.length} linked record(s)` : 'Not exposed'}</dd><dt>Projection</dt><dd>{projection.metadata.projectionId || 'Current UMAP surface'}</dd></dl></>}
        {selectedPoints.length === 1 && <Toggle id="show-embedding-neighbours" labelText="Show embedding neighbours" labelA="Off" labelB="On" toggled={showEmbeddingNeighbours} onToggle={(toggled) => { setShowEmbeddingNeighbours(toggled); if (toggled) { setAnchorId(inspectorPoint.id); loadNeighbours() } }} disabled={!inspectorPoint.chunkId} />}
        <div className="visual-analytics-workbench__actions"><Button size="sm" kind="ghost" onClick={() => handoff('/sources')}>Open source</Button><Button size="sm" kind="ghost" onClick={() => handoff('/source-interrogation')}>Ask about selected sources</Button><Button size="sm" kind="ghost" onClick={() => { setAnchorId(inspectorPoint.id); setView('neighbourhoods') }}>Semantic neighbourhood</Button><Button size="sm" kind="ghost" renderIcon={Add} onClick={() => setComparisonA((current) => [...new Set([...current, ...selectedIds])])}>Add to comparison A</Button><Button size="sm" kind="ghost" onClick={() => handoff('/cross-readings')}>Cross-read</Button><Button size="sm" kind="ghost" renderIcon={WarningAlt} onClick={() => handoff('/absences')}>Record scoped absence</Button></div>
        {selectedPoints.length === 1 && <div className="visual-analytics-workbench__annotation"><h3>Researcher annotation</h3><Select id="annotation-type" labelText="Annotation type" value={annotationType} onChange={(event) => { setAnnotationType(event.target.value); setAnnotationControlledValue(''); setAnnotationResearcherValue('') }}>{ANNOTATION_TYPES.map(([value, label]) => <SelectItem key={value} value={value} text={label} />)}</Select>{ANNOTATION_CONTROLLED_VALUES[annotationType] && <Select id="annotation-controlled-value" labelText="Controlled coding value" value={annotationControlledValue} onChange={(event) => setAnnotationControlledValue(event.target.value)}><SelectItem value="" text="Choose a researcher coding value" />{ANNOTATION_CONTROLLED_VALUES[annotationType].map(([value, label]) => <SelectItem key={value} value={value} text={label} />)}</Select>}{ANNOTATION_RESEARCHER_VALUE_LABELS[annotationType] && <TextInput id="annotation-researcher-value" labelText={ANNOTATION_RESEARCHER_VALUE_LABELS[annotationType]} value={annotationResearcherValue} maxLength={500} onChange={(event) => setAnnotationResearcherValue(event.target.value)} />}<Select id="annotation-status" labelText="Review status" value={annotationStatus} onChange={(event) => setAnnotationStatus(event.target.value)}><SelectItem value="draft" text="Draft" /><SelectItem value="reviewing" text="Reviewing" /><SelectItem value="reviewed" text="Reviewed" /><SelectItem value="contested" text="Contested" /><SelectItem value="withdrawn" text="Withdrawn" /></Select><TextArea id="annotation-value" labelText="Source-linked note" value={annotationValue} onChange={(event) => setAnnotationValue(event.target.value)} rows={3} /><Button size="sm" onClick={saveAnnotation} disabled={!annotationValue.trim() || (ANNOTATION_CONTROLLED_VALUES[annotationType] && !annotationControlledValue) || (ANNOTATION_RESEARCHER_VALUE_LABELS[annotationType] && !annotationResearcherValue.trim())}>{savedAnnotationId ? 'Save revision' : 'Save annotation'}</Button>{savedAnnotationId && <><Tag type="green">Saved annotation: {savedAnnotationId}</Tag><Button size="sm" kind="ghost" onClick={loadAnnotationHistory}>View revision history</Button>{annotationRevisions.length > 0 && <ol className="visual-analytics-workbench__revision-list">{annotationRevisions.map((revision) => <li key={revision.revision}>Revision {revision.revision}: {revision.snapshot?.value?.note || 'No note recorded'}</li>)}</ol>}</>}</div>}
        {showEmbeddingNeighbours && <><h3>Embedding neighbours</h3><p>Nearest passages in the original embedding space.</p>{neighbourhoodResult?.metadata && <div><h4>Why this neighbour?</h4><p>Rank and score use {neighbourhoodResult.metadata.metric || 'the recorded original-space metric'} in embedding set {neighbourhoodResult.metadata.embedding_set_id || 'Unavailable'}; projection {neighbourhoodResult.metadata.projection_id || 'Unavailable'} remains fixed. This is a retrieval diagnostic, not a historical relationship.</p></div>}<div className="visual-analytics-workbench__neighbour-list">{embeddingNeighbours.length ? embeddingNeighbours.map((point) => <div key={point.id}><button type="button" onClick={() => selectPoint(point)}><span>{point.title}</span><small>rank {point.rank || '-'} | {point.similarity ?? point.distance ?? 'metric unavailable'}</small></button><Button size="sm" kind="ghost" onClick={() => refocusNeighbour(point)} disabled={!point.chunkId}>Use as focal trace</Button></div>) : <span>Loading original-space neighbours...</span>}</div></>}
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