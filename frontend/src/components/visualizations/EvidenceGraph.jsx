import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { chartColors, carbonColors, chartStyles } from '../../utils/carbonD3Theme'

const EvidenceGraph = ({ data }) => {
  const svgRef = useRef()

  useEffect(() => {
    const width = 960
    const height = 420

    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')

    if (!data) {
      svg.append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', chartColors.emptyState)
        .style('font-size', '16px')
        .text('Submit a query to visualize evidence flow')

      return
    }

    const nodes = [
      { id: 'query', label: 'Query', column: 0, row: 0, group: 'query' },
      { id: 'model', label: data.model || 'Granite model', column: 1, row: 0, group: 'model' },
      { id: 'answer', label: 'Answer', column: 5, row: 0, group: 'answer' }
    ]

    const links = [
      { source: 'query', target: 'model', value: 1 },
      { source: 'model', target: 'answer', value: 1 }
    ]

    const documentsSeen = new Set()
    const pidsSeen = new Set()

    ;(data.sources || []).forEach((source, index) => {
      const chunkId = source.chunkId || `chunk-${index}`
      const documentId = source.documentId || `document-${index}`
      const pidId = source.pid || `pid-missing-${index}`

      nodes.push({ id: chunkId, label: source.chunkId ? `Chunk ${index + 1}` : `Source ${index + 1}`, column: 2, row: index, group: 'chunk' })
      links.push({ source: 'model', target: chunkId, value: source.score || 0.5 })

      if (!documentsSeen.has(documentId)) {
        nodes.push({ id: documentId, label: source.title || 'Document', column: 3, row: index, group: 'document' })
        documentsSeen.add(documentId)
      }

      links.push({ source: chunkId, target: documentId, value: 1 })

      if (source.pid && !pidsSeen.has(pidId)) {
        nodes.push({ id: pidId, label: source.pid, column: 4, row: index, group: 'pid' })
        pidsSeen.add(pidId)
      }

      if (source.pid) {
        links.push({ source: documentId, target: pidId, value: 1 })
        links.push({ source: pidId, target: 'answer', value: 1 })
      } else {
        links.push({ source: documentId, target: 'answer', value: 0.5 })
      }
    })

    const columns = [80, 240, 420, 600, 760, 900]
    const rowSpacing = 84
    const topOffset = 80

    nodes.forEach((node) => {
      node.x = columns[node.column]
      node.y = node.column === 0 || node.column === 1 || node.column === 5
        ? height / 2
        : topOffset + (node.row * rowSpacing)
    })

    const nodeLookup = new Map(nodes.map((node) => [node.id, node]))
    const hydratedLinks = links
      .map((link) => ({ ...link, source: nodeLookup.get(link.source), target: nodeLookup.get(link.target) }))
      .filter((link) => link.source && link.target)

    const colorMap = {
      query: chartColors.query,
      model: chartColors.model,
      chunk: chartColors.chunk,
      document: chartColors.document,
      pid: chartColors.pid,
      answer: chartColors.answer,
    }

    const linkGroup = svg.append('g').attr('class', 'evidence-graph__links')
    const nodeGroup = svg.append('g').attr('class', 'evidence-graph__nodes')

    linkGroup.selectAll('line')
      .data(hydratedLinks)
      .enter()
      .append('line')
      .attr('stroke', carbonColors.gray[50])
      .attr('stroke-opacity', 0.65)
      .attr('stroke-width', (d) => Math.max(1.5, d.value * 3))
      .attr('x1', (d) => d.source.x)
      .attr('y1', (d) => d.source.y)
      .attr('x2', (d) => d.target.x)
      .attr('y2', (d) => d.target.y)

    nodeGroup.selectAll('circle')
      .data(nodes)
      .enter()
      .append('circle')
      .attr('r', 22)
      .attr('cx', (d) => d.x)
      .attr('cy', (d) => d.y)
      .attr('fill', (d) => colorMap[d.group] || carbonColors.gray[60])
      .attr('stroke', chartColors.selectionStroke)
      .attr('stroke-width', 1.5)

    nodeGroup.selectAll('text')
      .data(nodes)
      .enter()
      .append('text')
      .text((d) => d.label.length > 20 ? `${d.label.slice(0, 20)}...` : d.label)
      .attr('font-size', 12)
      .attr('fill', chartStyles.timeline.text.fill)
      .attr('text-anchor', 'middle')
      .attr('x', (d) => d.x)
      .attr('y', (d) => d.y + 36)

  }, [data])

  return (
    <div className="evidence-graph">
      <svg ref={svgRef}></svg>
    </div>
  )
}

export default EvidenceGraph
