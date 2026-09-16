import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { chartColors, chartStyles } from '../../utils/carbonD3Theme'

const TrainingMetricsChart = () => {
  const svgRef = useRef()

  useEffect(() => {
    const data = [
      { epoch: 1, loss: 2.4 },
      { epoch: 2, loss: 1.8 },
      { epoch: 3, loss: 1.3 },
      { epoch: 4, loss: 0.9 },
      { epoch: 5, loss: 0.6 },
      { epoch: 6, loss: 0.45 },
      { epoch: 7, loss: 0.38 }
    ]

    const margin = { top: 20, right: 30, bottom: 40, left: 60 }
    const width = 800 - margin.left - margin.right
    const height = 300 - margin.top - margin.bottom

    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`)

    const x = d3.scaleLinear()
      .domain(d3.extent(data, d => d.epoch))
      .range([0, width])

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.loss) * 1.1])
      .range([height, 0])

    const line = d3.line()
      .x(d => x(d.epoch))
      .y(d => y(d.loss))
      .curve(d3.curveMonotoneX)

    svg.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x).ticks(7))
      .attr('color', chartStyles.timeline.text.fill)

    svg.append('g')
      .call(d3.axisLeft(y))
      .attr('color', chartStyles.timeline.text.fill)

    svg.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', chartColors.query)
      .attr('stroke-width', 2)
      .attr('d', line)

    svg.selectAll('circle')
      .data(data)
      .enter()
      .append('circle')
      .attr('cx', d => x(d.epoch))
      .attr('cy', d => y(d.loss))
      .attr('r', 4)
      .attr('fill', chartColors.query)

    svg.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('y', 0 - margin.left)
      .attr('x', 0 - (height / 2))
      .attr('dy', '1em')
      .style('text-anchor', 'middle')
      .attr('fill', chartStyles.timeline.text.fill)
      .text('Training Loss')

    svg.append('text')
      .attr('x', width / 2)
      .attr('y', height + margin.bottom - 5)
      .style('text-anchor', 'middle')
      .attr('fill', chartStyles.timeline.text.fill)
      .text('Epoch')

  }, [])

  return <svg ref={svgRef}></svg>
}

export default TrainingMetricsChart
