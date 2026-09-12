import { useEffect, useMemo, useRef } from 'react'
import * as d3 from 'd3'
import { chartColors, chartStyles, utils } from '../../utils/carbonD3Theme'

const categoricalFields = {
  cluster: (point) => point.clusterLabel || 'unclustered',
  source_type: (point) => point.sourceType || 'unknown',
  theme: (point) => point.themes?.[0] || 'unlabelled',
}

const numericFields = {
  year: (point) => point.year,
  confidence: (point) => point.confidence,
  drift_score: (point) => point.driftScore,
}

const UmapProjection = ({ points, loading, errorState, selectedPoint, highlightedTrace, colorBy, onSelectPoint }) => {
  const svgRef = useRef(null)
  const tooltipRef = useRef(null)

  const highlightedPointId = useMemo(() => {
    if (!highlightedTrace) {
      return null
    }

    return points.find((point) => (
      (highlightedTrace.chunkId && point.chunkId === highlightedTrace.chunkId) ||
      (highlightedTrace.documentId && point.documentId === highlightedTrace.documentId) ||
      (highlightedTrace.pid && point.pid === highlightedTrace.pid)
    ))?.id || null
  }, [highlightedTrace, points])

  useEffect(() => {
    const svgElement = svgRef.current
    if (!svgElement || loading || errorState || points.length === 0) {
      return undefined
    }

    const width = 880
    const height = 520
    const margin = { top: 32, right: 32, bottom: 48, left: 48 }

    const svg = d3.select(svgElement)
    svg.selectAll('*').remove()
    svg.attr('viewBox', `0 0 ${width} ${height}`)

    const root = svg.append('g')

    const xExtent = d3.extent(points, (point) => point.x)
    const yExtent = d3.extent(points, (point) => point.y)

    const xScale = d3.scaleLinear()
      .domain(xExtent[0] === xExtent[1] ? [xExtent[0] - 1, xExtent[1] + 1] : xExtent)
      .range([margin.left, width - margin.right])

    const yScale = d3.scaleLinear()
      .domain(yExtent[0] === yExtent[1] ? [yExtent[0] - 1, yExtent[1] + 1] : yExtent)
      .range([height - margin.bottom, margin.top])

    const categoricalValue = categoricalFields[colorBy]
    const numericValue = numericFields[colorBy]
    const color = categoricalValue
      ? utils.getClusterColorScale([...new Set(points.map(categoricalValue))], (key) => key)
      : (() => {
          const values = points.map(numericValue || categoricalFields.cluster).filter(Number.isFinite)
          if (values.length === 0) {
            return () => chartColors.plotStroke
          }
          const extent = d3.extent(values)
          const domain = extent[0] === extent[1] ? [extent[0] - 1, extent[1] + 1] : extent
          const scale = d3.scaleSequential(d3.interpolateTurbo).domain(domain)
          return (point) => Number.isFinite(numericValue?.(point)) ? scale(numericValue(point)) : chartColors.plotStroke
        })()

    const plot = root.append('g')

    root.append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(xScale).ticks(6))

    root.append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(yScale).ticks(6))

    root.append('text')
      .attr('x', width / 2)
      .attr('y', height - 10)
      .attr('text-anchor', 'middle')
      .attr('fill', chartStyles.timeline.label.fill)
      .text('UMAP dimension 1')

    root.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -height / 2)
      .attr('y', 16)
      .attr('text-anchor', 'middle')
      .attr('fill', chartStyles.timeline.label.fill)
      .text('UMAP dimension 2')

    const tooltip = d3.select(tooltipRef.current)

    plot.selectAll('circle')
      .data(points)
      .enter()
      .append('circle')
      .attr('class', 'umap-projection__point')
      .attr('cx', (point) => xScale(point.x))
      .attr('cy', (point) => yScale(point.y))
      .attr('r', (point) => (point.id === selectedPoint?.id ? 8 : point.id === highlightedPointId ? 7 : 5))
      .attr('fill', (point) => categoricalValue ? color(categoricalValue(point)) : color(point))
      .attr('stroke', (point) => (point.id === selectedPoint?.id ? chartColors.selectionStroke : point.id === highlightedPointId ? chartColors.highlightStroke : chartColors.plotStroke))
      .attr('stroke-width', (point) => (point.id === selectedPoint?.id || point.id === highlightedPointId ? 2.5 : 1))
      .on('mouseenter', (event, point) => {
        tooltip.style('opacity', 1)
        tooltip.html(`
          <strong>${point.title || 'Untitled trace'}</strong><br/>
          PID: ${point.pid || 'Unavailable'}<br/>
          Year: ${point.year || 'Unavailable'}<br/>
          Cluster: ${point.clusterLabel || 'Unlabelled'}<br/>
          Theme: ${point.themes?.[0] || 'Unavailable'}
        `)
        tooltip.style('left', `${event.pageX + 12}px`)
        tooltip.style('top', `${event.pageY - 16}px`)
      })
      .on('mouseleave', () => {
        tooltip.style('opacity', 0)
      })
      .on('click', (_, point) => onSelectPoint(point))

    const zoom = d3.zoom()
      .scaleExtent([0.75, 6])
      .on('zoom', (event) => {
        plot.attr('transform', event.transform)
      })

    svg.call(zoom)

    return () => {
      tooltip.style('opacity', 0)
    }
  }, [points, loading, errorState, selectedPoint, highlightedPointId, colorBy, onSelectPoint])

  if (loading) {
    return <div className="umap-projection__state">Loading UMAP projection…</div>
  }

  if (errorState) {
    return <div className="umap-projection__state">{errorState}</div>
  }

  if (points.length === 0) {
    return <div className="umap-projection__state">No UMAP projection is available yet. This requires embedded chunks or documents from the DDR corpus.</div>
  }

  const categoricalValue = categoricalFields[colorBy]
  const numericValue = numericFields[colorBy]
  const categories = categoricalValue ? [...new Set(points.map(categoricalValue))] : []
  const categoricalColor = categoricalValue ? utils.getClusterColorScale(categories, (key) => key) : null
  const numericValues = numericValue ? points.map(numericValue).filter(Number.isFinite) : []
  const numericExtent = numericValues.length ? d3.extent(numericValues) : null

  return (
    <div className="umap-projection">
      <p className="umap-projection__coordinate-note"><strong>Reading the map:</strong> each dot is an archival passage. The horizontal and vertical values are UMAP dimensions: learned coordinates that place semantically similar passages nearer together. They are not historical variables, timelines, or measures of importance.</p>
      <div className="umap-projection__legend" aria-label={`Colour legend: ${colorBy.replace('_', ' ')}`}>
        {categoricalValue && categories.slice(0, 12).map((category) => <span className="umap-projection__legend-item" key={category}><i style={{ backgroundColor: categoricalColor(category) }} />{category}</span>)}
        {categories.length > 12 && <span className="umap-projection__legend-overflow">+{categories.length - 12} categories</span>}
        {numericExtent && <span className="umap-projection__legend-scale"><i />{numericExtent[0]} to {numericExtent[1]}</span>}
      </div>
      <svg ref={svgRef} className="umap-projection__svg" />
      <div ref={tooltipRef} className="viz-tooltip umap-projection__tooltip" />
    </div>
  )
}

export default UmapProjection