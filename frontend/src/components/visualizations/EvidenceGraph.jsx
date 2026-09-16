import { Button } from '@carbon/react'
import { Download } from '@carbon/icons-react'
import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import { chartColors, carbonColors, chartStyles } from '../../utils/carbonD3Theme'

const sourceLabel = (source, index) => {
  const archiveId = source.pid || source.archiveRecordPid || source.documentId || `Source ${index + 1}`
  const locator = source.page ? `p. ${source.page}` : source.chunkId ? `chunk ${source.chunkId}` : 'locator unavailable'
  return `${archiveId} | ${locator}`
}

const sourceDetail = (source) => [
  source.title || 'Document title unavailable',
  source.evidenceClassification?.relationship_to_question || source.evidenceClassification?.classification || 'Not classified'
].join(' | ')

const labelLines = (label, maximumLength = 22) => {
  const lines = []
  let line = ''

  label.split(' ').forEach((word) => {
    const next = line ? `${line} ${word}` : word
    if (next.length > maximumLength && line) {
      lines.push(line)
      line = word
    } else {
      line = next
    }
  })
  if (line) lines.push(line)
  return lines.slice(0, 3)
}

const formatScore = (score) => {
  const value = Number(score)
  return Number.isFinite(value) ? value.toFixed(3) : 'Not exposed'
}

