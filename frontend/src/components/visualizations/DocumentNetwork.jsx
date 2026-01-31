import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Loading } from '@carbon/react';
import { carbonColors, d3Scales, chartStyles, animations } from '../../utils/carbonD3Theme';
import './DocumentNetwork.scss';

const DocumentNetwork = () => {
  const svgRef = useRef();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    fetchNetworkData();
    
    // Set up resize observer
    const resizeObserver = new ResizeObserver(entries => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width, height: Math.max(height, 500) });
      }
    });

    if (svgRef.current?.parentElement) {
      resizeObserver.observe(svgRef.current.parentElement);
    }

    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    if (data && dimensions.width > 0) {
      renderNetwork();
    }
  }, [data, dimensions]);

  const fetchNetworkData = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/viz/document-network`);
      const networkData = await response.json();
      setData(networkData);
    } catch (error) {
      console.error('Failed to fetch network data:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderNetwork = () => {
    if (!data || !svgRef.current) return;

    const { width, height } = dimensions;
    const margin = { top: 20, right: 20, bottom: 20, left: 20 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height]);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Create zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.5, 5])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Color scale for clusters
    const colorScale = d3Scales.categorical(data.clusters.map(c => c.theme));

    // Size scale for nodes (based on PDF count)
    const sizeScale = d3Scales.nodeSize(
      Math.min(...data.nodes.map(n => n.pdf_count)),
      Math.max(...data.nodes.map(n => n.pdf_count))
    );

    // Create force simulation
    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.links)
        .id(d => d.id)
        .distance(d => 100 - (d.weight * 50)) // Closer for stronger connections
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(innerWidth / 2, innerHeight / 2))
      .force('collision', d3.forceCollide().radius(d => sizeScale(d.pdf_count) + 5));

    // Create cluster backgrounds
    const clusterGroup = g.append('g').attr('class', 'clusters');

    // Draw links
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(data.links)
      .join('line')
      .attr('stroke', chartStyles.network.link.stroke)
      .attr('stroke-opacity', d => chartStyles.network.link.opacity(d.weight))
      .attr('stroke-width', d => d.weight * 3);

    // Draw nodes
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('circle')
      .data(data.nodes)
      .join('circle')
      .attr('r', d => sizeScale(d.pdf_count))
      .attr('fill', d => {
        const cluster = data.clusters.find(c => 
          c.documents.some(doc => doc.id === d.id)
        );
        return cluster ? colorScale(cluster.theme) : carbonColors.gray[50];
      })
      .attr('stroke', chartStyles.network.node.stroke)
      .attr('stroke-width', chartStyles.network.node.strokeWidth)
      .style('cursor', 'pointer')
      .call(drag(simulation));

    // Add labels
    const label = g.append('g')
      .attr('class', 'labels')
      .selectAll('text')
      .data(data.nodes)
      .join('text')
      .text(d => d.title.length > 30 ? d.title.substring(0, 30) + '...' : d.title)
      .attr('font-size', chartStyles.network.label.fontSize)
      .attr('fill', chartStyles.network.label.fill)
      .attr('text-anchor', 'middle')
      .attr('dy', d => sizeScale(d.pdf_count) + 15)
      .style('pointer-events', 'none')
      .style('opacity', 0);

    // Tooltip
    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'network-tooltip')
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

    // Node interactions
    node
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .attr('r', sizeScale(d.pdf_count) * 1.2)
          .attr('stroke-width', 3);

        // Show label
        label.filter(labelData => labelData.id === d.id)
          .transition()
          .duration(animations.duration.fast)
          .style('opacity', 1);

        // Show tooltip
        const cluster = data.clusters.find(c => 
          c.documents.some(doc => doc.id === d.id)
        );

        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 1);
        
        tooltip.html(`
          <strong>${d.title}</strong><br/>
          PDFs: ${d.pdf_count}<br/>
          Year: ${d.year || 'N/A'}<br/>
          Cluster: ${cluster?.theme || 'N/A'}
        `)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');

        // Highlight connected nodes
        const connectedNodeIds = new Set();
        data.links.forEach(l => {
          if (l.source.id === d.id) connectedNodeIds.add(l.target.id);
          if (l.target.id === d.id) connectedNodeIds.add(l.source.id);
        });

        node.style('opacity', n => 
          n.id === d.id || connectedNodeIds.has(n.id) ? 1 : 0.2
        );

        link.style('opacity', l => 
          l.source.id === d.id || l.target.id === d.id ? 
          chartStyles.network.link.opacity(l.weight) : 0.05
        );
      })
      .on('mouseout', function(event, d) {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .attr('r', sizeScale(d.pdf_count))
          .attr('stroke-width', chartStyles.network.node.strokeWidth);

        label.filter(labelData => labelData.id === d.id)
          .transition()
          .duration(animations.duration.fast)
          .style('opacity', 0);

        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 0);

        node.style('opacity', 1);
        link.style('opacity', l => chartStyles.network.link.opacity(l.weight));
      })
      .on('click', (event, d) => {
        console.log('Clicked document:', d);
        // TODO: Navigate to document detail page
      });

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);

      label
        .attr('x', d => d.x)
        .attr('y', d => d.y);
    });

    // Drag behavior
    function drag(simulation) {
      function dragstarted(event) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      }

      function dragged(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      }

      function dragended(event) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      }

      return d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended);
    }

    // Cleanup tooltip on unmount
    return () => {
      tooltip.remove();
    };
  };

  if (loading) {
    return (
      <div className="network-loading">
        <Loading description="Loading document network..." withOverlay={false} />
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="network-empty">
        <p>No document network data available. Generate embeddings to see relationships.</p>
      </div>
    );
  }

  return (
    <div className="document-network">
      <svg ref={svgRef} />
      <div className="network-legend">
        <h5>Clusters</h5>
        {data.clusters.map((cluster, index) => (
          <div key={cluster.theme} className="legend-item">
            <div 
              className="legend-color" 
              style={{ backgroundColor: d3Scales.categorical(data.clusters.map(c => c.theme))(cluster.theme) }}
            />
            <span>{cluster.theme} ({cluster.documents.length})</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DocumentNetwork;
