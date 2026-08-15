import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { chartColors, chartStyles } from '../../utils/carbonD3Theme'

const TemporalDriftChart = () => {
  const svgRef = useRef()

  useEffect(() => {
    // Sample data for testamentary traces visualization
    const data = [
      { year: 2015, dialectical: 45, emergent: 12 },
      { year: 2017, dialectical: 38, emergent: 23 },
      { year: 2019, dialectical: 29, emergent: 41 },
      { year: 2021, dialectical: 22, emergent: 58 },
      { year: 2023, dialectical: 15, emergent: 72 }
    ]

    const margin = { top: 20, right: 80, bottom: 40, left: 60 }
    const width = 800 - margin.left - margin.right
    const height = 300 - margin.top - margin.bottom

    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`)

    const x = d3.scaleLinear()
      .domain(d3.extent(data, d => d.year))
      .range([0, width])

    const y = d3.scaleLinear()
      .domain([0, 80])
      .range([height, 0])

    const lineDialectical = d3.line()
      .x(d => x(d.year))
      .y(d => y(d.dialectical))
      .curve(d3.curveMonotoneX)

    const lineEmergent = d3.line()
      .x(d => x(d.year))
      .y(d => y(d.emergent))
      .curve(d3.curveMonotoneX)

    svg.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x).tickFormat(d3.format('d')))
      .attr('color', chartStyles.timeline.text.fill)

    svg.append('g')
      .call(d3.axisLeft(y))
      .attr('color', chartStyles.timeline.text.fill)

    svg.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', chartColors.dialectical)
      .attr('stroke-width', 2)
      .attr('d', lineDialectical)

    svg.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', chartColors.emergent)
      .attr('stroke-width', 2)
      .attr('d', lineEmergent)

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(${width - 120}, 20)`)

    legend.append('line')
      .attr('x1', 0)
      .attr('x2', 30)
      .attr('y1', 0)
      .attr('y2', 0)
      .attr('stroke', chartColors.dialectical)
      .attr('stroke-width', 2)

    legend.append('text')
      .attr('x', 35)
      .attr('y', 5)
      .text('Dialectical')
      .attr('fill', chartStyles.timeline.text.fill)
      .style('font-size', '12px')

    legend.append('line')
      .attr('x1', 0)
      .attr('x2', 30)
      .attr('y1', 20)
      .attr('y2', 20)
      .attr('stroke', chartColors.emergent)
      .attr('stroke-width', 2)

    legend.append('text')
      .attr('x', 35)
      .attr('y', 25)
      .text('Emergent')
      .attr('fill', chartStyles.timeline.text.fill)
      .style('font-size', '12px')

  }, [])

  return (
    <div className="temporal-drift-chart">
      <svg ref={svgRef}></svg>
    </div>
  )
}

export default TemporalDriftChart