const EvidenceGraph = ({ data }) => {
  const svgRef = useRef()
  const [selectedSource, setSelectedSource] = useState(null)

  const downloadBlob = (blob, filename) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  const exportSvg = () => {
    if (!svgRef.current) return

    const copy = svgRef.current.cloneNode(true)
    copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    downloadBlob(new Blob([new XMLSerializer().serializeToString(copy)], { type: 'image/svg+xml;charset=utf-8' }), 'turin-evidence-trail.svg')
  }

  const exportPng = () => {
    if (!svgRef.current) return

    const copy = svgRef.current.cloneNode(true)
    copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    const svgBlob = new Blob([new XMLSerializer().serializeToString(copy)], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)
    const image = new Image()
    image.onload = () => {
      const viewBox = svgRef.current.viewBox.baseVal
      const scale = 2
      const canvas = document.createElement('canvas')
      canvas.width = viewBox.width * scale
      canvas.height = viewBox.height * scale
      const context = canvas.getContext('2d')
      context.fillStyle = '#262626'
      context.fillRect(0, 0, canvas.width, canvas.height)
      context.drawImage(image, 0, 0, canvas.width, canvas.height)
      canvas.toBlob((blob) => {
        if (blob) downloadBlob(blob, 'turin-evidence-trail.png')
        URL.revokeObjectURL(url)
      }, 'image/png')
    }
    image.src = url
  }

  useEffect(() => {
    const width = 960
    const rowSpacing = 84
    const topOffset = 80
    const rowCount = Math.max(data?.sources?.length || 0, 1)
    const height = Math.max(420, topOffset + ((rowCount - 1) * rowSpacing) + 64)

    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
    .attr('viewBox', `0 0 1120 ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')

    if (!data) {
      svg.append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', chartColors.emptyState)
        .style('font-size', '16px')
        .text('Submit a question to inspect its evidence trail')

      return
    }

    const sources = data.sources || []
    const archiveIds = new Set(sources.map((source) => source.pid || source.archiveRecordPid).filter(Boolean))
    const answerConstruction = data.answerOrigin === 'deterministic_evidence_bound_fallback'
      ? 'Evidence-bound assembly'
      : data.answerOrigin === 'retrieval_only'
        ? 'No model synthesis'
        : 'Qwen evidence synthesis'
    const nodes = [
      { id: 'question', label: 'Research question', detail: data.prompt || data.query || 'Question text unavailable', column: 0, row: 0, group: 'query' },
      { id: 'selection', label: 'Archive-first selection', detail: `${sources.length} retained passage${sources.length === 1 ? '' : 's'} nominated from the available evidence surface`, column: 1, row: 0, group: 'document' },
      { id: 'evidence-set', label: 'Inspectable evidence set', detail: `${sources.length} passage${sources.length === 1 ? '' : 's'} from ${archiveIds.size || 'unresolved'} archival record${archiveIds.size === 1 ? '' : 's'}`, column: 3, row: 0, group: 'pid' },
      { id: 'construction', label: answerConstruction, detail: data.model ? `Runtime model: ${data.model}` : 'Answer construction method recorded by this run', column: 4, row: 0, group: data.answerOrigin === 'deterministic_evidence_bound_fallback' ? 'document' : 'model' },
      { id: 'answer', label: 'Evidence-backed response', detail: 'Read alongside the selected passages, provenance chain, and stated limits.', column: 5, row: 0, group: 'answer' }
    ]
    const links = [{ source: 'question', target: 'selection', value: 1 }]

    sources.forEach((source, index) => {
      const sourceId = source.chunkId || source.sourceId || `source-${index}`
      const selectionScore = Number.isFinite(source.sourceNominationScore) ? source.sourceNominationScore : source.score || 0.5
      const passageScore = Number.isFinite(source.passageScore) ? source.passageScore : source.score || 0.5

      nodes.push({ id: sourceId, label: sourceLabel(source, index), detail: sourceDetail(source), source, column: 2, row: index, group: 'chunk' })
      links.push({ source: 'selection', target: sourceId, value: selectionScore })
      links.push({ source: sourceId, target: 'evidence-set', value: passageScore })
    })

    links.push({ source: 'evidence-set', target: 'construction', value: 1 })
    links.push({ source: 'construction', target: 'answer', value: 1 })

    const columns = [90, 280, 505, 730, 920, 1080]

    nodes.forEach((node) => {
      node.x = columns[node.column]
      node.y = node.column === 2 ? topOffset + (node.row * rowSpacing) : height / 2
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
      .attr('stroke-width', (d) => Math.max(1.5, Math.min(4, d.value * 3)))
      .attr('x1', (d) => d.source.x)
      .attr('y1', (d) => d.source.y)
      .attr('x2', (d) => d.target.x)
      .attr('y2', (d) => d.target.y)

    const node = nodeGroup.selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('transform', (d) => `translate(${d.x}, ${d.y})`)
      .attr('tabindex', (d) => d.source ? 0 : null)
      .attr('role', (d) => d.source ? 'button' : null)
      .attr('aria-label', (d) => d.source ? `Inspect provenance for ${d.label}` : null)
      .on('click', (_event, d) => d.source && setSelectedSource(d.source))
      .on('keydown', (event, d) => {
        if (d.source && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault()
          setSelectedSource(d.source)
        }
      })

    node.append('title').text((d) => `${d.label}\n${d.detail || ''}`)
    node.append('circle')
      .attr('r', 22)
      .attr('fill', (d) => colorMap[d.group] || carbonColors.gray[60])
      .attr('stroke', chartColors.selectionStroke)
      .attr('stroke-width', 1.5)

    node.append('text')
      .attr('font-size', 12)
      .attr('fill', chartStyles.timeline.text.fill)
      .attr('text-anchor', 'middle')
      .attr('y', 36)
      .each(function appendLabelLines(nodeData) {
        labelLines(nodeData.label).forEach((line, index) => {
          d3.select(this)
            .append('tspan')
            .attr('x', 0)
            .attr('dy', index === 0 ? 0 : 13)
            .text(line)
        })
      })

  }, [data])

  return (
    <div className="evidence-graph">
      {data && (
        <div className="evidence-graph__toolbar" aria-label="Retrieval trail export controls">
          <Button kind="ghost" size="sm" renderIcon={Download} onClick={exportSvg}>Download SVG</Button>
          <Button kind="ghost" size="sm" renderIcon={Download} onClick={exportPng}>Download PNG</Button>
        </div>
      )}
      <svg ref={svgRef} aria-label="Evidence retrieval trail" role="img"></svg>
      {selectedSource && (
        <aside className="evidence-graph__inspector" aria-live="polite">
          <h4>Selected passage</h4>
          <dl>
            <div><dt>Document</dt><dd>{selectedSource.title || 'Unavailable'}</dd></div>
            <div><dt>Archive identity</dt><dd>{selectedSource.identity?.recordPid || 'record unavailable'} → {selectedSource.identity?.mediaPid || 'media unavailable'} → {selectedSource.pid || 'asset unavailable'}</dd></div>
            <div><dt>Passage locator</dt><dd>Page {selectedSource.page || 'unavailable'} | {selectedSource.chunkId || 'chunk unavailable'}</dd></div>
            <div><dt>Relation</dt><dd>{selectedSource.evidenceClassification?.relationship_to_question || selectedSource.evidenceClassification?.classification || 'Not classified'}</dd></div>
            <div><dt>Retrieval strength</dt><dd>{formatScore(selectedSource.score)} overall | {formatScore(selectedSource.sourceNominationScore)} nomination | {formatScore(selectedSource.passageScore)} passage</dd></div>
            <div><dt>Provenance status</dt><dd>{selectedSource.provenanceStatus || 'Unavailable'}</dd></div>
          </dl>
        </aside>
      )}
    </div>
  )
}

export default EvidenceGraph
