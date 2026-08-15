import { useEffect, useMemo, useRef } from 'react'
import * as d3 from 'd3'
import { chartColors, chartStyles, utils } from '../../utils/carbonD3Theme'

const UmapProjection = ({ points, loading, errorState, selectedPoint, highlightedTrace, onSelectPoint }) => {
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

    const color = utils.getClusterColorScale(
      [...new Set(points.map((point) => point.clusterLabel || point.sourceType || 'unclustered'))],
      (key) => key
    )

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
      .attr('fill', (point) => color(point.clusterLabel || point.sourceType || 'unclustered'))
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
  }, [points, loading, errorState, selectedPoint, highlightedPointId, onSelectPoint])

  if (loading) {
    return <div className="umap-projection__state">Loading UMAP projection…</div>
  }

  if (errorState) {
    return <div className="umap-projection__state">{errorState}</div>
  }

  if (points.length === 0) {
    return <div className="umap-projection__state">No UMAP projection is available yet. This requires embedded chunks or documents from the DDR corpus.</div>
  }

  return (
    <div className="umap-projection">
      <svg ref={svgRef} className="umap-projection__svg" />
      <div ref={tooltipRef} className="viz-tooltip umap-projection__tooltip" />
    </div>
  )
}

export default UmapProjection