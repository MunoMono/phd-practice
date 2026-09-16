import * as d3 from 'd3'

export const createVisualizationTooltip = (className = '') => {
  const tooltip = d3.select('body')
    .append('div')
    .attr('class', ['viz-tooltip', className].filter(Boolean).join(' '))
    .style('visibility', 'hidden')

  return tooltip
}

export const showVisualizationTooltip = (tooltip, html, event, offset = { x: 10, y: -10 }) => {
  tooltip
    .interrupt()
    .style('visibility', 'visible')

  tooltip
    .html(html)
    .style('left', `${event.pageX + offset.x}px`)
    .style('top', `${event.pageY + offset.y}px`)
}

export const moveVisualizationTooltip = (tooltip, event, offset = { x: 10, y: -10 }) => {
  tooltip
    .style('left', `${event.pageX + offset.x}px`)
    .style('top', `${event.pageY + offset.y}px`)
}

export const hideVisualizationTooltip = (tooltip) => {
  tooltip
    .interrupt()
    .style('visibility', 'hidden')
}

export const removeVisualizationTooltip = (tooltip) => {
  tooltip.remove()
}