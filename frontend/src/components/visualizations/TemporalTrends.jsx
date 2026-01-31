import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Loading } from '@carbon/react';
import { carbonColors, d3Scales, chartStyles, animations } from '../../utils/carbonD3Theme';
import './TemporalTrends.scss';

const TemporalTrends = () => {
  const svgRef = useRef();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    fetchTrendsData();
    
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
  }, [data, dimensions]);

  const fetchTrendsData = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/viz/temporal-trends`);
      const trendsData = await response.json();
      setData(trendsData);
    } catch (error) {
      console.error('Failed to fetch trends data:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderChart = () => {
    if (!data || !svgRef.current) return;

    const { width, height } = dimensions;
    const margin = { top: 40, right: 120, bottom: 60, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Parse years
    const parseYear = d3.timeParse('%Y');
    data.trends.forEach(d => {
      d.parsedYear = parseYear(d.year.toString());
    });

    // Scales
    const xScale = d3.scaleTime()
      .domain(d3.extent(data.trends, d => d.parsedYear))
      .range([0, innerWidth]);

    const yScaleDocs = d3.scaleLinear()
      .domain([0, d3.max(data.trends, d => d.document_count)])
      .range([innerHeight, 0])
      .nice();

    const yScalePdfs = d3.scaleLinear()
      .domain([0, d3.max(data.trends, d => d.pdf_count)])
      .range([innerHeight, 0])
      .nice();

    // Axes
    const xAxis = d3.axisBottom(xScale)
      .ticks(d3.timeYear.every(2))
      .tickFormat(d3.timeFormat('%Y'));

    const yAxisDocs = d3.axisLeft(yScaleDocs);
    const yAxisPdfs = d3.axisRight(yScalePdfs);

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis)
      .style('font-size', '12px')
      .style('color', carbonColors.gray[70])
      .selectAll('text')
      .attr('transform', 'rotate(-45)')
      .style('text-anchor', 'end');

    g.append('g')
      .call(yAxisDocs)
      .style('font-size', '12px')
      .style('color', carbonColors.gray[70]);

    g.append('g')
      .attr('transform', `translate(${innerWidth},0)`)
      .call(yAxisPdfs)
      .style('font-size', '12px')
      .style('color', carbonColors.gray[70]);

    // Axis labels
    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('y', -45)
      .attr('x', -innerHeight / 2)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .style('fill', carbonColors.primary)
      .text('Documents');

    g.append('text')
      .attr('transform', 'rotate(90)')
      .attr('y', -innerWidth - 45)
      .attr('x', innerHeight / 2)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .style('fill', carbonColors.purple)
      .text('PDFs');

    // Area generators
    const areaDocs = d3.area()
      .x(d => xScale(d.parsedYear))
      .y0(innerHeight)
      .y1(d => yScaleDocs(d.document_count))
      .curve(d3.curveMonotoneX);

    const areaPdfs = d3.area()
      .x(d => xScale(d.parsedYear))
      .y0(innerHeight)
      .y1(d => yScalePdfs(d.pdf_count))
      .curve(d3.curveMonotoneX);

    // Line generators
    const lineDocs = d3.line()
      .x(d => xScale(d.parsedYear))
      .y(d => yScaleDocs(d.document_count))
      .curve(d3.curveMonotoneX);

    const linePdfs = d3.line()
      .x(d => xScale(d.parsedYear))
      .y(d => yScalePdfs(d.pdf_count))
      .curve(d3.curveMonotoneX);

    // Draw areas
    g.append('path')
      .datum(data.trends)
      .attr('class', 'area-docs')
      .attr('fill', carbonColors.primary)
      .attr('opacity', 0.2)
      .attr('d', areaDocs);

    g.append('path')
      .datum(data.trends)
      .attr('class', 'area-pdfs')
      .attr('fill', carbonColors.purple)
      .attr('opacity', 0.2)
      .attr('d', areaPdfs);

    // Draw lines
    const pathDocs = g.append('path')
      .datum(data.trends)
      .attr('class', 'line-docs')
      .attr('fill', 'none')
      .attr('stroke', carbonColors.primary)
      .attr('stroke-width', 3)
      .attr('d', lineDocs);

    const pathPdfs = g.append('path')
      .datum(data.trends)
      .attr('class', 'line-pdfs')
      .attr('fill', 'none')
      .attr('stroke', carbonColors.purple)
      .attr('stroke-width', 3)
      .attr('d', linePdfs);

    // Animate lines
    const lengthDocs = pathDocs.node().getTotalLength();
    const lengthPdfs = pathPdfs.node().getTotalLength();

    pathDocs
      .attr('stroke-dasharray', lengthDocs + ' ' + lengthDocs)
      .attr('stroke-dashoffset', lengthDocs)
      .transition()
      .duration(animations.duration.slow)
      .attr('stroke-dashoffset', 0);

    pathPdfs
      .attr('stroke-dasharray', lengthPdfs + ' ' + lengthPdfs)
      .attr('stroke-dashoffset', lengthPdfs)
      .transition()
      .duration(animations.duration.slow)
      .delay(200)
      .attr('stroke-dashoffset', 0);

    // Tooltip
    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'trends-tooltip')
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

    // Points and interactions
    const pointsDocs = g.selectAll('.point-doc')
      .data(data.trends)
      .join('circle')
      .attr('class', 'point-doc')
      .attr('cx', d => xScale(d.parsedYear))
      .attr('cy', d => yScaleDocs(d.document_count))
      .attr('r', 0)
      .attr('fill', carbonColors.primary)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .attr('r', 8);

        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 1);
        
        tooltip.html(`
          <strong>${d.year}</strong><br/>
          Documents: ${d.document_count}<br/>
          PDFs: ${d.pdf_count}
        `)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseout', function() {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .attr('r', 5);

        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 0);
      });

    pointsDocs
      .transition()
      .delay((d, i) => i * 100 + 800)
      .duration(animations.duration.normal)
      .attr('r', 5);

    // Legend
    const legend = svg.append('g')
      .attr('class', 'legend')
      .attr('transform', `translate(${width - margin.right + 20},${margin.top})`);

    const legendData = [
      { label: 'Documents', color: carbonColors.primary },
      { label: 'PDFs', color: carbonColors.purple }
    ];

    legendData.forEach((item, i) => {
      const legendRow = legend.append('g')
        .attr('transform', `translate(0,${i * 25})`);

      legendRow.append('line')
        .attr('x1', 0)
        .attr('x2', 30)
        .attr('y1', 0)
        .attr('y2', 0)
        .attr('stroke', item.color)
        .attr('stroke-width', 3);

      legendRow.append('text')
        .attr('x', 40)
        .attr('y', 4)
        .style('font-size', '12px')
        .style('fill', carbonColors.gray[70])
        .text(item.label);
    });

    // Cleanup
    return () => {
      tooltip.remove();
    };
  };

  if (loading) {
    return (
      <div className="trends-loading">
        <Loading description="Loading temporal trends..." withOverlay={false} />
      </div>
    );
  }

  if (!data || data.trends.length === 0) {
    return (
      <div className="trends-empty">
        <p>No temporal data available.</p>
      </div>
    );
  }

  return (
    <div className="temporal-trends">
      <svg ref={svgRef} />
    </div>
  );
};

export default TemporalTrends;
