import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Loading, Toggle } from '@carbon/react';
import { carbonColors, d3Scales, chartStyles, animations, utils } from '../../utils/carbonD3Theme';
import './ThemeDistribution.scss';

const ThemeDistribution = () => {
  const svgRef = useRef();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [viewType, setViewType] = useState('donut'); // 'donut' or 'bar'
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    fetchThemeData();
    
    const resizeObserver = new ResizeObserver(entries => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width, height: Math.max(height, 400) });
      }
    });

    if (svgRef.current?.parentElement) {
      resizeObserver.observe(svgRef.current.parentElement);
    }

    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    if (data && dimensions.width > 0) {
      renderChart();
    }
  }, [data, dimensions, viewType]);

  const fetchThemeData = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/viz/theme-distribution`);
      const themeData = await response.json();
      setData(themeData);
    } catch (error) {
      console.error('Failed to fetch theme data:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderChart = () => {
    if (!data || !svgRef.current) return;

    const { width, height } = dimensions;
    const margin = viewType === 'donut' 
      ? { top: 40, right: 40, bottom: 40, left: 40 }
      : { top: 40, right: 40, bottom: 60, left: 200 };

    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    if (viewType === 'donut') {
      renderDonutChart(svg, width, height, margin);
    } else {
      renderBarChart(svg, width, height, margin);
    }
  };

  const renderDonutChart = (svg, width, height, margin) => {
    const radius = Math.min(width - margin.left - margin.right, height - margin.top - margin.bottom) / 2;
    const innerRadius = radius * 0.6;

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2},${height / 2})`);

    const colorScale = d3Scales.categorical(data.themes.map(d => d.theme));

    const pie = d3.pie()
      .value(d => d.count)
      .sort(null);

    const arc = d3.arc()
      .innerRadius(innerRadius)
      .outerRadius(radius);

    const hoverArc = d3.arc()
      .innerRadius(innerRadius)
      .outerRadius(radius + 10);

    // Tooltip
    const tooltip = createTooltip();

    // Draw slices
    const slices = g.selectAll('path')
      .data(pie(data.themes))
      .join('path')
      .attr('d', arc)
      .attr('fill', d => colorScale(d.data.theme))
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .attr('d', hoverArc);

        const percentage = ((d.data.count / d3.sum(data.themes, t => t.count)) * 100).toFixed(1);
        
        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 1);
        
        tooltip.html(`
          <strong>${d.data.theme}</strong><br/>
          Documents: ${d.data.count}<br/>
          Percentage: ${percentage}%
        `)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseout', function() {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .attr('d', arc);

        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 0);
      });

    // Animate on mount
    slices
      .transition()
      .duration(animations.duration.slow)
      .attrTween('d', function(d) {
        const interpolate = d3.interpolate({ startAngle: 0, endAngle: 0 }, d);
        return function(t) {
          return arc(interpolate(t));
        };
      });

    // Center text
    const total = d3.sum(data.themes, d => d.count);
    g.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '-0.5em')
      .style('font-size', '32px')
      .style('font-weight', '600')
      .style('fill', carbonColors.gray[100])
      .text(total);

    g.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '1.5em')
      .style('font-size', '14px')
      .style('fill', carbonColors.gray[70])
      .text('Total Documents');
  };

  const renderBarChart = (svg, width, height, margin) => {
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Sort data by count
    const sortedData = [...data.themes].sort((a, b) => b.count - a.count);

    const colorScale = d3Scales.categorical(sortedData.map(d => d.theme));

    const xScale = d3.scaleLinear()
      .domain([0, d3.max(sortedData, d => d.count)])
      .range([0, innerWidth]);

    const yScale = d3.scaleBand()
      .domain(sortedData.map(d => d.theme))
      .range([0, innerHeight])
      .padding(0.2);

    // Tooltip
    const tooltip = createTooltip();

    // Draw bars
    g.selectAll('rect')
      .data(sortedData)
      .join('rect')
      .attr('x', 0)
      .attr('y', d => yScale(d.theme))
      .attr('width', 0)
      .attr('height', yScale.bandwidth())
      .attr('fill', d => colorScale(d.theme))
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .style('opacity', 0.8);

        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 1);
        
        tooltip.html(`
          <strong>${d.theme}</strong><br/>
          Documents: ${d.count}
        `)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseout', function() {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .style('opacity', 1);

        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 0);
      })
      .transition()
      .duration(animations.duration.slow)
      .attr('width', d => xScale(d.count));

    // Add value labels
    g.selectAll('text.value')
      .data(sortedData)
      .join('text')
      .attr('class', 'value')
      .attr('x', d => xScale(d.count) + 5)
      .attr('y', d => yScale(d.theme) + yScale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .style('font-size', '12px')
      .style('fill', carbonColors.gray[70])
      .style('opacity', 0)
      .text(d => d.count)
      .transition()
      .delay(animations.duration.slow)
      .duration(animations.duration.normal)
      .style('opacity', 1);

    // Y axis (theme labels)
    g.append('g')
      .call(d3.axisLeft(yScale))
      .style('font-size', '12px')
      .style('color', carbonColors.gray[70])
      .select('.domain').remove();

    // X axis
    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).ticks(5))
      .style('font-size', '12px')
      .style('color', carbonColors.gray[70])
      .select('.domain').remove();

    // X axis label
    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 40)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .style('fill', carbonColors.gray[70])
      .text('Number of Documents');
  };

  const createTooltip = () => {
    return d3.select('body')
      .append('div')
      .attr('class', 'theme-tooltip')
      .style('opacity', 0)
      .style('position', 'absolute')
      .style('background-color', carbonColors.gray[100])
      .style('color', carbonColors.gray[10])
      .style('padding', '12px')
      .style('border-radius', '4px')
      .style('font-family', 'IBM Plex Sans')
      .style('font-size', '14px')
      .style('pointer-events', 'none')
      .style('z-index', 1000);
  };

  if (loading) {
    return (
      <div className="theme-loading">
        <Loading description="Loading theme distribution..." withOverlay={false} />
      </div>
    );
  }

  if (!data || data.themes.length === 0) {
    return (
      <div className="theme-empty">
        <p>No theme data available. Process documents with ML to extract themes.</p>
      </div>
    );
  }

  return (
    <div className="theme-distribution">
      <div className="chart-controls">
        <Toggle
          id="view-toggle"
          labelText="Chart Type"
          labelA="Donut"
          labelB="Bar"
          toggled={viewType === 'bar'}
          onToggle={(checked) => setViewType(checked ? 'bar' : 'donut')}
          size="sm"
        />
      </div>
      <svg ref={svgRef} />
    </div>
  );
};

export default ThemeDistribution;
