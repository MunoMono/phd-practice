import { Button, InlineNotification } from '@carbon/react'
import { Download } from '@carbon/icons-react'
import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import { chartColors, carbonColors, chartStyles } from '../../utils/carbonD3Theme'

const sourceLabel = (source, index) => {
  const archiveId = source.pid || source.archiveRecordPid || `Source ${index + 1}`
  const locator = source.page != null ? `p. ${source.page}` : 'page unavailable'
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
  const [exportError, setExportError] = useState('')
  const exportCopy = () => {
    const copy = svgRef.current.cloneNode(true)
    copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    const originals = [svgRef.current, ...svgRef.current.querySelectorAll('*')]
    const copies = [copy, ...copy.querySelectorAll('*')]
    originals.forEach((element, index) => {
      const style = getComputedStyle(element)
      for (const property of ['fill', 'stroke', 'font-family', 'font-size', 'font-weight']) {
        copies[index].setAttribute(property, style.getPropertyValue(property))
      }
    })
    const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
    background.setAttribute('width', svgRef.current.viewBox.baseVal.width)
    background.setAttribute('height', svgRef.current.viewBox.baseVal.height)
    background.setAttribute('fill', getComputedStyle(svgRef.current.parentElement.parentElement).backgroundColor)
    copy.insertBefore(background, copy.firstChild)
    return copy
  }

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

    const copy = exportCopy()
    setExportError('')
    downloadBlob(new Blob([new XMLSerializer().serializeToString(copy)], { type: 'image/svg+xml;charset=utf-8' }), 'turin-evidence-trail.svg')
  }

  const exportPng = () => {
    if (!svgRef.current) return

    const copy = exportCopy()
    setExportError('')
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
      if (!context) {
        setExportError('PNG export failed: a canvas drawing context is unavailable.')
        URL.revokeObjectURL(url)
        return
      }
      context.fillStyle = getComputedStyle(svgRef.current.parentElement).backgroundColor
      context.fillRect(0, 0, canvas.width, canvas.height)
      context.drawImage(image, 0, 0, canvas.width, canvas.height)
      canvas.toBlob((blob) => {
        if (blob) downloadBlob(blob, 'turin-evidence-trail.png')
        else setExportError('PNG export failed: the browser could not encode the image.')
        URL.revokeObjectURL(url)
      }, 'image/png')
    }
    image.onerror = () => {
      setExportError('PNG export failed: the browser could not render the SVG.')
      URL.revokeObjectURL(url)
    }
    image.src = url
  }

  useEffect(() => {
    setSelectedSource(null)
    const width = 1200
    const rowSpacing = 84
    const rowCount = data?.sources?.length || 0
    const height = data ? Math.max(420, (Math.max(rowCount - 1, 0) * rowSpacing) + 140) : 160

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
        .attr('class', 'evidence-graph__empty')
        .text('Submit a question to inspect its evidence trail')

      return
    }

    const sources = data.sources || []
    const archiveIds = new Set(sources.map((source) => source.pid || source.archiveRecordPid).filter(Boolean))
    const unverified = data.answerState === 'unverified_research_draft'
    const unavailable = ['synthesis_unavailable', 'evidential_limit'].includes(data.answerState)
      || ['retrieval_only', 'model_parse_failure', 'model_runtime_failure'].includes(data.answerOrigin)
      || (!data.answer && !data.answerParagraphs?.length)
    const deterministic = data.answerOrigin?.startsWith('deterministic_')
    const model = typeof data.model === 'string' ? data.model : data.model?.name || data.model?.display_name || ''
    const construction = unavailable ? 'No model synthesis'
      : deterministic ? 'Evidence-bound assembly'
        : /granite/i.test(model) ? 'Granite evidence synthesis' : 'Model evidence synthesis'
    const nodes = [
      { id: 'question', label: 'Research question', detail: data.prompt || data.query, column: 0, group: 'query' },
      { id: 'selection', label: 'Archive-first selection', detail: `${sources.length} retained passages. Catalogue association is not proof of historical action.`, column: 1, group: 'document' },
      { id: 'evidence-set', label: 'Inspectable evidence set', detail: `${sources.length} passages from ${archiveIds.size || 'unresolved'} archival records`, column: 3, group: 'pid' },
      { id: 'construction', label: construction, detail: `Construction: ${data.answerOrigin || 'not recorded'}; model: ${model || 'not recorded'}`, column: 4, group: 'model' },
      { id: 'answer', label: 'Research response', status: unverified ? 'Unverified draft' : unavailable ? 'Synthesis unavailable' : 'Researcher review required', detail: 'Read alongside the selected passages and stated limits. No human acceptance is implied.', column: 5, group: 'answer' },
    ]
    const links = [
      { source: 'question', target: 'selection' },
      { source: 'evidence-set', target: 'construction' },
      { source: 'construction', target: 'answer' },
    ]

    sources.forEach((source, index) => {
      const sourceId = source.anchor || `passage-${index}`

      nodes.push({ id: sourceId, label: sourceLabel(source, index), detail: sourceDetail(source), source, column: 2, row: index, group: 'chunk' })
      links.push({ source: 'selection', target: sourceId })
      links.push({ source: sourceId, target: 'evidence-set' })
    })

    const columns = [90, 280, 505, 730, 920, 1100]

    nodes.forEach((node) => {
      node.x = columns[node.column]
      node.y = node.source ? (height - ((rowCount - 1) * rowSpacing)) / 2 + (node.row * rowSpacing) : height / 2
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
      .attr('stroke-width', 2)
      .attr('x1', (d) => d.source.x)
      .attr('y1', (d) => d.source.y)
      .attr('x2', (d) => d.target.x)
      .attr('y2', (d) => d.target.y)

    const node = nodeGroup.selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', (d) => d.source ? 'evidence-graph__source' : 'evidence-graph__stage')
      .attr('data-stage', (d) => d.source ? null : d.label)
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
      .attr('class', 'evidence-graph__label')
      .attr('fill', chartStyles.timeline.text.fill)
      .attr('text-anchor', 'middle')
      .attr('y', 36)
      .each(function appendLabelLines(nodeData) {
        labelLines(nodeData.label, nodeData.source ? 30 : 20).forEach((line, index) => {
          d3.select(this)
            .append('tspan')
            .attr('x', 0)
            .attr('dy', index === 0 ? 0 : 18)
            .text(line)
        })
      })
    node.filter((d) => d.status).append('text')
        .attr('class', 'evidence-graph__stage-status')
        .attr('text-anchor', 'middle')
        .attr('y', 84)
        .each(function appendStatusLines(nodeData) {
          labelLines(nodeData.status, 18).forEach((line, index) => {
            d3.select(this).append('tspan').attr('x', 0).attr('dy', index ? 16 : 0).text(index ? ` ${line}` : line)
          })
        })

  }, [data])

  return (
    <div className="evidence-graph">
      <div className="evidence-graph__heading">
        <h4>Retrieval trail</h4>
        <p>Trace-derived map of the retrieved archival passages. Each passage names its archive identifier and page; hover for its title and evidential classification.</p>
      </div>
      {data && (
        <div className="evidence-graph__toolbar" aria-label="Retrieval trail export controls">
          <Button kind="ghost" size="sm" renderIcon={Download} onClick={exportSvg}>Download SVG</Button>
          <Button kind="ghost" size="sm" renderIcon={Download} onClick={exportPng}>Download PNG</Button>
        </div>
      )}
      {exportError && <InlineNotification lowContrast kind="error" title="Retrieval trail export failed" subtitle={exportError} />}
      <div className="evidence-graph__viewport" tabIndex={0} role="region" aria-label="Scrollable retrieval trail">
        <svg ref={svgRef} aria-label="Evidence retrieval trail" role="img"></svg>
      </div>
      {selectedSource && (
        <aside className="evidence-graph__inspector" aria-live="polite">
          <h4>Selected passage</h4>
          <dl>
            <div><dt>Document</dt><dd>{selectedSource.title || 'Unavailable'}</dd></div>
            <div><dt>Archive identity</dt><dd>{selectedSource.identity?.recordPid || 'record unavailable'} → {selectedSource.identity?.mediaPid || 'media unavailable'} → {selectedSource.pid || 'asset unavailable'}</dd></div>
            <div><dt>Passage locator</dt><dd>Page {selectedSource.page ?? 'unavailable'} | {selectedSource.chunkId || 'chunk unavailable'}</dd></div>
            <div><dt>Relation</dt><dd>{selectedSource.evidenceClassification?.relationship_to_question || selectedSource.evidenceClassification?.classification || 'Not classified'}</dd></div>
            <div><dt>Retrieval strength</dt><dd>{formatScore(selectedSource.score)} overall | {formatScore(selectedSource.sourceNominationScore)} nomination | {formatScore(selectedSource.passageScore)} passage</dd></div>
            <div><dt>Provenance status</dt><dd>{selectedSource.provenanceStatus || 'Unavailable'}</dd></div>
          </dl>
          <a href={`#${selectedSource.anchor || ''}`}>Read selected source passage</a>
        </aside>
      )}
      <details className="evidence-graph__framework-note">
        <summary>Research framework and evidential limits</summary>
        <p>Question → Retrieval → Evidence → Validated claims → Scholarly argument → Citations → Bounded Qualification.</p>
        <p>The framework is not seven model calls or human acceptance. Retrieved passages and graph connections do not independently validate historical claims. Inspect the recorded assessments below.</p>
      </details>
    </div>
  )
}

export default EvidenceGraph
